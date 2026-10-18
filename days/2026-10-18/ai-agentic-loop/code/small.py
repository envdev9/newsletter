"""Dwa male skrypty pomocnicze (wybierane pierwszym argumentem):

  acq     --dir D --name N --start-at T   : jedna proba try_acquire w zsynchronizowanej chwili; wypisuje token albo null
  flockhold --file F                      : zdobywa flock(LOCK_EX) na F, tworzy F.ready i spi (baza porownawcza z #19)
  flocktry  --file F --timeout S          : probuje flock przez S sekund; wypisuje {"got": bool, "waited": s}
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lease import LeaseStore   # noqa: E402


def main() -> int:
    cmd = sys.argv[1]
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir")
    ap.add_argument("--name")
    ap.add_argument("--start-at", type=float, default=0.0)
    ap.add_argument("--ttl", type=float, default=0.6)
    ap.add_argument("--file")
    ap.add_argument("--timeout", type=float, default=2.0)
    a = ap.parse_args(sys.argv[2:])
    if cmd == "acq":
        store = LeaseStore(os.path.join(a.dir, "lease.json"), a.ttl)
        while a.start_at and time.time() < a.start_at:
            pass
        lease = store.try_acquire(a.name)
        print(json.dumps({"name": a.name, "token": lease.token if lease else None}))
    elif cmd == "flockhold":
        fd = os.open(a.file, os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        open(a.file + ".ready", "w").close()
        time.sleep(3600)
    elif cmd == "flocktry":
        fd = os.open(a.file, os.O_RDWR | os.O_CREAT, 0o600)
        t0 = time.monotonic()
        got = False
        while time.monotonic() - t0 < a.timeout:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                got = True
                break
            except OSError:
                time.sleep(0.01)
        print(json.dumps({"got": got, "waited": round(time.monotonic() - t0, 3)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
