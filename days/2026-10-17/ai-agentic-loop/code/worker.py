"""Proces-pisarz: nadzorca z #14-#18 nad wspolnym dziennikiem, z wybranym trybem blokady.
Rola modelu: funkcja (policy). Efekt uboczny: dopisanie wiersza do effects.log (O_APPEND) - to liczymy.

python3 worker.py --dir D --mode none|flock|flock-nb|excl|excl-stale --steps 12 --delay 0.003 --tool keyed|plain
Wypisuje jedna linie JSON z wynikiem. Kod wyjscia 75 (EX_TEMPFAIL) gdy blokada zajeta.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agentloop import Action, Budget, Done, Journal, Supervisor, Tool, fold   # noqa: E402
from joblock import ExclLock, FlockLock, LockBusy                              # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--mode", default="none")
    ap.add_argument("--steps", type=int, default=12)
    ap.add_argument("--delay", type=float, default=0.003)
    ap.add_argument("--tool", default="keyed")
    ap.add_argument("--start-at", type=float, default=0.0)
    ap.add_argument("--lock-timeout", type=float, default=30.0)
    ap.add_argument("--compact-every", type=int, default=0)
    a = ap.parse_args()

    jpath = os.path.join(a.dir, "journal.jsonl")
    effects = os.path.join(a.dir, "effects.log")

    def charge(args: dict, key: str) -> str:
        time.sleep(a.delay)                                   # "praca" narzedzia
        if a.tool == "keyed":                                 # narzedzie honoruje klucz idempotencji
            try:
                with open(effects) as f:
                    if key in f.read():
                        return "already"
            except FileNotFoundError:
                pass
        fd = os.open(effects, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        os.write(fd, f"{args['i']} {key} {os.getpid()}\n".encode())
        os.close(fd)
        return "charged"

    tools = {"charge": Tool("charge", charge, honors_key=(a.tool == "keyed"), side_effect=True)}

    def policy(h):
        return Action("charge", {"i": h.total}) if h.total < a.steps else Done("komplet")

    while a.start_at and time.time() < a.start_at:            # synchronizacja startu wielu procesow
        pass

    lock = None
    t0 = time.monotonic()
    try:
        if a.mode in ("flock", "flock-nb"):
            lock = FlockLock(jpath + ".lock", timeout=(0.0 if a.mode == "flock-nb" else a.lock_timeout)).acquire()
        elif a.mode in ("excl", "excl-stale"):
            lock = ExclLock(jpath + ".lock", stale_check=(a.mode == "excl-stale")).acquire(a.lock_timeout)
    except LockBusy as e:
        print(json.dumps({"pid": os.getpid(), "busy": True, "holder": e.holder,
                          "waited": round(time.monotonic() - t0, 3)}))
        return 75
    waited = time.monotonic() - t0
    try:
        # UWAGA na kolejnosc: stan (fold dziennika) czytamy DOPIERO po zdobyciu blokady - run() robi to na starcie.
        sup = Supervisor(tools, Budget(max_steps=200, max_cost=10 ** 6), Journal(jpath), run_id="shared",
                         compact_every=a.compact_every, compact_keep=2 if a.compact_every else 3)
        res = sup.run(policy)
    finally:
        if lock:
            lock.release()
    print(json.dumps({"pid": os.getpid(), "busy": False, "status": res.status, "total": res.total,
                      "resumed_from": res.resumed_from, "replayed": res.replayed,
                      "waited": round(waited, 3)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
