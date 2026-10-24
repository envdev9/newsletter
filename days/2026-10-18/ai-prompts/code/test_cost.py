#!/usr/bin/env python3
"""Sprawdza niezmienniki modelu kosztu (stdlib, bez dotnet). Exit 1 przy naruszeniu."""
import os
import shutil
import sys

import chain
import cost

EXPECTED_STAGE = {"s0_good": "bramka", "s1_fenced_json": "krok 1", "s2_halluc_symbol": "krok 1",
                  "s3_scope_creep": "krok 2", "s4_test_tamper": "krok 3", "s5_bad_context": "krok 3",
                  "s6_wrong_fix": "bramka"}   # "bramka" = doszedl do bramki (gate jest stubem)


def main() -> int:
    index = chain.build_index()
    bug = open(os.path.join(chain.HERE, "bug_report.txt"), encoding="utf-8").read()
    wd = chain.make_workdir()
    bad = []
    try:
        for s, exp in EXPECTED_STAGE.items():
            rc, resc = cost.run(s, True, bug, index, wd)
            rb, resb = cost.run(s, False, bug, index, wd)
            if resc.stage != exp:
                bad.append(f"{s}: etap {resc.stage!r}, oczekiwano {exp!r}")
            if cost.cost(rc.calls)[2] > cost.cost(rb.calls)[2]:
                bad.append(f"{s}: kontrakty drozsze niz baseline")
            if (cost.repair_cost(rc, resc) is None) != (resc.stage in ("bramka", "-")):
                bad.append(f"{s}: repair_cost niespojne z etapem")
        if cost.tok("a" * 9, 4) != 3 or cost.tok("", 4) != 0:
            bad.append("tok: ceil(znaki/k)")
    finally:
        shutil.rmtree(wd, ignore_errors=True)
    for b in bad:
        print("!!", b)
    print("OK: 7 scenariuszy, niezmienniki spelnione" if not bad else f"BLEDY: {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
