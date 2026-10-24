#!/usr/bin/env python3
"""Testy scan_signals.py: plik 'bad' musi dac konkretne reguly, 'good' - zero uwag."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, "claude-skills", "angular-signals-review")
SMP = os.path.join(HERE, "samples")

CASES = [
    # (plik, oczekiwany exit, reguly ktore MUSZA wystapic, reguly ktorych NIE MOZE byc)
    ("bad.component.ts", 1,
     {"ONPUSH-MISSING", "EFFECT-STATE-SYNC", "EFFECT-SELF-WRITE", "UNTRACKED-CANDIDATE",
      "COMPUTED-SIDE-EFFECT", "MUTATING-UPDATE"}, set()),
    ("good.component.ts", 0, set(),
     {"ONPUSH-MISSING", "EFFECT-STATE-SYNC", "EFFECT-SELF-WRITE", "UNTRACKED-CANDIDATE",
      "COMPUTED-SIDE-EFFECT", "MUTATING-UPDATE"}),
]


def rules_of(out):
    r = set()
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(" | ")]
        # "plik:linia | LEVEL | RULE | msg"
        if len(parts) >= 4 and parts[1] in ("WARN", "INFO"):
            r.add(parts[2])
    return r


def main():
    fails = 0
    for fname, want_exit, must, mustnot in CASES:
        p = subprocess.run(
            [sys.executable, os.path.join(SK, "scan_signals.py"), os.path.join(SMP, fname)],
            capture_output=True, text=True,
        )
        got = rules_of(p.stdout)
        problems = []
        if p.returncode != want_exit:
            problems.append("exit=%d, oczekiwano %d" % (p.returncode, want_exit))
        if must - got:
            problems.append("brakuje regul: %s" % sorted(must - got))
        if mustnot & got:
            problems.append("niechciane reguly: %s" % sorted(mustnot & got))
        print("%s  %-20s reguly: %s" % ("OK  " if not problems else "FAIL", fname, ", ".join(sorted(got)) or "-"))
        for pr in problems:
            print("       ->", pr)
        fails += bool(problems)
    print("\nWYNIK: %d/%d przypadkow zgodnych" % (len(CASES) - fails, len(CASES)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
