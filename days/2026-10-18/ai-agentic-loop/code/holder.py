"""Proces-pracownik: bierze dzierzawe i wykonuje `--items` krokow, kazdy = sprawdzenie, "praca", zapis.

python3 holder.py --dir D --name A --mode unfenced|checked|fenced [--items 3] [--step 0.4] [--ttl 0.6]
                  [--no-heartbeat] [--acquire-timeout 5] [--hold-forever]
 unfenced - nic nie sprawdza, pisze zwyklym append
 checked  - przed krokiem pyta store.is_valid (check-then-act), pisze zwyklym append
 fenced   - j.w. + zasob odrzuca zapis ze starym tokenem (FencedLog)
Przed "praca" tworzy znacznik D/<name>.ready.<i>; harness uzywa go, by zamrozic proces (SIGSTOP) dokladnie
miedzy sprawdzeniem a zapisem. Wypisuje jedna linie JSON. Kod 75 gdy nie dostal dzierzawy.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lease import FencedLog, Heartbeat, LeaseStore, StaleToken   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--mode", default="fenced")
    ap.add_argument("--items", type=int, default=3)
    ap.add_argument("--step", type=float, default=0.4)
    ap.add_argument("--ttl", type=float, default=0.6)
    ap.add_argument("--no-heartbeat", action="store_true")
    ap.add_argument("--acquire-timeout", type=float, default=5.0)
    ap.add_argument("--hold-forever", action="store_true", help="po zdobyciu dzierzawy spij (do testu SIGKILL)")
    a = ap.parse_args()

    store = LeaseStore(os.path.join(a.dir, "lease.json"), a.ttl)
    log = FencedLog(os.path.join(a.dir, "work.log"))
    t0 = time.monotonic()
    lease = store.acquire_wait(a.name, a.acquire_timeout)
    if lease is None:
        print(json.dumps({"name": a.name, "busy": True, "peek": store.peek()}))
        return 75
    got = round(time.monotonic() - t0, 3)
    open(os.path.join(a.dir, f"{a.name}.acquired"), "w").close()
    hb = None if a.no_heartbeat else Heartbeat(store, lease).start()
    events = []
    if a.hold_forever:
        time.sleep(3600)
    for i in range(a.items):
        if a.mode != "unfenced" and not store.is_valid(a.name, lease.token):
            events.append(f"stop:lease-lost-before-{i}")
            break
        open(os.path.join(a.dir, f"{a.name}.ready.{i}"), "w").close()
        time.sleep(a.step)                                       # "wywolanie LLM / budowanie"
        line = f"{a.name} token={lease.token} item={i}"
        try:
            if a.mode == "fenced":
                log.append(lease.token, line)
            else:
                log.append_unfenced(line)
            events.append(f"wrote:{i}")
        except StaleToken as e:
            events.append(f"REJECTED:{i}:{e}")
            break
    if hb:
        hb.stop()
    store.release(a.name, lease.token)
    print(json.dumps({"name": a.name, "busy": False, "token": lease.token, "waited": got, "events": events,
                      "hb_lost": bool(hb and hb.lost.is_set()), "renewals": hb.renewals if hb else None}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
