"""Zawodnik o blokade: wchodzi do sekcji krytycznej (odczyt licznika, sen, zapis +1) i raportuje przedzial czasu.
Sluzy do mierzenia, czy dwa PRAWDZIWE procesy mogly byc w sekcji krytycznej jednoczesnie.

python3 contender.py --lock PATH --kind flock|excl-stale --counter PATH --start-at EPOCH [--takeover-delay S]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from joblock import ExclLock, FlockLock, LockBusy   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lock", required=True)
    ap.add_argument("--kind", required=True)
    ap.add_argument("--counter", required=True)
    ap.add_argument("--start-at", type=float, default=0.0)
    ap.add_argument("--takeover-delay", type=float, default=0.0)
    ap.add_argument("--hold", type=float, default=0.03)
    ap.add_argument("--timeout", type=float, default=0.0)
    a = ap.parse_args()

    if a.kind == "flock":
        lock = FlockLock(a.lock, timeout=a.timeout)
    else:
        lock = ExclLock(a.lock, stale_check=True, takeover_delay=a.takeover_delay)
    while a.start_at and time.time() < a.start_at:
        pass
    try:
        if a.kind == "flock":
            lock.acquire()
        else:
            lock.acquire(a.timeout)
    except LockBusy:
        print(json.dumps({"pid": os.getpid(), "acquired": False}))
        return 0
    enter = time.time()
    with open(a.counter) as f:
        v = int(f.read() or 0)
    time.sleep(a.hold)
    with open(a.counter, "w") as f:
        f.write(str(v + 1))
    leave = time.time()
    lock.release()
    print(json.dumps({"pid": os.getpid(), "acquired": True, "enter": enter, "leave": leave,
                      "took_over": getattr(lock, "took_over", False)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
