#!/usr/bin/env python3
"""Testy skanera `scan_plan.py` na REALNYCH planach Showplan XML (code/samples/*.xml) z zywego
SQL Server 2022 (Docker) - nie na recznie pisanych fixturach.

Wydanie #13: 5 planow z #10 (regresja) + 9 nowych (SPILL, MEMORY-GRANT, NO-JOIN-PREDICATE,
NO-STATISTICS i jego slepe plamki). Dodatkowo asercje licznosci (SPILL dokladnie raz na operator).
Nie wymaga SQL Servera - probki to pliki XML.

Uzycie:  python3 run_tests.py
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
SCANNER = HERE / "claude-skills" / "sql-plan-review" / "scan_plan.py"
SAMPLES = HERE / "samples"

CASES = {
    # --- regresja z wydania #10 ---
    "missing_index_trivial.xml": {"SCAN"},
    "missing_index_full.xml": {"SCAN", "MISSING-INDEX"},
    # keylookup: w #10 test oczekiwal tez ESTIMATE-SKEW - to byl falszywy alarm (est. na wykonanie
    # vs actual sumaryczny po 10 wykonaniach); po poprawce #13 zostaje sam KEY-LOOKUP.
    "keylookup.xml": {"KEY-LOOKUP"},
    "implicit_convert_bad.xml": {"SCAN", "IMPLICIT-CONVERT"},
    "implicit_convert_good.xml": set(),
    # --- nowe w #13 ---
    # zmienna tabelowa (est. 1 wiersz, rzecz. 500 000) -> Sort z grantem "na 1 wiersz" -> spill
    "spill.xml": {"SPILL", "ESTIMATE-SKEW", "SCAN"},
    # varchar(4000) z krotkimi wartosciami -> grant 268 MB, uzyte 5 MB
    "memory_grant.xml": {"SCAN", "MEMORY-GRANT"},
    # cross join bez predykatu -> <Warnings NoJoinPredicate="1">
    "no_join_predicate.xml": {"NO-JOIN-PREDICATE", "SCAN"},
    # kolumna bez statystyk: GROUP BY / ORDER BY / klucz joina -> ColumnsWithNoStatistics
    "no_statistics_groupby.xml": {"SCAN", "NO-STATISTICS"},
    "no_statistics_orderby.xml": {"SCAN", "NO-STATISTICS", "MISSING-INDEX"},
    "no_statistics_joinkey.xml": {"SCAN", "NO-STATISTICS"},
    # SLEPE PLAMKI (realne plany BEZ ostrzezenia, mimo ze kolumna nie ma statystyk):
    "no_statistics_trivial.xml": {"SCAN"},            # plan TRIVIAL - brak ostrzezenia
    "no_statistics.xml": {"SCAN", "MISSING-INDEX"},   # WHERE Category = 7 w joinie - brak ostrzezenia
}

# dokladna liczba wystapien reguly w pliku (lapie duplikaty, np. podwojny SPILL)
COUNTS = {
    ("spill.xml", "SPILL"): 1,
    ("no_join_predicate.xml", "NO-JOIN-PREDICATE"): 1,
}

LINE_RE = re.compile(r"\|\s*(?:WARN|INFO)\s*\|\s*([A-Z-]+)\s*\|")


def scan_lines(xml_path: Path):
    proc = subprocess.run([sys.executable, str(SCANNER), str(xml_path)], capture_output=True, text=True)
    return [m.group(1) for line in proc.stdout.splitlines() for m in [LINE_RE.search(line)] if m]


def main() -> int:
    ok_count = 0
    total = len(CASES) + len(COUNTS)
    for name, expected in CASES.items():
        path = SAMPLES / name
        if not path.exists():
            print("BRAK  %-30s plik nie istnieje" % name)
            continue
        actual = set(scan_lines(path))
        ok = actual == expected
        ok_count += ok
        print("%s  %-30s oczekiwano: %-42s otrzymano: %s" % (
            "OK  " if ok else "FAIL", name, ", ".join(sorted(expected)) or "-", ", ".join(sorted(actual)) or "-"))
    for (name, rule), want in COUNTS.items():
        got = scan_lines(SAMPLES / name).count(rule)
        ok = got == want
        ok_count += ok
        print("%s  %-30s liczba %-18s oczekiwano: %d  otrzymano: %d" % ("OK  " if ok else "FAIL", name, rule, want, got))
    print()
    print("WYNIK: %d/%d sprawdzen zgodnych (realne plany z SQL Server 2022, Docker)" % (ok_count, total))
    return 0 if ok_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
