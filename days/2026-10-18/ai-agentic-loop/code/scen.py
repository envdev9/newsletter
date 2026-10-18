"""Scenariusze na PRAWDZIWYCH procesach (subprocess, SIGSTOP/SIGCONT/SIGKILL). Wspolne dla demo.py i run_tests.py.
Katalogi robocze: /tmp/prasowka-lease-* (sprzatane przez workdir())."""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Iterator

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lease import LeaseStore   # noqa: E402


@contextlib.contextmanager
def workdir() -> Iterator[str]:
    d = tempfile.mkdtemp(prefix="prasowka-lease-")
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def spawn(script: str, *args: str) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-B", os.path.join(HERE, script), *args],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def finish(p: subprocess.Popen, timeout: float = 30.0) -> dict:
    out, err = p.communicate(timeout=timeout)
    d = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
    d["rc"] = p.returncode
    if p.returncode not in (0, 75):
        d["stderr"] = err[-400:]
    return d


def wait_file(path: str, timeout: float = 10.0) -> None:
    t0 = time.time()
    while not os.path.exists(path):
        if time.time() - t0 > timeout:
            raise TimeoutError(path)
        time.sleep(0.002)


def read_log(d: str) -> list[str]:
    try:
        with open(os.path.join(d, "work.log")) as f:
            return [ln.strip() for ln in f if ln.strip()]
    except FileNotFoundError:
        return []


def stale_writes(lines: list[str]) -> int:
    """Wiersze z tokenem NIZSZYM niz token wczesniejszego wiersza = zapis przeterminowanego wlasciciela."""
    hi, bad = 0, 0
    for ln in lines:
        tok = int(ln.split("token=")[1].split()[0])
        if tok < hi:
            bad += 1
        hi = max(hi, tok)
    return bad


def freeze(mode: str, ttl: float = 0.6) -> dict:
    """A bierze dzierzawe, jest zamrozony (SIGSTOP) MIEDZY sprawdzeniem a zapisem, dzierzawa wygasa,
    B przejmuje i pracuje, potem A jest wznawiany (SIGCONT) i dokancza swoj zapis."""
    with workdir() as d:
        common = ["--dir", d, "--mode", mode, "--items", "3", "--ttl", str(ttl)]
        a = spawn("holder.py", *common, "--name", "A", "--step", "0.4")
        wait_file(os.path.join(d, "A.ready.0"))
        os.kill(a.pid, signal.SIGSTOP)
        time.sleep(ttl + 0.3)                                    # dzierzawa A wygasa (heartbeat tez zamrozony)
        b = finish(spawn("holder.py", *common, "--name", "B", "--step", "0.01"))
        os.kill(a.pid, signal.SIGCONT)
        ra = finish(a)
        lines = read_log(d)
        return {"A": ra, "B": b, "log": lines, "stale": stale_writes(lines)}


def flock_vs_lease_freeze(ttl: float = 0.6, flock_timeout: float = 2.0) -> dict:
    """Zamrozony (zywy!) wlasciciel: flock trzyma bez konca, dzierzawa wygasa po ~ttl."""
    with workdir() as d:
        f = os.path.join(d, "x.lock")
        h = spawn("small.py", "flockhold", "--file", f)
        wait_file(f + ".ready")
        os.kill(h.pid, signal.SIGSTOP)
        r_flock = finish(spawn("small.py", "flocktry", "--file", f, "--timeout", str(flock_timeout)))
        os.kill(h.pid, signal.SIGKILL)
        h.wait()
        h.stdout.close()
        h.stderr.close()
    with workdir() as d:
        a = spawn("holder.py", "--dir", d, "--name", "A", "--mode", "fenced", "--ttl", str(ttl), "--hold-forever")
        wait_file(os.path.join(d, "A.acquired"))
        os.kill(a.pid, signal.SIGSTOP)
        t0 = time.monotonic()
        rb = finish(spawn("holder.py", "--dir", d, "--name", "B", "--mode", "fenced", "--ttl", str(ttl),
                          "--items", "1", "--step", "0.01"))
        rb["since_stop"] = round(time.monotonic() - t0, 3)
        os.kill(a.pid, signal.SIGKILL)
        a.wait()
        a.stdout.close()
        a.stderr.close()
    return {"flock": r_flock, "lease": rb}


def long_work(heartbeat: bool, ttl: float = 0.6, work: float = 2.0, probe_at: float = 1.5) -> dict:
    """Zywy wlasciciel z DLUGA praca (work >> ttl). Czy ktos moze mu wlezc w dzierzawe w trakcie?"""
    with workdir() as d:
        extra = [] if heartbeat else ["--no-heartbeat"]
        a = spawn("holder.py", "--dir", d, "--name", "A", "--mode", "checked", "--items", "1", "--step", str(work),
                  "--ttl", str(ttl), *extra)
        wait_file(os.path.join(d, "A.ready.0"))
        time.sleep(probe_at)
        b = finish(spawn("holder.py", "--dir", d, "--name", "B", "--mode", "checked", "--items", "1",
                         "--step", "0.01", "--ttl", str(ttl), "--acquire-timeout", "0.1"))
        ra = finish(a)
        return {"A": ra, "B": b}


def takeover_after_kill(kind: str, ttl: float = 0.6) -> float:
    """Czas od SIGKILL wlasciciela do zdobycia zasobu przez nastepce (s)."""
    with workdir() as d:
        if kind == "lease":
            a = spawn("holder.py", "--dir", d, "--name", "A", "--ttl", str(ttl), "--hold-forever")
            wait_file(os.path.join(d, "A.acquired"))
            time.sleep(0.05)
            os.kill(a.pid, signal.SIGKILL)
            t0 = time.monotonic()
            got = LeaseStore(os.path.join(d, "lease.json"), ttl).acquire_wait("B", 5.0, poll=0.005)
            dt = time.monotonic() - t0
            assert got is not None
        else:
            f = os.path.join(d, "x.lock")
            a = spawn("small.py", "flockhold", "--file", f)
            wait_file(f + ".ready")
            os.kill(a.pid, signal.SIGKILL)
            t0 = time.monotonic()
            r = finish(spawn("small.py", "flocktry", "--file", f, "--timeout", "5"))
            dt = time.monotonic() - t0
            assert r["got"]
        a.wait()
        a.stdout.close()
        a.stderr.close()
        return dt


def race(n: int = 4) -> dict:
    """n procesow jednoczesnie robi try_acquire na wolnej dzierzawie. Ilu wygrywa i z jakimi tokenami?"""
    with workdir() as d:
        start = time.time() + 0.3
        ps = [spawn("small.py", "acq", "--dir", d, "--name", f"P{i}", "--start-at", repr(start)) for i in range(n)]
        rs = [finish(p) for p in ps]
        toks = [r["token"] for r in rs if r.get("token") is not None]
        return {"winners": len(toks), "tokens": toks}
