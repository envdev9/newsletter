"""Pomiary do artykulu #20. Uzycie: python3 -B demo.py [powtorzenia=10]"""
from __future__ import annotations

import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scen   # noqa: E402


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10

    print("== 1. zamrozony (SIGSTOP) wlasciciel miedzy sprawdzeniem a zapisem; B przejmuje; A wznowiony (ttl 0.6 s)")
    for mode in ("unfenced", "checked", "fenced"):
        r = scen.freeze(mode)
        print(f"  {mode:8}: tokeny A/B = {r['A'].get('token')}/{r['B'].get('token')}; A: {r['A']['events']}; "
              f"zapisy przeterminowane = {r['stale']}; log: {r['log']}")

    print("== 2. zamrozony ZYWY wlasciciel: flock vs dzierzawa")
    r = scen.flock_vs_lease_freeze()
    print(f"  flock  : got={r['flock']['got']} po {r['flock']['waited']} s oczekiwania (timeout 2 s)")
    print(f"  dzierz.: B busy={r['lease']['busy']} token={r['lease'].get('token')} czekal {r['lease'].get('waited')} s")

    print("== 3. zywy wlasciciel, dluga praca 2.0 s przy ttl 0.6 s; probe B po 1.5 s")
    for hb in (True, False):
        r = scen.long_work(hb)
        print(f"  heartbeat={hb!s:5}: B busy={r['B']['busy']}; A odnowien={r['A'].get('renewals')}, "
              f"A hb_lost={r['A'].get('hb_lost')}, A events={r['A']['events']}")

    print(f"== 4. czas od SIGKILL do przejecia ({n} prob, ttl 0.6 s)")
    for kind in ("flock", "lease"):
        xs = sorted(scen.takeover_after_kill(kind) for _ in range(n))
        print(f"  {kind:5}: min {xs[0]:.3f} s, mediana {statistics.median(xs):.3f} s, max {xs[-1]:.3f} s")

    print(f"== 5. wyscig 4 procesow o wolna dzierzawe ({n * 2} rund)")
    rs = [scen.race(4) for _ in range(n * 2)]
    print(f"  zwyciezcow na runde: {sorted({r['winners'] for r in rs})}; tokeny zwyciezcow: {sorted({tuple(r['tokens']) for r in rs})}")


if __name__ == "__main__":
    main()
