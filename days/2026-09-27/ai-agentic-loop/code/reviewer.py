#!/usr/bin/env python3
"""SKRYPTOWY zastepnik subagenta-reviewera (NIE model). Jedna 'rola' = jeden zestaw regul regex.

Kontrakt wyjscia (jak 'jedna linia na znalezisko' z artykulu #3), tu jako JSON Lines:
  {"file":..., "line":..., "severity":"high|medium|low", "category":..., "msg":..., "role":...}
Uzycie: python3 reviewer.py --role security [--delay 0.5] plik.cs ...
Rola 'crash' celowo pada (exit 3) - do testu obslugi awarii jednego z rownoleglych workerow.
"""
import argparse
import json
import re
import sys
import time

RULES = {
    "security": [
        (r'"\s*SELECT[^"]*"\s*\+|\+\s*"[^"]*\'"', "high", "sql-injection",
         "SQL sklejany konkatenacja - uzyj parametrow (SqlParameter / Dapper)"),
        (r'(?i)\b(password|secret|apikey)\w*\s*=\s*"[^"]+"', "high", "hardcoded-secret",
         "sekret w kodzie - przenies do konfiguracji/secret store"),
    ],
    "concurrency": [
        (r'\.Result\b', "high", "sync-over-async", "blokujace .Result - await zamiast tego"),
        (r'\.Wait\(\)', "high", "sync-over-async", "blokujace .Wait() - await zamiast tego"),
        (r'\basync\s+void\b', "medium", "async-void", "async void polyka wyjatki - zwroc Task"),
    ],
    "perf": [
        (r'\.Count\(\)\s*>\s*0', "low", "count-vs-any", "Count() > 0 - uzyj Any()"),
        (r'\.Result\b', "medium", "sync-over-async", "blokujace .Result wstrzymuje watek z puli"),
    ],
    "style": [
        (r'catch\s*\(Exception\)\s*\{\s*\}', "medium", "empty-catch", "pusty catch polyka bledy"),
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", required=True)
    ap.add_argument("--delay", type=float, default=0.0, help="symulacja czasu 'myslenia' modelu")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    if a.role == "crash":
        print("reviewer[crash]: symulowana awaria", file=sys.stderr)
        return 3
    if a.role not in RULES:
        print(f"nieznana rola: {a.role}", file=sys.stderr)
        return 2
    time.sleep(a.delay)
    for f in a.files:
        with open(f, encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                for rx, sev, cat, msg in RULES[a.role]:
                    if re.search(rx, line):
                        print(json.dumps({"file": f, "line": n, "severity": sev,
                                          "category": cat, "msg": msg, "role": a.role}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
