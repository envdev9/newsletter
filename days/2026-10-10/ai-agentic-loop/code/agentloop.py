"""Nadzorca petli agentowej v3: snapshoty stanu zamiast pelnej historii (kompaktowanie dziennika)
oraz detektor postepu na hashu drzewa repo. Rozwija nadzorce z wydan #14 i #15.

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

WINDOW = 12   # tyle ostatnich odciskow/sygnatur trzyma podsumowanie (detektory potrzebuja <= 9)


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
    verifies: bool = False          # czy to "weryfikacja" (testy/build): jej porazka liczy sie do TREE_STALL


@dataclass
class Budget:
    max_steps: int = 20
    max_cost: int = 10_000          # umowne "tokeny": len(tekstu)//4 akcji + wyniku
    max_wall: float = 60.0          # sekundy czasu WIRTUALNEGO (backoff tez go zuzywa)
    loop_window_repeat: int = 3
    cycle_repeats: int = 3
    no_progress: int = 4
    tree_repeat: int = 3            # tyle PORAZEK weryfikacji na identycznym drzewie = TREE_STALL
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


FINAL = {"DONE", "LOOP", "NO_PROGRESS"}   # NEEDS_HUMAN koncowy do 'resolve'; BUDGET_* wznawialne


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


def step_cost(args: dict, out: str) -> int:
    return len(canonical(args) + out) // 4 + 1


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


def detect_tree_stall(tree_fail: dict[str, int], tf: Optional[str], b: Budget) -> Optional[str]:
    """tf = hash drzewa, na ktorym wlasnie PADLA weryfikacja (None gdy krok nie byl porazka weryfikacji)."""
    if tf is not None and tree_fail.get(tf, 0) >= b.tree_repeat:
        return (f"TREE_STALL: weryfikacja padla {tree_fail[tf]}x na identycznym drzewie {tf[:8]} "
                f"(tresc kodu sie nie zmienila albo wrocila do znanego stanu)")
    return None


def tree_hash(root: str, ignore: tuple[str, ...] = (".git", "bin", "obj", "__pycache__", "node_modules")) -> str:
    """Hash TRESCI drzewa: sciezki wzgledne + bajty plikow, posortowane. Bez mtime, bez katalogow
    artefaktow buildu (inaczej kazdy build 'zmienia' drzewo)."""
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in ignore)
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            with open(full, "rb") as f:
                data = f.read()
            h.update(rel.encode() + b"\0" + str(len(data)).encode() + b"\0" + data)
    return h.hexdigest()


# ---------------------------------------------------------------- dziennik
class Journal:
    """Write-ahead log w JSONL. Rekordy: intent, result, end, resolve, snapshot.

    repair=True (domyslnie): przed pierwszym zapisem obcina urwany OSTATNI wiersz.
    """

    def __init__(self, path: str, repair: bool = True) -> None:
        self.path = path
        self.repair = repair
        self.repaired_bytes = 0
        self._checked = False

    def _scan(self) -> tuple[list[dict], int, bool]:
        if not os.path.exists(self.path):
            return [], 0, False
        with open(self.path, "rb") as f:
            raw = f.read()
        lines = raw.split(b"\n")
        trailing = lines.pop()
        recs: list[dict] = []
        good_end = 0
        for i, line in enumerate(lines):
            if not line.strip():
                good_end += len(line) + 1
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                if i != len(lines) - 1 or trailing:
                    raise JournalCorrupt(f"wiersz {i + 1} uszkodzony, a po nim sa dane")
                return recs, good_end, True
            good_end += len(line) + 1
        if trailing.strip():
            try:
                recs.append(json.loads(trailing))
                return recs, good_end, True
            except json.JSONDecodeError:
                return recs, good_end, True
        return recs, good_end, False

    def read(self) -> list[dict]:
        return self._scan()[0]

    def size(self) -> int:
        return os.path.getsize(self.path) if os.path.exists(self.path) else 0

    def _repair_tail(self) -> None:
        recs, good_end, bad = self._scan()
        if not bad:
            return
        with open(self.path, "rb") as f:
            raw = f.read()
        tail = raw[good_end:]
        try:
            json.loads(tail)
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
class Summary:
    """Wszystko, co detektory i budzet wiedza o PRZESZLOSCI, ktorej kroki wypadly z okna."""
    total: int = 0                                  # ile krokow lacznie (takze skompaktowanych)
    cost: int = 0
    fps: list[str] = field(default_factory=list)
    sigs: list[Optional[str]] = field(default_factory=list)
    tree_fail: dict[str, int] = field(default_factory=dict)

    def add(self, step: Step, tf: Optional[str]) -> None:
        self.total += 1
        self.cost += step_cost(step.action.args, step.out)
        self.fps = (self.fps + [fingerprint(step.action)])[-WINDOW:]
        self.sigs = (self.sigs + [None if step.ok else error_signature(step.out)])[-WINDOW:]
        if tf is not None:
            self.tree_fail[tf] = self.tree_fail.get(tf, 0) + 1

    def to_dict(self) -> dict:
        return {"total": self.total, "cost": self.cost, "fps": self.fps, "sigs": self.sigs,
                "tree_fail": self.tree_fail}

    @staticmethod
    def from_dict(d: dict) -> "Summary":
        return Summary(d["total"], d["cost"], list(d["fps"]), list(d["sigs"]), dict(d["tree_fail"]))


class History(list):
    """Okno historii widziane przez 'model'. Po kompaktowaniu to tylko OGON; calosc = .total."""

    def __init__(self, steps: list[Step], total: int) -> None:
        super().__init__(steps)
        self.total = total


@dataclass
class RunResult:
    status: str
    reason: str
    steps: list[Step] = field(default_factory=list)   # ogon (po kompaktowaniu: tylko okno)
    cost: int = 0
    resumed_from: int = 0
    replayed: bool = False
    vt: float = 0.0
    total: int = 0                                      # ile krokow lacznie


@dataclass
class State:
    steps: list[Step]
    pending: Optional[dict]
    last_end: Optional[dict]
    vt: float
    approved_retry: bool = False
    summary: Summary = field(default_factory=Summary)


def _step_from(d: dict) -> Step:
    return Step(d["n"], Action(d["tool"], d["args"]), d["ok"], d["out"], d["attempts"])


def fold(recs: list[dict]) -> State:
    """Sklada dziennik w stan. Jedyne miejsce, ktore rozumie semantyke rekordow (takze snapshotow)."""
    steps: list[Step] = []
    pending: Optional[dict] = None
    last_end: Optional[dict] = None
    vt = 0.0
    approved = False
    summ = Summary()
    for rec in recs:
        vt = max(vt, rec.get("vt", 0.0))
        t = rec["t"]
        if t == "snapshot":
            steps = [_step_from(s) for s in rec["steps"]]
            summ = Summary.from_dict(rec["summary"])
            pending, last_end, approved = rec["pending"], rec["last_end"], rec["approved"]
        elif t == "intent":
            pending, last_end, approved = rec, None, False
        elif t == "result" and pending and pending["step"] == rec["step"]:
            st = Step(rec["step"], Action(pending["tool"], pending["args"]),
                      rec["ok"], rec["out"], rec.get("attempts", 1))
            steps.append(st)
            summ.add(st, rec.get("tf"))
            pending = None
        elif t == "end":
            last_end = rec
        elif t == "resolve" and pending and pending["step"] == rec["step"]:
            if rec["outcome"] == "executed":
                st = Step(rec["step"], Action(pending["tool"], pending["args"]),
                          rec.get("ok", True), rec["out"], 0)
                steps.append(st)
                summ.add(st, None)
                pending = None
            else:
                approved = True
            if last_end and last_end["status"] == "NEEDS_HUMAN":
                last_end = None
    return State(steps, pending, last_end, vt, approved, summ)


def compact(journal: Journal, keep: int = 3, archive: bool = False,
            crash_hook: Optional[Callable[[str, int], None]] = None) -> dict:
    """Zastepuje dziennik JEDNYM rekordem 'snapshot' (+ ogon `keep` ostatnich krokow w pelnej postaci).

    Kolejnosc jest wazna: (1) zapis kompletnego pliku tymczasowego + fsync, (2) opcjonalnie twarde
    dowiazanie starego pliku jako archiwum, (3) atomowe os.replace. Crash w dowolnym punkcie zostawia
    albo stary, kompletny dziennik, albo nowy, kompletny - nigdy polowe.
    """
    hook = crash_hook or (lambda p, s: None)
    recs = journal.read()
    st = fold(recs)
    before_bytes, before_recs = journal.size(), len(recs)
    tail = st.steps[-keep:] if keep > 0 else []
    snap = {"t": "snapshot",
            "steps": [{"n": s.n, "tool": s.action.tool, "args": s.action.args, "ok": s.ok,
                       "out": s.out, "attempts": s.attempts} for s in tail],
            "summary": st.summary.to_dict(), "pending": st.pending, "last_end": st.last_end,
            "approved": st.approved_retry, "vt": st.vt, "dropped": st.summary.total - len(tail)}
    tmp = journal.path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:       # stary .tmp po crashu jest po prostu nadpisany
        f.write(json.dumps(snap, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    hook("compact_tmp_written", st.summary.total)
    archived = None
    if archive and os.path.exists(journal.path):
        archived = f"{journal.path}.archive-{st.summary.total:05d}"
        if not os.path.exists(archived):
            os.link(journal.path, archived)
    os.replace(tmp, journal.path)
    journal._checked = False
    hook("compact_replaced", st.summary.total)
    return {"before_bytes": before_bytes, "after_bytes": journal.size(), "before_recs": before_recs,
            "after_recs": 1, "kept_steps": len(tail), "archive": archived}


def resolve(journal: Journal, step: int, outcome: str, out: str = "", ok: bool = True) -> None:
    if outcome not in ("executed", "not_executed"):
        raise ResolveError("outcome: executed | not_executed")
    st = fold(journal.read())
    if not st.pending or st.pending["step"] != step:
        raise ResolveError(f"krok {step} nie jest wiszacy (pending: "
                           f"{st.pending['step'] if st.pending else None})")
    if outcome == "executed" and not out:
        raise ResolveError("dla 'executed' podaj obserwacje (out) - agent musi cos zobaczyc")
    journal.append({"t": "resolve", "step": step, "outcome": outcome, "out": out, "ok": ok, "vt": st.vt})


Policy = Callable[[History], "Action | Done"]


class Supervisor:
    def __init__(self, tools: dict[str, Tool], budget: Budget, journal: Journal,
                 clock: Optional[VirtualClock] = None, seed: int = 7, run_id: str = "run1",
                 crash_hook: Optional[Callable[[str, int], None]] = None,
                 restore_clock: bool = True,
                 observer: Optional[Callable[[], str]] = None,
                 compact_every: int = 0, compact_keep: int = 3, archive: bool = False) -> None:
        self.tools, self.b, self.j = tools, budget, journal
        self.clock = clock or VirtualClock()
        self.rng = random.Random(seed)
        self.run_id = run_id
        self.crash_hook = crash_hook or (lambda point, step: None)
        self.restore_clock = restore_clock
        self.observer = observer                 # () -> hash drzewa; None = bez detektora TREE_STALL
        self.compact_every, self.compact_keep, self.archive = compact_every, compact_keep, archive
        if compact_every and compact_keep >= compact_every:
            raise ValueError("compact_keep musi byc < compact_every, inaczej kompaktowanie nic nie skraca")

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

    def _record(self, n: int, a: Action, ok: bool, out: str, att: int,
                steps: list[Step], summ: Summary) -> Optional[str]:
        """Zapisuje wynik, aktualizuje okno i podsumowanie. Zwraca tf (hash drzewa przy porazce weryfikacji)."""
        tool = self.tools.get(a.tool)
        th = self.observer() if self.observer else None
        rec: dict[str, Any] = {"t": "result", "step": n, "ok": ok, "out": out, "attempts": att}
        tf = th if (th is not None and not ok and tool is not None and tool.verifies) else None
        if th is not None:
            rec["th"] = th
        if tf is not None:
            rec["tf"] = tf
        self._w(rec)
        st = Step(n, a, ok, out, att)
        steps.append(st)
        summ.add(st, tf)
        return tf

    def run(self, policy: Policy) -> RunResult:
        st = fold(self.j.read())
        steps, pending, last_end, summ = st.steps, st.pending, st.last_end, st.summary
        if self.restore_clock:
            self.clock.now = max(self.clock.now, st.vt)
        resumed_from = summ.total

        def res(status: str, reason: str) -> RunResult:
            if not (last_end and last_end["status"] == status and last_end["reason"] == reason):
                self._w({"t": "end", "status": status, "reason": reason})
            return RunResult(status, reason, steps, summ.cost, resumed_from, False,
                             self.clock.now, summ.total)

        if last_end and (last_end["status"] in FINAL or last_end["status"] == "NEEDS_HUMAN"):
            return RunResult(last_end["status"], last_end["reason"], steps, summ.cost, resumed_from,
                             True, self.clock.now, summ.total)

        if pending is not None:
            a = Action(pending["tool"], pending["args"])
            tool = self.tools.get(a.tool)
            if tool and tool.side_effect and not tool.honors_key and not st.approved_retry:
                return res("NEEDS_HUMAN", f"krok {pending['step']} ({a.tool}) mogl sie wykonac, "
                                          "narzedzie nie honoruje klucza idempotencji")
            ok, out, att = self._execute(a, pending["key"])
            self._record(pending["step"], a, ok, out, att, steps, summ)

        while True:
            if summ.total >= self.b.max_steps:
                return res("BUDGET_STEPS", f"limit {self.b.max_steps} krokow")
            if summ.cost >= self.b.max_cost:
                return res("BUDGET_COST", f"koszt {summ.cost} >= {self.b.max_cost}")
            if self.clock.now >= self.b.max_wall:
                return res("BUDGET_WALL", f"czas wirtualny {self.clock.now:.1f}s >= {self.b.max_wall}s")
            decision = policy(History(steps, summ.total))
            if isinstance(decision, Done):
                return res("DONE", decision.summary)
            n = summ.total + 1
            a = decision
            key = idem_key(self.run_id, n, a)
            self._w({"t": "intent", "step": n, "tool": a.tool, "args": a.args, "key": key})
            last_end = None
            self.crash_hook("after_intent", n)
            ok, out, att = self._execute(a, key)
            self.crash_hook("after_effect", n)
            tf = self._record(n, a, ok, out, att, steps, summ)
            for status, reason in (("LOOP", detect_loop(summ.fps, self.b)),
                                   ("NO_PROGRESS", detect_no_progress(summ.sigs, self.b)),
                                   ("NO_PROGRESS", detect_tree_stall(summ.tree_fail, tf, self.b))):
                if reason:
                    return res(status, reason)
            if self.compact_every and len(steps) >= self.compact_every:
                compact(self.j, self.compact_keep, self.archive, self.crash_hook)
                steps[:] = fold(self.j.read()).steps      # okno = to, co zobaczylby proces po restarcie
