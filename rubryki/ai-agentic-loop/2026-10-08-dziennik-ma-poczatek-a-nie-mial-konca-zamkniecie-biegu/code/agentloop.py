"""Nadzorca petli agentowej v2: cykl zycia dziennika (zamkniecie biegu, czas, naprawa ogona,
reczne rozstrzygniecie NEEDS_HUMAN). Rozwija nadzorce z wydania #14.

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


class JournalCorrupt(Exception):
    """Uszkodzenie w SRODKU dziennika (nie w ogonie) - tego nie naprawiamy automatycznie."""


class ResolveError(Exception):
    """Reczne rozstrzygniecie nie pasuje do stanu dziennika."""


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
    loop_window_repeat: int = 3
    cycle_repeats: int = 3
    no_progress: int = 4
    max_attempts: int = 4
    backoff_base: float = 1.0
    backoff_cap: float = 8.0


class VirtualClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.now += s


# stany koncowe biegu: po nich wznowienie NIE wykonuje juz zadnej pracy
FINAL = {"DONE", "LOOP", "NO_PROGRESS"}
# NEEDS_HUMAN jest koncowy dopoki czlowiek nie dopisze rekordu 'resolve'
# BUDGET_* sa wznawialne: zwiekszasz budzet i bieg idzie dalej


# ---------------------------------------------------------------- funkcje czyste
def canonical(args: dict) -> str:
    return json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(a: Action) -> str:
    return a.tool + ":" + canonical(a.args)


def idem_key(run_id: str, step: int, a: Action) -> str:
    return hashlib.sha256(f"{run_id}|{step}|{fingerprint(a)}".encode()).hexdigest()[:16]


def error_signature(out: str) -> str:
    first = out.strip().splitlines()[0] if out.strip() else ""
    return re.sub(r"\d+", "N", first)


def backoff_delay(attempt: int, base: float, cap: float, rng: random.Random) -> float:
    return rng.uniform(0, min(cap, base * (2 ** attempt)))


def detect_loop(fps: list[str], b: Budget) -> Optional[str]:
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
    errs = [s for s in sigs if s is not None]
    n = b.no_progress
    if len(errs) >= n and len(set(errs[-n:])) == 1:
        return f"NO_PROGRESS: {n}x ten sam blad '{errs[-1]}' mimo roznych akcji"
    return None


# ---------------------------------------------------------------- dziennik
class Journal:
    """Write-ahead log w JSONL. Rekordy: intent, result, end, resolve.

    repair=True (domyslnie): przed pierwszym zapisem obcina urwany OSTATNI wiersz.
    repair=False odtwarza zachowanie z #14 (zostawione tylko po to, by pokazac blad).
    """

    def __init__(self, path: str, repair: bool = True) -> None:
        self.path = path
        self.repair = repair
        self.repaired_bytes = 0          # ile bajtow urwanego ogona obcieto
        self._checked = False

    def _scan(self) -> tuple[list[dict], int, bool]:
        """Zwraca (rekordy, offset konca ostatniego dobrego wiersza, czy_ogon_uszkodzony)."""
        if not os.path.exists(self.path):
            return [], 0, False
        with open(self.path, "rb") as f:
            raw = f.read()
        lines = raw.split(b"\n")
        trailing = lines.pop()           # tekst po ostatnim \n ('' jesli plik konczy sie \n)
        recs: list[dict] = []
        good_end = 0
        for i, line in enumerate(lines):
            if not line.strip():
                good_end += len(line) + 1
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                # zly wiersz zakonczony \n: jesli to nie ostatni wiersz - uszkodzenie w srodku
                if i != len(lines) - 1 or trailing:
                    raise JournalCorrupt(f"wiersz {i + 1} uszkodzony, a po nim sa dane")
                return recs, good_end, True
            good_end += len(line) + 1
        if trailing.strip():
            try:
                recs.append(json.loads(trailing))   # poprawny JSON, tylko bez \n
                return recs, good_end, True          # ogon do 'domkniecia' znakiem nowej linii
            except json.JSONDecodeError:
                return recs, good_end, True
        return recs, good_end, False

    def read(self) -> list[dict]:
        if not self.repair:
            return self._read_legacy()
        return self._scan()[0]

    def _read_legacy(self) -> list[dict]:
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
                    break
        return out

    def _repair_tail(self) -> None:
        recs, good_end, bad = self._scan()
        if not bad:
            return
        with open(self.path, "rb") as f:
            raw = f.read()
        tail = raw[good_end:]
        try:
            json.loads(tail)             # poprawny JSON bez \n: dopisz tylko \n
            with open(self.path, "ab") as f:
                f.write(b"\n")
                f.flush()
                os.fsync(f.fileno())
        except json.JSONDecodeError:
            with open(self.path, "r+b") as f:
                f.truncate(good_end)
                f.flush()
                os.fsync(f.fileno())
            self.repaired_bytes = len(tail)

    def append(self, rec: dict) -> None:
        if self.repair and not self._checked:
            self._repair_tail()
        self._checked = True
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())


@dataclass
class Step:
    n: int
    action: Action
    ok: bool
    out: str
    attempts: int = 1


@dataclass
class RunResult:
    status: str                     # DONE | BUDGET_* | LOOP | NO_PROGRESS | NEEDS_HUMAN
    reason: str
    steps: list[Step] = field(default_factory=list)
    cost: int = 0
    resumed_from: int = 0
    replayed: bool = False          # True = bieg byl juz zamkniety, nic nie wykonano
    vt: float = 0.0                 # czas wirtualny na koniec


@dataclass
class State:
    steps: list[Step]
    pending: Optional[dict]
    last_end: Optional[dict]
    vt: float
    approved_retry: bool = False    # czlowiek potwierdzil: pending NIE wykonano -> wolno powtorzyc


def fold(recs: list[dict]) -> State:
    """Sklada dziennik w stan. Jedyne miejsce, ktore rozumie semantyke rekordow."""
    steps: list[Step] = []
    pending: Optional[dict] = None
    last_end: Optional[dict] = None
    vt = 0.0
    approved = False
    for rec in recs:
        vt = max(vt, rec.get("vt", 0.0))
        t = rec["t"]
        if t == "intent":
            pending, last_end, approved = rec, None, False   # nowa praca = poprzedni 'end' uniewazniony
        elif t == "result" and pending and pending["step"] == rec["step"]:
            steps.append(Step(rec["step"], Action(pending["tool"], pending["args"]),
                              rec["ok"], rec["out"], rec.get("attempts", 1)))
            pending = None
        elif t == "end":
            last_end = rec
        elif t == "resolve" and pending and pending["step"] == rec["step"]:
            if rec["outcome"] == "executed":
                steps.append(Step(rec["step"], Action(pending["tool"], pending["args"]),
                                  rec.get("ok", True), rec["out"], 0))   # attempts=0: wynik od czlowieka
                pending = None
            else:
                approved = True
            if last_end and last_end["status"] == "NEEDS_HUMAN":
                last_end = None
    return State(steps, pending, last_end, vt, approved)


def resolve(journal: Journal, step: int, outcome: str, out: str = "", ok: bool = True) -> None:
    """Czlowiek rozstrzyga NEEDS_HUMAN: 'executed' (efekt zaszedl; podaj obserwacje) albo 'not_executed'."""
    if outcome not in ("executed", "not_executed"):
        raise ResolveError("outcome: executed | not_executed")
    st = fold(journal.read())
    if not st.pending or st.pending["step"] != step:
        raise ResolveError(f"krok {step} nie jest wiszacy (pending: "
                           f"{st.pending['step'] if st.pending else None})")
    if outcome == "executed" and not out:
        raise ResolveError("dla 'executed' podaj obserwacje (out) - agent musi cos zobaczyc")
    journal.append({"t": "resolve", "step": step, "outcome": outcome, "out": out, "ok": ok, "vt": st.vt})


Policy = Callable[[list[Step]], "Action | Done"]


class Supervisor:
    def __init__(self, tools: dict[str, Tool], budget: Budget, journal: Journal,
                 clock: Optional[VirtualClock] = None, seed: int = 7, run_id: str = "run1",
                 crash_hook: Optional[Callable[[str, int], None]] = None,
                 restore_clock: bool = True) -> None:
        self.tools, self.b, self.j = tools, budget, journal
        self.clock = clock or VirtualClock()
        self.rng = random.Random(seed)
        self.run_id = run_id
        self.crash_hook = crash_hook or (lambda point, step: None)
        self.restore_clock = restore_clock

    def _w(self, rec: dict) -> None:
        rec["vt"] = round(self.clock.now, 6)
        self.j.append(rec)

    def _execute(self, a: Action, key: str) -> tuple[bool, str, int]:
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
            except Exception as e:
                return False, f"{type(e).__name__}: {e}", attempt + 1

    def run(self, policy: Policy) -> RunResult:
        st = fold(self.j.read())
        steps, pending, last_end = st.steps, st.pending, st.last_end
        if self.restore_clock:
            self.clock.now = max(self.clock.now, st.vt)
        resumed_from = len(steps)
        cost = sum(len(canonical(s.action.args) + s.out) // 4 + 1 for s in steps)
        fps = [fingerprint(s.action) for s in steps]
        sigs: list[Optional[str]] = [None if s.ok else error_signature(s.out) for s in steps]

        def res(status: str, reason: str) -> RunResult:
            if not (last_end and last_end["status"] == status and last_end["reason"] == reason):
                self._w({"t": "end", "status": status, "reason": reason})
            return RunResult(status, reason, steps, cost, resumed_from, False, self.clock.now)

        # 1. bieg zamkniety: odtworz wynik z dziennika, nie dotykaj ani modelu, ani narzedzi
        if last_end and (last_end["status"] in FINAL or last_end["status"] == "NEEDS_HUMAN"):
            return RunResult(last_end["status"], last_end["reason"], steps, cost, resumed_from,
                             True, self.clock.now)

        # 2. krok przerwany w polowie
        if pending is not None:
            a = Action(pending["tool"], pending["args"])
            tool = self.tools.get(a.tool)
            if tool and tool.side_effect and not tool.honors_key and not st.approved_retry:
                return res("NEEDS_HUMAN", f"krok {pending['step']} ({a.tool}) mogl sie wykonac, "
                                          "narzedzie nie honoruje klucza idempotencji")
            ok, out, att = self._execute(a, pending["key"])   # ten sam klucz!
            self._w({"t": "result", "step": pending["step"], "ok": ok, "out": out, "attempts": att})
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
            self._w({"t": "intent", "step": n, "tool": a.tool, "args": a.args, "key": key})
            last_end = None
            self.crash_hook("after_intent", n)
            ok, out, att = self._execute(a, key)
            self.crash_hook("after_effect", n)
            self._w({"t": "result", "step": n, "ok": ok, "out": out, "attempts": att})
            steps.append(Step(n, a, ok, out, att))
            fps.append(fingerprint(a)); sigs.append(None if ok else error_signature(out))
            cost += len(canonical(a.args) + out) // 4 + 1
            why = detect_loop(fps, self.b)
            if why:
                return res("LOOP", why)
            why = detect_no_progress(sigs, self.b)
            if why:
                return res("NO_PROGRESS", why)
