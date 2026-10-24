"""Scenariusze na prawdziwych procesach: A zamrozony (SIGSTOP), B przejmuje, A wznowiony (SIGCONT) lub zabity."""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections import Counter

from wal import Journal, fold

HERE = os.path.dirname(os.path.abspath(__file__))


def spawn(d: str, name: str, mode: str, think: float, pause: float) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-B", os.path.join(HERE, "actor.py"), "--dir", d, "--name", name,
         "--mode", mode, "--think", str(think), "--pause", str(pause)],
        cwd=HERE)


def wait_event(d: str, needle: str, timeout: float = 10.0) -> None:
    p = os.path.join(d, "events.log")
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        try:
            with open(p) as f:
                if needle in f.read():
                    return
        except FileNotFoundError:
            pass
        time.sleep(0.005)
    raise TimeoutError(needle)


def read_lines(path: str) -> list[str]:
    try:
        with open(path) as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return []


def run(mode: str, freeze_event: str, pause: float = 0.0, kill: bool = False) -> dict:
    """A startuje, po zdarzeniu freeze_event dostaje SIGSTOP; potem startuje B (po wygasnieciu dzierzawy
    przejmuje i konczy); na koncu A dostaje SIGCONT (albo SIGKILL, gdy kill=True)."""
    d = tempfile.mkdtemp(prefix="prasowka-fence-")
    try:
        a = spawn(d, "A", mode, 0.3, pause)
        wait_event(d, freeze_event)
        a.send_signal(signal.SIGSTOP)
        if kill:
            a.send_signal(signal.SIGKILL)
        b = spawn(d, "B", mode, 0.02, 0.0)
        b.wait(timeout=20)
        if not kill:
            a.send_signal(signal.SIGCONT)
        a.wait(timeout=20)
        recs, _ = Journal(os.path.join(d, "journal.jsonl")).read()
        fenced, naive = fold(recs, True), fold(recs, False)
        eff = read_lines(os.path.join(d, "effects.log"))
        per_step = Counter(int(e.split("step=")[1]) for e in eff)
        return {
            "fenced": fenced.summary(), "naive": naive.summary(),
            "effects": eff, "effects_per_step": dict(sorted(per_step.items())),
            "dup_steps": sorted(s for s, n in per_step.items() if n > 1),
            "missing_steps": [s for s in range(6) if s not in per_step],
            "journal_lines": len(recs),
        }
    finally:
        shutil.rmtree(d, ignore_errors=True)
