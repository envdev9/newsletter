#!/usr/bin/env python3
"""Testy skanerow SQL: 'zle' probki musza dac konkretne reguly, 'dobre' - zero WARN/INFO."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, "claude-skills", "sql-plan-review")
SMP = os.path.join(HERE, "samples")

CASES = [
    # (skaner, plik, oczekiwany exit, reguly ktore MUSZA wystapic, reguly ktorych NIE MOZE byc)
    ("scan_sql.py", "bad_orders.sql", 1,
     {"FK-NO-INDEX", "SELECT-STAR", "NOLOCK", "NON-SARGABLE", "LEADING-WILDCARD", "NOT-IN-SUBQUERY", "N-LITERAL", "TOP-NO-ORDER"}, set()),
    ("scan_sql.py", "good_orders.sql", 0, set(), {"FK-NO-INDEX", "SELECT-STAR", "NOLOCK", "NON-SARGABLE",
                                                   "LEADING-WILDCARD", "NOT-IN-SUBQUERY", "N-LITERAL", "TOP-NO-ORDER"}),
    ("scan_plan.py", "bad_plan.sqlplan", 1,
     {"MISSING-INDEX", "NO-JOIN-PREDICATE", "ESTIMATE-SKEW", "SCAN", "KEY-LOOKUP", "SPILL", "NO-STATISTICS", "IMPLICIT-CONVERT", "MEMORY-GRANT"}, set()),
    ("scan_plan.py", "good_plan.sqlplan", 0, set(), {"MISSING-INDEX", "SCAN", "KEY-LOOKUP", "SPILL", "ESTIMATE-SKEW", "IMPLICIT-CONVERT"}),
]


def rules_of(out):
    r = set()
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(" | ")]
        # sql: plik:linia | LEVEL | RULE | msg    plan: plik | stmt | LEVEL | RULE | msg
        if len(parts) >= 4:
            r.add(parts[2] if parts[1] in ("WARN", "INFO") else parts[3])
    return r


def main():
    fails = 0
    for scanner, fname, want_exit, must, mustnot in CASES:
        p = subprocess.run([sys.executable, os.path.join(SK, scanner), os.path.join(SMP, fname)],
                           capture_output=True, text=True)
        got = rules_of(p.stdout)
        problems = []
        if p.returncode != want_exit:
            problems.append("exit=%d, oczekiwano %d" % (p.returncode, want_exit))
        if must - got:
            problems.append("brakuje regul: %s" % sorted(must - got))
        if mustnot & got:
            problems.append("niechciane reguly: %s" % sorted(mustnot & got))
        print("%s  %-14s %-20s reguly: %s" % ("OK  " if not problems else "FAIL", scanner, fname, ", ".join(sorted(got)) or "-"))
        for pr in problems:
            print("       ->", pr)
        fails += bool(problems)
    print("\nWYNIK: %d/%d przypadkow zgodnych" % (len(CASES) - fails, len(CASES)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
