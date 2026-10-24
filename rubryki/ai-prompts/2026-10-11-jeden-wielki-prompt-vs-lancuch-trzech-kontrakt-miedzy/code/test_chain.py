#!/usr/bin/env python3
"""Porownanie lancucha Z kontraktami i BEZ kontraktow na 7 nagraniach (Python stdlib).

Nagrania w fixtures/ pisal czlowiek (autor) - nie sa outputem modelu. Mierzone jest to,
co deterministyczne: na ktorym etapie lancuch odrzuca, ile wywolan modelu zmarnowano
i czy werdykt zgadza sie z "prawda" (czy zmiana naprawia blad i nie robi nic ponad).
"""
import os
import shutil
import sys

import chain

SCENARIOS = [
    # nazwa, opis, czy zmiana jest naprawde dobra (prawda), oczekiwany etap (kontrakty), baseline zaakceptuje?
    ("s0_good", "poprawny przebieg", True, "-", True),
    ("s1_fenced_json", "tresc dobra, JSON w ``` + prosa", True, "krok 1", True),
    ("s2_halluc_symbol", "krok 1 zmysla InvoiceCalculator.RoundTotal", False, "krok 1", False),
    ("s3_scope_creep", "plan i diff dotykaja Discounts.cs", False, "krok 2", True),
    ("s4_test_tamper", "diff zmienia oczekiwania w Billing.Check", False, "krok 3", True),
    ("s5_bad_context", "diff nie aplikuje sie (zly kontekst)", False, "krok 3", False),
    ("s6_wrong_fix", "poprawny format, zla poprawka (ToPositiveInfinity)", False, "bramka", False),
]


def main() -> int:
    index = chain.build_index()
    bug = open(os.path.join(chain.HERE, "bug_report.txt"), encoding="utf-8").read()
    wd = chain.make_workdir()
    cache: dict[str, tuple[bool, str]] = {}

    def gate(diff, workdir):
        if diff not in cache:
            cache[diff] = chain.final_gate(diff, workdir)
        return cache[diff]

    rows = []
    bad = 0
    try:
        for name, desc, truth, exp_stage, exp_base in SCENARIOS:
            rc = chain.run_chain(chain.ReplayModel(name), True, bug, index, wd, gate)
            rb = chain.run_chain(chain.ReplayModel(name), False, bug, index, wd, gate)
            rows.append((name, desc, truth, rc, rb))
            if rc.stage != exp_stage or rb.accepted != exp_base:
                bad += 1
                print(f"!! {name}: kontrakty stage={rc.stage} acc={rc.accepted}; baseline acc={rb.accepted}")
    finally:
        shutil.rmtree(wd, ignore_errors=True)

    print(f"{'id':<18} {'prawda':<8} {'kontrakty':<22} {'wywolan':<8} {'baseline':<22} opis")
    for name, desc, truth, rc, rb in rows:
        k = "ZIELONE" if rc.accepted else f"odrzucone: {rc.stage}"
        b = "ZIELONE" if rb.accepted else f"odrzucone: {rb.stage}"
        print(f"{name:<18} {'dobra' if truth else 'zla':<8} {k:<22} {rc.calls}/{rb.calls:<6} {b:<22} {desc}")

    def verdict_ok(r, truth):
        return r.accepted == truth

    n = len(rows)
    c_ok = sum(verdict_ok(rc, t) for _, _, t, rc, _ in rows)
    b_ok = sum(verdict_ok(rb, t) for _, _, t, _, rb in rows)
    c_false_green = sum(rc.accepted and not t for _, _, t, rc, _ in rows)
    b_false_green = sum(rb.accepted and not t for _, _, t, _, rb in rows)
    c_false_red = sum((not rc.accepted) and t for _, _, t, rc, _ in rows)
    b_false_red = sum((not rb.accepted) and t for _, _, t, _, rb in rows)
    bad_rows = [r for r in rows if not r[2]]
    c_calls = sum(rc.calls for _, _, _, rc, _ in bad_rows)
    b_calls = sum(rb.calls for _, _, _, _, rb in bad_rows)
    print()
    print(f"zgodnosc werdyktu z prawda: kontrakty {c_ok}/{n}, baseline {b_ok}/{n}")
    print(f"falszywe zielone (zla zmiana przyjeta): kontrakty {c_false_green}, baseline {b_false_green}")
    print(f"falszywe czerwone (dobra zmiana odrzucona): kontrakty {c_false_red}, baseline {b_false_red}")
    print(f"wywolania modelu na {len(bad_rows)} zlych scenariuszach: kontrakty {c_calls}, baseline {b_calls}")
    print(f"niezgodnosci z oczekiwaniem: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
