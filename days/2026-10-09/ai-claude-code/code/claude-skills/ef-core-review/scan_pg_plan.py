#!/usr/bin/env python3
"""scan_pg_plan.py - skaner planow PostgreSQL z EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) (tylko stdlib).

Uzycie:
    python3 scan_pg_plan.py [--budget budgets.json] [--min-rows N] <plan.json | katalog> [...]

Wyjscie: `plik | WARN/INFO | REGULA | opis`. Kod wyjscia 1 = jest WARN albo przekroczony budzet (nadaje sie na bramke w CI).

Reguly:
  SEQ-SCAN      WARN  Seq Scan przegladajacy >= N wierszy (domyslnie 10000), z filtrem odrzucajacym >= 90% z nich
  HASH-SPILL    WARN  wezel Hash z Hash Batches > 1: tablica haszujaca nie zmiescila sie w work_mem, partie ida na dysk
  SORT-SPILL    WARN  Sort Method: external merge/disk - sortowanie na dysku
  TEMP-IO       INFO  Temp Written Blocks > 0 w calym planie (laczny zapis do plikow tymczasowych)
  ESTIMATE-SKEW INFO  Plan Rows vs Actual Rows rozjechane >= 10x (przy >= 1000 wierszach po stronie wiekszej)
Budzet (--budget): {"etykieta": {"max_buffers": 100}} - etykieta = nazwa pliku bez .json. Przekroczenie = BUDGET (WARN).
Plan w pliku to tablica JSON z jednym elementem {"Plan": {...}, "Execution Time": ...} (taki zwraca EXPLAIN FORMAT JSON).
"""
import json
import os
import sys


def walk(node, parent=None):
    yield node, parent
    for kid in node.get("Plans", []):
        yield from walk(kid, node)


def scan_plan(path, min_rows=10000, budgets=None):
    out = []
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    root = doc[0]
    plan = root["Plan"]
    label = os.path.splitext(os.path.basename(path))[0]

    def add(sev, rule, msg):
        out.append((os.path.basename(path), sev, rule, msg))

    for node, _parent in walk(plan):
        typ = node["Node Type"]
        loops = node.get("Actual Loops", 1) or 1
        if typ == "Seq Scan":
            removed = node.get("Rows Removed by Filter", 0)
            actual = node.get("Actual Rows", 0)
            examined = (actual + removed) * loops
            if examined >= min_rows and removed >= 0.9 * (actual + removed) and node.get("Filter"):
                add("WARN", "SEQ-SCAN",
                    f"Seq Scan na {node.get('Relation Name')}: przejrzano {examined} wierszy, filtr zostawil {actual} "
                    f"(odrzucono {100.0 * removed / (actual + removed):.1f}%); filtr: {node['Filter']}")
        if typ == "Hash" and node.get("Hash Batches", 1) > 1:
            add("WARN", "HASH-SPILL",
                f"Hash: {node['Hash Batches']} partii (Original: {node.get('Original Hash Batches')}), "
                f"pamiec {node.get('Peak Memory Usage')} kB - tablica haszujaca poza work_mem, partie na dysku")
        if typ == "Sort" and "external" in str(node.get("Sort Method", "")):
            add("WARN", "SORT-SPILL",
                f"Sort: {node['Sort Method']}, {node.get('Sort Space Used')} kB na dysku (klucz: {node.get('Sort Key')})")
        plan_rows, act_rows = node.get("Plan Rows", 0), node.get("Actual Rows", 0) * loops
        big, small = max(plan_rows, act_rows), max(1, min(plan_rows, act_rows))
        if big >= 1000 and big / small >= 10:
            add("INFO", "ESTIMATE-SKEW", f"{typ}: estymata {plan_rows}, rzeczywiste {act_rows} wierszy ({big / small:.0f}x)")

    temp = plan.get("Temp Written Blocks", 0)
    if temp:
        add("INFO", "TEMP-IO", f"Temp Written Blocks = {temp} (zapis do plikow tymczasowych)")

    buffers = plan.get("Shared Hit Blocks", 0) + plan.get("Shared Read Blocks", 0)
    if budgets and label in budgets:
        limit = budgets[label].get("max_buffers")
        if limit is not None and buffers > limit:
            add("WARN", "BUDGET", f"{buffers} buforow wspoldzielonych > budzet {limit}")
    return out, buffers


def collect(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += [os.path.join(p, n) for n in sorted(os.listdir(p)) if n.endswith(".json")]
        elif os.path.isfile(p):
            files.append(p)
    return files


def main(argv):
    budgets, min_rows, paths = None, 10000, []
    i = 0
    while i < len(argv):
        if argv[i] == "--budget":
            with open(argv[i + 1], encoding="utf-8") as fh:
                budgets = json.load(fh)
            i += 2
        elif argv[i] == "--min-rows":
            min_rows = int(argv[i + 1])
            i += 2
        else:
            paths.append(argv[i])
            i += 1
    if not paths:
        print(__doc__)
        return 2
    n_warn = n_all = 0
    for f in collect(paths):
        findings, buffers = scan_plan(f, min_rows, budgets)
        if not findings:
            print(f"{os.path.basename(f)} | OK | - | {buffers} buforow, bez uwag")
        for name, sev, rule, msg in findings:
            print(f"{name} | {sev} | {rule} | {msg}")
            n_all += 1
            n_warn += sev == "WARN"
    print(f"scan_pg_plan: {n_all} znalezisk ({n_warn} WARN)", file=sys.stderr)
    return 1 if n_warn else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
