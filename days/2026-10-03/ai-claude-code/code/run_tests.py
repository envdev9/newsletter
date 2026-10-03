#!/usr/bin/env python3
"""Testy skanera `scan_plan.py` na REALNYCH planach Showplan XML (code/samples/*.xml),
zarejestrowanych z zywego SQL Server 2022 (Docker) - nie na recznie napisanych fixturach.

Dla kazdej probki porownuje zbior regul (WARN/INFO <REGULA>), jakie scan_plan.py faktycznie
zwraca, z zestawem oczekiwanym (ustalonym na podstawie realnego uruchomienia - patrz
code/README.md). Nie wymaga SQL Servera/Dockera do odpalenia - probki juz sa plikami XML.

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
    # trywialny plan (StatementOptmLevel=TRIVIAL) -> optymalizator NIE sugeruje indeksu,
    # mimo ze Clustered Index Scan na 50000 wierszach jest realnym problemem (SCAN leci).
    "missing_index_trivial.xml": {"SCAN"},
    # ten sam predykat + ORDER BY -> FULL optimization -> MissingIndexGroup sie pojawia.
    "missing_index_full.xml": {"SCAN", "MISSING-INDEX"},
    # indeks na CustomerId bez INCLUDE -> Key Lookup (realnie: IndexScan@Lookup="1" na
    # operatorze z PhysicalOp="Clustered Index Seek", nie z literalnym LogicalOp="Key Lookup").
    "keylookup.xml": {"KEY-LOOKUP", "ESTIMATE-SKEW"},
    # EF Core/ADO.NET default: string parametr jako NVARCHAR, kolumna VARCHAR -> PlanAffectingConvert,
    # indeks na OrderStatus zignorowany, Index Scan zamiast Seek.
    "implicit_convert_bad.xml": {"SCAN", "IMPLICIT-CONVERT"},
    # ten sam predykat, parametr VARCHAR (typ zgodny z kolumna) -> czysty Index Seek, cisza.
    "implicit_convert_good.xml": set(),
}

RULE_RE = re.compile(r"\|\s*(?:WARN|INFO)\s*\|\s*([A-Z-]+)\s*\|")


def rules_found(xml_path: Path) -> set:
    proc = subprocess.run(
        [sys.executable, str(SCANNER), str(xml_path)],
        capture_output=True, text=True,
    )
    return {m.group(1) for line in proc.stdout.splitlines() for m in [RULE_RE.search(line)] if m}


def main() -> int:
    total = len(CASES)
    passed = 0
    for name, expected in CASES.items():
        path = SAMPLES / name
        if not path.exists():
            print("BRAK  %-28s plik nie istnieje: %s" % (name, path))
            continue
        actual = rules_found(path)
        ok = actual == expected
        passed += ok
        status = "OK  " if ok else "FAIL"
        print("%s  %-28s oczekiwano: %-40s otrzymano: %s" % (
            status, name, ", ".join(sorted(expected)) or "-", ", ".join(sorted(actual)) or "-"))
    print()
    print("WYNIK: %d/%d przypadkow zgodnych (realne plany z SQL Server 2022, Docker)" % (passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
