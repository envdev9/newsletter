"""Wspolny kod testow i demo: uruchamianie PRAWDZIWYCH procesow (subprocess) i liczenie skutkow.
Wszystkie katalogi robocze sa tymczasowe (/tmp/prasowka-lock-*) i sprzatane przez workdir()."""
from __future__ import annotations

import contextlib
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Iterator, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from agentloop import Journal, fold   # noqa: E402


@contextlib.contextmanager
def workdir() -> Iterator[str]:
    d = tempfile.mkdtemp(prefix="prasowka-lock-")
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def spawn(script: str, *args: str) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-B", os.path.join(HERE, script), *args],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def finish(p: subprocess.Popen, timeout: float = 60.0) -> dict:
    out, err = p.communicate(timeout=timeout)
    line = out.strip().splitlines()[-1] if out.strip() else "{}"
    d = json.loads(line)
    d["rc"] = p.returncode
    if p.returncode not in (0, 75):
        d["stderr"] = err[-400:]
    return d


def effects(d: str) -> list[list[str]]:
    try:
        with open(os.path.join(d, "effects.log")) as f:
            return [ln.split() for ln in f.read().splitlines() if ln.strip()]
    except FileNotFoundError:
        return []


def journal_stats(d: str) -> dict:
    """Czytamy dziennik jak nadzorca: rekord po rekordzie + fold."""
    j = Journal(os.path.join(d, "journal.jsonl"))
    recs = j.read()
    st = fold(recs)
    return {"records": len(recs),
            "intents": sum(1 for r in recs if r["t"] == "intent"),
            "fold_total": st.summary.total,
            "pending": st.pending is not None,
            "end": st.last_end["status"] if st.last_end else None}


def two_writers(d: str, mode: str, steps: int = 12, tool: str = "keyed", delay: float = 0.003,
                lock_timeout: float = 30.0, compact_every: int = 0) -> list[dict]:
    """Dwa procesy startuja w tej samej chwili na TYM SAMYM dzienniku."""
    start = time.time() + 0.35
    common = ["--dir", d, "--mode", mode, "--steps", str(steps), "--tool", tool, "--delay", str(delay),
              "--start-at", repr(start), "--lock-timeout", str(lock_timeout),
              "--compact-every", str(compact_every)]
    ps = [spawn("worker.py", *common) for _ in range(2)]
    return [finish(p) for p in ps]


def wait_for_effects(d: str, n: int, timeout: float = 20.0) -> None:
    t0 = time.time()
    while len(effects(d)) < n:
        if time.time() - t0 > timeout:
            raise TimeoutError(f"efektow < {n}")
        time.sleep(0.001)


def kill_and_takeover(d: str, kill_after: int, mode: str, tool: str, steps: int = 12,
                      takeover_timeout: float = 15.0) -> dict:
    """A pracuje, po `kill_after` efektach dostaje SIGKILL; B startuje natychmiast po smierci A."""
    a = spawn("worker.py", "--dir", d, "--mode", mode, "--steps", str(steps), "--tool", tool,
              "--delay", "0.004", "--lock-timeout", "30")
    wait_for_effects(d, kill_after)
    os.kill(a.pid, signal.SIGKILL)
    a.wait()
    a.stdout.close()
    a.stderr.close()
    pend = journal_stats(d)["pending"]
    t0 = time.monotonic()
    b = spawn("worker.py", "--dir", d, "--mode", mode, "--steps", str(steps), "--tool", tool,
              "--delay", "0.004", "--lock-timeout", str(takeover_timeout))
    rb = finish(b)
    rb["pending_at_kill"] = pend
    rb["b_wall"] = round(time.monotonic() - t0, 3)
    rb["effects"] = len(effects(d))
    rb["unique_keys"] = len({e[1] for e in effects(d)})
    return rb


def dead_pid() -> int:
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def contend(d: str, kind: str, takeover_delay: float = 0.0, n: int = 2, stale_pid: Optional[int] = None,
            hold: float = 0.03) -> dict:
    """n procesow walczy o zamek, ktory na starcie jest MARTWY (wlasciciel nie zyje) albo wolny."""
    lock = os.path.join(d, "x.lock")
    counter = os.path.join(d, "counter")
    with open(counter, "w") as f:
        f.write("0")
    if stale_pid is not None:
        from joblock import proc_start_ticks   # noqa: F401
        with open(lock, "w") as f:
            json.dump({"pid": stale_pid, "start": 1, "t": 0}, f)
    start = time.time() + 0.3
    ps = [spawn("contender.py", "--lock", lock, "--kind", kind, "--counter", counter, "--start-at", repr(start),
                "--takeover-delay", str(takeover_delay), "--hold", str(hold), "--timeout", "5") for _ in range(n)]
    rs = [finish(p) for p in ps]
    acq = [r for r in rs if r.get("acquired")]
    overlap = False
    for i in range(len(acq)):
        for j in range(i + 1, len(acq)):
            if acq[i]["enter"] < acq[j]["leave"] and acq[j]["enter"] < acq[i]["leave"]:
                overlap = True
    with open(counter) as f:
        cnt = int(f.read())
    return {"acquired": len(acq), "overlap": overlap, "counter": cnt, "expected": len(acq)}
