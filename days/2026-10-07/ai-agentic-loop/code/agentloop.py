"""Nadzorca petli agentowej: budzet, wykrywanie zapetlenia, retry z backoffem,
idempotentne kroki i dziennik (journal) z wznawianiem po awarii.

Rola modelu: funkcja deterministyczna policy(history) -> Action | Done.
To NIE jest LLM ani Claude Code - realny jest caly mechanizm nadzorcy.
Tylko biblioteka standardowa Pythona (testowane: 3.10).
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ---------------------------------------------------------------- typy
@dataclass(frozen=True)
class Action:
    tool: str
    args: dict


@dataclass(frozen=True)
class Done:
    summary: str = ""


class TransientError(Exception):
    """Blad przejsciowy (timeout, 429, 503) - wolno ponowic."""


class SimulatedCrash(BaseException):
    """Symulacja zabicia procesu. BaseException, zeby zaden `except Exception` jej nie polknal."""


class NeedsHuman(Exception):
    """Wznowienie niebezpieczne: krok mogl sie wykonac, a nie umiemy tego sprawdzic."""


@dataclass
class Tool:
    name: str
    fn: Callable[..., str]          # fn(args, key) -> str
    honors_key: bool = False        # czy efekt uboczny jest deduplikowany po kluczu idempotencji
    side_effect: bool = False       # czy ma efekt uboczny (czytanie plikow = False)


@dataclass
class Budget:
    max_steps: int = 20
    max_cost: int = 10_000          # umowne "tokeny": len(tekstu)//4 akcji + wyniku
    max_wall: float = 60.0          # sekundy czasu WIRTUALNEGO (backoff tez go zuzywa)
    loop_window_repeat: int = 3     # tyle identycznych akcji z rzedu = zapetlenie
    cycle_repeats: int = 3          # tyle pelnych powtorzen cyklu okresu 2..3
    no_progress: int = 4            # tyle takich samych sygnatur BLEDU z rzedu
    max_attempts: int = 4           # proby jednego kroku (1 + 3 ponowienia)
    backoff_base: float = 1.0
    backoff_cap: float = 8.0


class VirtualClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.now += s


# ---------------------------------------------------------------- funkcje czyste
def canonical(args: dict) -> str:
    return json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(a: Action) -> str:
    return a.tool + ":" + canonical(a.args)


def idem_key(run_id: str, step: int, a: Action) -> str:
    return hashlib.sha256(f"{run_id}|{step}|{fingerprint(a)}".encode()).hexdigest()[:16]


def error_signature(out: str) -> str:
    """Pierwsza linia bledu bez liczb (numery linii/czasy nie powinny rozrozniac bledow)."""
    first = out.strip().splitlines()[0] if out.strip() else ""
    return re.sub(r"\d+", "N", first)


def backoff_delay(attempt: int, base: float, cap: float, rng: random.Random) -> float:
    """Full jitter: losowo z [0, min(cap, base*2^attempt)]."""
    return rng.uniform(0, min(cap, base * (2 ** attempt)))


def detect_loop(fps: list[str], b: Budget) -> Optional[str]:
    """Zwraca powod zapetlenia albo None. Patrzy tylko na ogon historii."""
    n = b.loop_window_repeat
    if len(fps) >= n and len(set(fps[-n:])) == 1:
        return f"LOOP_EXACT: {n}x ta sama akcja z rzedu"
    for p in (2, 3):
        need = p * b.cycle_repeats
        if len(fps) >= need:
            tail = fps[-need:]
            cyc = tail[:p]
            if len(set(cyc)) > 1 and all(tail[i] == cyc[i % p] for i in range(need)):
                return f"LOOP_CYCLE: cykl okresu {p} powtorzony {b.cycle_repeats}x"
    return None


def detect_no_progress(sigs: list[Optional[str]], b: Budget) -> Optional[str]:
    """Ostatnie N BLEDOW (udane kroki posrednie, np. edycje, pomijamy) maja te sama sygnature."""
    errs = [s for s in sigs if s is not None]
    n = b.no_progress
    if len(errs) >= n and len(set(errs[-n:])) == 1:
        return f"NO_PROGRESS: {n}x ten sam blad '{errs[-1]}' mimo roznych akcji"
    return None


# ---------------------------------------------------------------- dziennik
class Journal:
    """Write-ahead log w JSONL: 'intent' PRZED wykonaniem, 'result' PO."""

    def __init__(self, path: str) -> None:
        self.path = path

    def append(self, rec: dict) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def read(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    break   # urwany ostatni zapis po crashu: ignorujemy ogon
        return out


@dataclass
class Step:
    n: int
    action: Action
    ok: bool
    out: str
    attempts: int = 1


@dataclass
class RunResult:
    status: str                     # DONE | BUDGET_STEPS | BUDGET_COST | BUDGET_WALL | LOOP | NO_PROGRESS | NEEDS_HUMAN
    reason: str
    steps: list[Step] = field(default_factory=list)
    cost: int = 0
    resumed_from: int = 0


Policy = Callable[[list[Step]], "Action | Done"]


class Supervisor:
    def __init__(self, tools: dict[str, Tool], budget: Budget, journal: Journal,
                 clock: Optional[VirtualClock] = None, seed: int = 7, run_id: str = "run1",
                 crash_hook: Optional[Callable[[str, int], None]] = None) -> None:
        self.tools, self.b, self.j = tools, budget, journal
        self.clock = clock or VirtualClock()
        self.rng = random.Random(seed)
        self.run_id = run_id
        self.crash_hook = crash_hook or (lambda point, step: None)

    # -- odtworzenie stanu z dziennika
    def _load(self) -> tuple[list[Step], Optional[dict]]:
        steps: list[Step] = []
        pending: Optional[dict] = None
        for rec in self.j.read():
            if rec["t"] == "intent":
                pending = rec
            elif rec["t"] == "result" and pending and pending["step"] == rec["step"]:
                steps.append(Step(rec["step"], Action(pending["tool"], pending["args"]),
                                  rec["ok"], rec["out"], rec.get("attempts", 1)))
                pending = None
        return steps, pending

    def _execute(self, a: Action, key: str) -> tuple[bool, str, int]:
        """Jedno wywolanie narzedzia z retry. Blad nieprzejsciowy -> obserwacja dla agenta."""
        tool = self.tools.get(a.tool)
        if tool is None:
            return False, f"unknown tool '{a.tool}'", 1
        attempt = 0
        while True:
            try:
                return True, tool.fn(a.args, key), attempt + 1
            except TransientError as e:
                attempt += 1
                if attempt >= self.b.max_attempts:
                    return False, f"TransientError po {attempt} probach: {e}", attempt
                self.clock.sleep(backoff_delay(attempt - 1, self.b.backoff_base,
                                               self.b.backoff_cap, self.rng))
            except Exception as e:  # blad nieprzejsciowy: NIE ponawiamy, oddajemy agentowi
                return False, f"{type(e).__name__}: {e}", attempt + 1

    def run(self, policy: Policy) -> RunResult:
        steps, pending = self._load()
        resumed_from = len(steps)
        cost = sum(len(canonical(s.action.args) + s.out) // 4 + 1 for s in steps)
        fps = [fingerprint(s.action) for s in steps]
        sigs: list[Optional[str]] = [None if s.ok else error_signature(s.out) for s in steps]

        def res(status: str, reason: str) -> RunResult:
            self.j.append({"t": "end", "status": status, "reason": reason})
            return RunResult(status, reason, steps, cost, resumed_from)

        # krok przerwany w polowie: decyzja zalezy od wlasnosci narzedzia
        if pending is not None:
            a = Action(pending["tool"], pending["args"])
            tool = self.tools.get(a.tool)
            if tool and tool.side_effect and not tool.honors_key:
                return res("NEEDS_HUMAN", f"krok {pending['step']} ({a.tool}) mogl sie wykonac, "
                                          "narzedzie nie honoruje klucza idempotencji")
            ok, out, att = self._execute(a, pending["key"])   # ten sam klucz!
            self.j.append({"t": "result", "step": pending["step"], "ok": ok, "out": out, "attempts": att})
            steps.append(Step(pending["step"], a, ok, out, att))
            fps.append(fingerprint(a)); sigs.append(None if ok else error_signature(out))
            cost += len(canonical(a.args) + out) // 4 + 1

        while True:
            if len(steps) >= self.b.max_steps:
                return res("BUDGET_STEPS", f"limit {self.b.max_steps} krokow")
            if cost >= self.b.max_cost:
                return res("BUDGET_COST", f"koszt {cost} >= {self.b.max_cost}")
            if self.clock.now >= self.b.max_wall:
                return res("BUDGET_WALL", f"czas wirtualny {self.clock.now:.1f}s >= {self.b.max_wall}s")
            decision = policy(steps)
            if isinstance(decision, Done):
                return res("DONE", decision.summary)
            n = len(steps) + 1
            a = decision
            key = idem_key(self.run_id, n, a)
            self.j.append({"t": "intent", "step": n, "tool": a.tool, "args": a.args, "key": key})
            self.crash_hook("after_intent", n)
            ok, out, att = self._execute(a, key)
            self.crash_hook("after_effect", n)           # efekt wykonany, wyniku jeszcze nie zapisano
            self.j.append({"t": "result", "step": n, "ok": ok, "out": out, "attempts": att})
            steps.append(Step(n, a, ok, out, att))
            fps.append(fingerprint(a)); sigs.append(None if ok else error_signature(out))
            cost += len(canonical(a.args) + out) // 4 + 1
            why = detect_loop(fps, self.b)
            if why:
                return res("LOOP", why)
            why = detect_no_progress(sigs, self.b)
            if why:
                return res("NO_PROGRESS", why)
