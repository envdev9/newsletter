#!/usr/bin/env python3
"""Testy skilla ef-core-review v3 (#16): PostgreSQL - skaner kodu (dialekt Npgsql), skaner planow EXPLAIN JSON, bramka budzetowa, hook.

Uruchomienie z katalogu code/:   python3 run_tests.py
Tylko stdlib. Nie wymaga .NET ani PostgreSQL: plany w samples/ zostaly nagrane przez PgPlanCaptureInterceptor z prawdziwego
PostgreSQL 16.14 (patrz README). Oczekiwania dla planow ustalono PO obejrzeniu wynikow - to test regresji, nie dowod poprawnosci progow.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "claude-skills", "ef-core-review")
sys.path.insert(0, SKILL)
import scan_ef  # noqa: E402
import scan_pg_plan  # noqa: E402

HOOK = os.path.join(HERE, "claude-hooks", "ef-post-edit.py")
DEMO = os.path.join(HERE, "pg-plan-demo")
SAMPLES = os.path.join(HERE, "samples")
results = []


def check(name, expected, actual):
    ok = expected == actual
    results.append(ok)
    print(f"{'OK  ' if ok else 'FAIL'}  {name:<66} oczekiwano: {expected}  otrzymano: {actual}")


def rules(findings):
    out = {}
    for f in findings:
        out[f[3]] = out.get(f[3], 0) + 1
    return dict(sorted(out.items()))


def scan_files(files):
    """files: {nazwa: tresc}; skanuje wszystkie w katalogu tymczasowym."""
    d = tempfile.mkdtemp(prefix="efscan-")
    try:
        paths = []
        for name, body in files.items():
            p = os.path.join(d, name)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body)
            paths.append(p)
        return scan_ef.scan_paths(paths)
    finally:
        shutil.rmtree(d, ignore_errors=True)


ENTITY = """using Microsoft.EntityFrameworkCore;
public class Cust { public int Id { get; set; } public string Email { get; set; } = ""; }
public class Ctx : DbContext {
    public DbSet<Cust> Customers => Set<Cust>();
    protected override void OnConfiguring(DbContextOptionsBuilder o) => o.%PROVIDER%;
    protected override void OnModelCreating(ModelBuilder b) { b.Entity<Cust>().HasIndex(c => c.Email); %EXTRA% }
}
"""


def model(provider, extra=""):
    return ENTITY.replace("%PROVIDER%", provider).replace("%EXTRA%", extra)


def q(body):
    return "using System.Linq; using Microsoft.EntityFrameworkCore;\nclass R { void M(Ctx db, List<int> ids, string t) {\n" + body + "\n} }\n"


PG = 'UseNpgsql("x")'
MS = 'UseSqlServer("x")'

# ------------------------------------------------------------------ 1. skaner kodu: dialekty
print("== 1. scan_ef v3: dialekt PostgreSQL (Npgsql) vs SQL Server ==")
sw = q("var a = db.Customers.Where(c => c.Email.StartsWith(t)).ToList();")
contains = q("var a = db.Customers.Where(c => c.Email.Contains(t)).ToList();")
inlist = q("var a = db.Customers.Where(c => ids.Contains(c.Id)).ToList();")
ilike = q('var a = db.Customers.Where(c => EF.Functions.ILike(c.Email, "%x%")).ToList();')

check("Npgsql + StartsWith, brak pattern_ops -> PG-STARTSWITH-OPCLASS", {"NO-ASNOTRACKING": 1, "PG-STARTSWITH-OPCLASS": 1},
      rules(scan_files({"m.cs": model(PG), "q.cs": sw})))
check("Npgsql + StartsWith + varchar_pattern_ops w modelu -> cisza (poza ASNOTRACKING)", {"NO-ASNOTRACKING": 1},
      rules(scan_files({"m.cs": model(PG, 'b.Entity<Cust>().HasIndex(c => c.Email).HasOperators("varchar_pattern_ops");'), "q.cs": sw})))
check("Npgsql + StartsWith + UseCollation(\"C\") -> cisza (poza ASNOTRACKING)", {"NO-ASNOTRACKING": 1},
      rules(scan_files({"m.cs": model(PG, 'b.Entity<Cust>().Property(c => c.Email).UseCollation("C");'), "q.cs": sw})))
check("SQL Server + StartsWith -> bez PG-STARTSWITH-OPCLASS (STRING-UNICODE: model bez varchar)",
      {"NO-ASNOTRACKING": 1, "STRING-UNICODE": 1}, rules(scan_files({"m.cs": model(MS), "q.cs": sw})))
check("Npgsql + Contains -> LIKE-LEADING-WILDCARD", {"LIKE-LEADING-WILDCARD": 1, "NO-ASNOTRACKING": 1},
      rules(scan_files({"m.cs": model(PG), "q.cs": contains})))
check("Npgsql + EF.Functions.ILike(x, \"%..\") -> LIKE-LEADING-WILDCARD", {"LIKE-LEADING-WILDCARD": 1, "NO-ASNOTRACKING": 1},
      rules(scan_files({"m.cs": model(PG), "q.cs": ilike})))
check("Npgsql + ids.Contains -> bez CONTAINS-LIST (tablica = 1 plan)", {"NO-ASNOTRACKING": 1}, rules(scan_files({"m.cs": model(PG), "q.cs": inlist})))
check("SQL Server + ids.Contains -> CONTAINS-LIST (bez zmian wzgledem #15)",
      {"CONTAINS-LIST": 1, "NO-ASNOTRACKING": 1, "STRING-UNICODE": 1},
      rules(scan_files({"m.cs": model(MS), "q.cs": inlist})))
check("Npgsql: STRING-UNICODE nie dotyczy (brak nvarchar)", {}, rules(scan_files({"m.cs": model(PG)})))
check("SQL Server: STRING-UNICODE nadal dziala", {"STRING-UNICODE": 1}, rules(scan_files({"m.cs": model(MS)})))
mode_const = model('UseNpgsql("x", o => o.UseParameterizedCollectionMode(ParameterTranslationMode.Constant))')
check("Npgsql + ParameterTranslationMode.Constant -> CONTAINS-CONSTANT", {"CONTAINS-CONSTANT": 1}, rules(scan_files({"m.cs": mode_const})))
msg_pg = [f[4] for f in scan_files({"m.cs": model(PG), "q.cs": contains}) if f[3] == "LIKE-LEADING-WILDCARD"][0]
msg_ms = [f[4] for f in scan_files({"m.cs": model(MS), "q.cs": contains}) if f[3] == "LIKE-LEADING-WILDCARD"][0]
check("komunikat PG wspomina gin_trgm_ops, komunikat SQL Server - nie", (True, False), ("gin_trgm_ops" in msg_pg, "gin_trgm_ops" in msg_ms))
check("ignore: // ef-review: ignore PG-STARTSWITH-OPCLASS", {"NO-ASNOTRACKING": 1},
      rules(scan_files({"m.cs": model(PG), "q.cs": q("// ef-review: ignore PG-STARTSWITH-OPCLASS\nvar a = db.Customers.Where(c => c.Email.StartsWith(t)).ToList();")})))

# ------------------------------------------------------------------ 2. kod pg-plan-demo
print("\n== 2. scan_ef na kodzie pg-plan-demo (zapytania mierzone na PostgreSQL) ==")
check("Queries.cs", {"LIKE-LEADING-WILDCARD": 2}, rules(scan_ef.scan_paths([os.path.join(DEMO, "Queries.cs")])))
check("Program.cs (tryb Constant porownywany celowo)", {"CONTAINS-CONSTANT": 1}, rules(scan_ef.scan_paths([os.path.join(DEMO, "Program.cs")])))
check("ShopContext.cs / interceptor (cisza)", {}, rules(scan_ef.scan_paths([os.path.join(DEMO, "ShopContext.cs"),
                                                                           os.path.join(DEMO, "PgPlanCaptureInterceptor.cs")])))

# ------------------------------------------------------------------ 3. plany z prawdziwego PostgreSQL
print("\n== 3. scan_pg_plan na 16 realnych planach EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) z PostgreSQL 16.14 ==")
EXPECT = {
    "btree_eq": {}, "btree_startswith": {"SEQ-SCAN": 1}, "btree_contains": {"SEQ-SCAN": 1}, "btree_endswith": {},
    "btree_pattern_ops_eq": {}, "btree_pattern_ops_startswith": {}, "btree_pattern_ops_contains": {"SEQ-SCAN": 1},
    "btree_pattern_ops_endswith": {},
    "gin_trgm_eq": {}, "gin_trgm_startswith": {}, "gin_trgm_contains": {}, "gin_trgm_endswith": {},
    "normal_hashjoin": {"HASH-SPILL": 1, "TEMP-IO": 1}, "normal_sort": {"SORT-SPILL": 1, "TEMP-IO": 1},
    "lowmem_hashjoin": {"HASH-SPILL": 1, "TEMP-IO": 1}, "lowmem_sort": {"SORT-SPILL": 1, "TEMP-IO": 1},
}
for label, exp in EXPECT.items():
    found, _ = scan_pg_plan.scan_plan(os.path.join(SAMPLES, label + ".json"))
    got = {}
    for _n, _s, rule, _m in found:
        got[rule] = got.get(rule, 0) + 1
    check(label, exp, dict(sorted(got.items())))
check("liczba planow w samples/", 16, len([n for n in os.listdir(SAMPLES) if n.endswith(".json")]))

# EndsWith('@corp.example') zwraca 25% tabeli: Seq Scan jest tam rozsadny, skaner (prog 90% odrzuconych) milczy
f, buffers = scan_pg_plan.scan_plan(os.path.join(SAMPLES, "btree_endswith.json"))
check("btree_endswith: Seq Scan, ale 75% wierszy pasuje -> bez SEQ-SCAN", ([], 1696), (f, buffers))

# ------------------------------------------------------------------ 4. bramka budzetowa (CI)
print("\n== 4. Bramka budzetowa: --budget budgets.json (exit code jak w CI) ==")
BUDGET = os.path.join(HERE, "budgets.json")


def run_gate(*files):
    cmd = [sys.executable, os.path.join(SKILL, "scan_pg_plan.py"), "--budget", BUDGET] + [os.path.join(SAMPLES, x) for x in files]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout


code, out = run_gate("gin_trgm_contains.json", "btree_eq.json")
check("plany w budzecie -> exit 0", 0, code)
code, out = run_gate("btree_contains.json")
check("btree_contains: 1696 > budzet 100 -> exit 1 i regula BUDGET", (1, True), (code, "| BUDGET |" in out))
code, out = run_gate("btree_pattern_ops_startswith.json")
check("btree_pattern_ops_startswith: 4 buforow <= budzet -> exit 0", 0, code)

# plan recznie zlozony (NIE z bazy) - tylko do reguly ESTIMATE-SKEW, ktorej nie wywolano na prawdziwych danych
skew = [{"Plan": {"Node Type": "Index Scan", "Relation Name": "t", "Plan Rows": 1, "Actual Rows": 5000, "Actual Loops": 1,
                  "Shared Hit Blocks": 10}, "Execution Time": 1.0}]
d = tempfile.mkdtemp(prefix="pgplan-")
try:
    p = os.path.join(d, "skew.json")
    with open(p, "w") as fh:
        json.dump(skew, fh)
    f, _ = scan_pg_plan.scan_plan(p)
    check("fixtura reczna (nie z bazy): ESTIMATE-SKEW", ["ESTIMATE-SKEW"], [x[2] for x in f])
finally:
    shutil.rmtree(d, ignore_errors=True)

# ------------------------------------------------------------------ 5. hook
print("\n== 5. Hook ef-post-edit.py na plikach pg-plan-demo (JSON na stdin, jak PostToolUse) ==")


def run_hook(path):
    payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": path}})
    r = subprocess.run([sys.executable, HOOK], input=payload, capture_output=True, text=True)
    return r.returncode, r.stderr


code, err = run_hook(os.path.join(DEMO, "Queries.cs"))
check("Queries.cs (Contains/EndsWith na Npgsql) -> exit 2, GIN w komunikacie", (2, True), (code, "gin_trgm_ops" in err))
code, err = run_hook(os.path.join(DEMO, "ShopContext.cs"))
check("ShopContext.cs -> exit 0", 0, code)

n_ok = sum(results)
print(f"\nWYNIK: {n_ok}/{len(results)} sprawdzen zgodnych")
sys.exit(0 if n_ok == len(results) else 1)
