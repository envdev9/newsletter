"""Proces-"agent" (rola modelu: sleep). Bierze dzierzawe, pisze barierke z tokenem, wznawia z dziennika.

Tryby (--mode):
  blind   - najpierw SKUTEK (wiersz w effects.log), potem rekord w dzienniku. Bez zadnego sprawdzania.
  intent  - najpierw rekord w dzienniku, potem odczyt+fold(fence) i sprawdzenie, czy rekord zostal przyjety;
            dopiero potem (po --pause s) skutek. Przyjmuje semantyke "co najwyzej raz".
Wszystko co istotne laduje w katalogu --dir: journal.jsonl, lease.json, effects.log, events.log.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

from lease import Heartbeat, LeaseStore
from wal import Journal, fold


def line(path: str, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, (text + "\n").encode())
    finally:
        os.close(fd)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--mode", choices=["blind", "intent"], default="blind")
    ap.add_argument("--steps", type=int, default=6)
    ap.add_argument("--think", type=float, default=0.3)
    ap.add_argument("--pause", type=float, default=0.0)
    ap.add_argument("--ttl", type=float, default=0.6)
    a = ap.parse_args()

    ev = lambda t: line(os.path.join(a.dir, "events.log"), f"{a.name} {t}")
    store = LeaseStore(os.path.join(a.dir, "lease.json"), a.ttl)
    lease = store.acquire_wait(a.name, timeout=15)
    if lease is None:
        ev("no-lease")
        return 3
    hb = Heartbeat(store, lease).start()
    tok = lease.token
    j = Journal(os.path.join(a.dir, "journal.jsonl"))
    j.append({"op": "barrier", "tok": tok, "who": a.name, "id": f"{a.name}-{tok}-barrier"})
    ev(f"barrier tok={tok}")

    st = fold(j.read()[0])                     # stan widziany PO barierze
    todo = [s for s in range(a.steps) if s not in st.steps]
    ev(f"todo={todo}")
    for s in todo:
        ev(f"pre:{s}")
        time.sleep(a.think)
        rid = f"{a.name}-{tok}-{s}"
        rec = {"op": "step", "step": s, "tok": tok, "who": a.name, "id": rid}
        if a.mode == "blind":
            line(os.path.join(a.dir, "effects.log"), f"{a.name} tok={tok} step={s}")
            j.append(rec)
            ev(f"recorded:{s}")
        else:
            j.append(rec)
            if rid in fold(j.read()[0]).dropped:
                ev(f"rejected:{s}")
                hb.stop()
                return 0
            ev(f"checked:{s}")
            time.sleep(a.pause)                # okno: miedzy sprawdzeniem a skutkiem
            line(os.path.join(a.dir, "effects.log"), f"{a.name} tok={tok} step={s}")
    j.append({"op": "done", "tok": tok, "who": a.name, "id": f"{a.name}-{tok}-done"})
    ev("done")
    hb.stop()
    store.release(a.name, tok)
    return 0


if __name__ == "__main__":
    sys.exit(main())
