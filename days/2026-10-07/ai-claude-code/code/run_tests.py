#!/usr/bin/env python3
"""Testy skilla ef-core-review: skaner na kodzie demo, fixtury inline, plany z SQL Server, hook.

Uruchomienie z katalogu code/:   python3 run_tests.py
Tylko stdlib. Nie wymaga .NET ani SQL Server (plany sa w samples/, nagrane z prawdziwego SQL Server 2022).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "claude-skills", "ef-core-review")
sys.path.insert(0, SKILL)
import scan_ef  # noqa: E402

HOOK = os.path.join(HERE, "claude-hooks", "ef-post-edit.py")
DEMO = os.path.join(HERE, "ef-demo")
results = []


def check(name, expected, actual):
    ok = expected == actual
    results.append(ok)
    print(f"{'OK  ' if ok else 'FAIL'}  {name:<58} oczekiwano: {expected}  otrzymano: {actual}")


def rules(findings):
    out = {}
    for f in findings:
        out[f[3]] = out.get(f[3], 0) + 1
    return dict(sorted(out.items()))


def scan_text(files):
    """files: {nazwa: tresc} -> lista znalezisk (w katalogu tymczasowym)."""
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


def wrap(body, usings="using Microsoft.EntityFrameworkCore;"):
    return usings + "\nclass T {\n" + body + "\n}\n"


# ------------------------------------------------------------------ 1. kod demo
print("== 1. Skaner na kodzie ef-demo ==")
check("BadQueries.cs", {"FUNC-ON-COLUMN": 1, "INCLUDE-NO-SPLIT": 1, "N-PLUS-1": 1, "NO-ASNOTRACKING": 2,
                        "SAVECHANGES-IN-LOOP": 1, "TOLIST-BEFORE-FILTER": 1},
      rules(scan_ef.scan_paths([os.path.join(DEMO, "BadQueries.cs")])))
check("GoodQueries.cs", {}, rules(scan_ef.scan_paths([os.path.join(DEMO, "GoodQueries.cs")])))
check("BadShopContext.cs", {"STRING-UNICODE": 1}, rules(scan_ef.scan_paths([os.path.join(DEMO, "BadShopContext.cs")])))
check("GoodShopContext.cs", {}, rules(scan_ef.scan_paths([os.path.join(DEMO, "GoodShopContext.cs")])))
check("Program.cs + Entities.cs (cisza)", {},
      rules(scan_ef.scan_paths([os.path.join(DEMO, "Program.cs"), os.path.join(DEMO, "Entities.cs")])))

# ------------------------------------------------------------------ 2. fixtury inline
print("\n== 2. Fixtury inline (przypadki brzegowe skanera) ==")
check("komentarz i string z antywzorcem -> cisza", {}, rules(scan_text({"a.cs": wrap(
    'void M(AppDb db) {\n'
    '  // db.Orders.ToList().Where(o => o.Id > 1);\n'
    '  var s = "db.Orders.ToList().Where(o => o.Id > 1)";\n'
    '  /* foreach (var x in y) { db.Orders.Count(); } */\n}')})))
check("(await ...ToListAsync()).Where -> TOLIST", {"TOLIST-BEFORE-FILTER": 1}, rules(scan_text({"a.cs": wrap(
    'async Task M(AppDb db) {\n  var x = (await db.Orders.ToListAsync()).Where(o => o.Total > 1).Count();\n}')})))
check("ef-review: ignore (linia wyzej)", {}, rules(scan_text({"a.cs": wrap(
    'int M(AppDb db) {\n  // ef-review: ignore TOLIST-BEFORE-FILTER\n'
    '  return db.Orders.AsNoTracking().ToList().Where(o => o.Total > 1).Count();\n}')})))
check("foreach bez klamer, Count w ciele -> N+1", {"N-PLUS-1": 1}, rules(scan_text({"a.cs": wrap(
    'int M(AppDb db, int[] ids) {\n  var t = 0;\n'
    '  foreach (var id in ids) t += db.Orders.Count(o => o.CustomerId == id);\n  return t;\n}')})))
check("ToList w NAGLOWKU foreach to nie N+1", {}, rules(scan_text({"a.cs": wrap(
    'int M(AppDb db) {\n  var t = 0;\n'
    '  foreach (var c in db.Customers.AsNoTracking().ToList()) { t += c.Id; }\n  return t;\n}')})))
check("zagniezdzone petle: jedno znalezisko (dedup)", {"N-PLUS-1": 1}, rules(scan_text({"a.cs": wrap(
    'void M(AppDb db, int[] a, int[] b) {\n'
    '  foreach (var x in a) {\n    foreach (var y in b) {\n'
    '      var o = db.Orders.AsNoTracking().FirstOrDefault(z => z.Id == x + y);\n    }\n  }\n}')})))
check("UseQuerySplittingBehavior w pliku -> bez INCLUDE", {"NO-ASNOTRACKING": 1}, rules(scan_text({"a.cs": wrap(
    'void Cfg(DbContextOptionsBuilder b) { b.UseSqlServer("x", o => o.UseQuerySplittingBehavior(QuerySplittingBehavior.SplitQuery)); }\n'
    'List<C> M(AppDb db) {\n  return db.Customers.Include(c => c.Orders).Include(c => c.Tags).ToList();\n}')})))
check("jeden Include + ThenInclude -> bez INCLUDE", {"NO-ASNOTRACKING": 1}, rules(scan_text({"a.cs": wrap(
    'List<C> M(AppDb db) {\n  return db.Customers.Include(c => c.Orders).ThenInclude(o => o.Lines).ToList();\n}')})))
check("metoda z SaveChanges -> bez NO-ASNOTRACKING", {}, rules(scan_text({"a.cs": wrap(
    'void M(AppDb db) {\n  var c = db.Customers.Where(x => x.Id == 1).ToList();\n  c[0].Name = "n";\n  db.SaveChanges();\n}')})))
check("Select (projekcja) -> bez NO-ASNOTRACKING", {}, rules(scan_text({"a.cs": wrap(
    'List<string> M(AppDb db) {\n  return db.Customers.Select(c => c.Name).ToList();\n}')})))
check("Year w predykacie -> FUNC", {"FUNC-ON-COLUMN": 1}, rules(scan_text({"a.cs": wrap(
    'int M(AppDb db) {\n  return db.Orders.Count(o => o.Created.Year == 2026);\n}')})))
check("ToLower w Select (nie w predykacie) -> cisza", {}, rules(scan_text({"a.cs": wrap(
    'IQueryable<string> M(AppDb db) {\n  return db.Customers.Select(c => c.Email.ToLower());\n}')})))
check("lista w pamieci (list.ToList().Where) -> cisza", {}, rules(scan_text({"a.cs": wrap(
    'int M(List<int> list) {\n  return list.ToList().Where(x => x > 1).Count();\n}')})))
ENT = "public class P { public int Id {get;set;} public string Sku {get;set;} = \"\"; public string Name {get;set;} = \"\"; }\n"
check("HasIndex(string) bez varchar -> STRING-UNICODE", {"STRING-UNICODE": 1}, rules(scan_text({
    "ent.cs": ENT,
    "ctx.cs": wrap('void C(ModelBuilder b) { b.Entity<P>().HasIndex(p => p.Sku); }')})))
check("HasIndex + IsUnicode(false) -> cisza", {}, rules(scan_text({
    "ent.cs": ENT,
    "ctx.cs": wrap('void C(ModelBuilder b) { b.Entity<P>(e => { e.Property(p => p.Sku).HasMaxLength(20).IsUnicode(false); e.HasIndex(p => p.Sku); }); }')})))
check("HasColumnType(\"varchar(20)\") -> cisza", {}, rules(scan_text({
    "ent.cs": ENT,
    "ctx.cs": wrap('void C(ModelBuilder b) { b.Entity<P>(e => { e.Property(p => p.Sku).HasColumnType("varchar(20)"); e.HasIndex(p => p.Sku); }); }')})))
check("atrybut [Unicode(false)] -> cisza", {}, rules(scan_text({
    "ent.cs": "public class P { public int Id {get;set;} [Unicode(false)] public string Sku {get;set;} = \"\"; }\n",
    "ctx.cs": wrap('void C(ModelBuilder b) { b.Entity<P>().HasIndex(p => p.Sku); }')})))
check("indeks zlozony new { Sku, Name } -> 2 x STRING-UNICODE", {"STRING-UNICODE": 2}, rules(scan_text({
    "ent.cs": ENT,
    "ctx.cs": wrap('void C(ModelBuilder b) { b.Entity<P>().HasIndex(p => new { p.Sku, p.Name }); }')})))
check("HasIndex(int Id) -> cisza (nie string)", {}, rules(scan_text({
    "ent.cs": ENT,
    "ctx.cs": wrap('void C(ModelBuilder b) { b.Entity<P>().HasIndex(p => p.Id); }')})))
check("ZNANA LUKA: zmienna `repo` nie jest rozpoznana jako kontekst", {}, rules(scan_text({"a.cs": wrap(
    'int M(Repo repo) {\n  return repo.Orders.ToList().Where(o => o.Total > 1).Count();\n}')})))

# ------------------------------------------------------------------ 3. plany z prawdziwego SQL Server
print("\n== 3. scan_plan.py na planach zapytan wygenerowanych przez EF Core (SQL Server 2022) ==")


def plan_rules(name):
    r = subprocess.run([sys.executable, os.path.join(SKILL, "scan_plan.py"), os.path.join(HERE, "samples", name)],
                       capture_output=True, text=True)
    return sorted(set(re.findall(r"\| (?:WARN|INFO) \| ([A-Z\-]+) \|", r.stdout)))


check("ef_bad.xml (parametr nvarchar na kolumnie varchar)", ["IMPLICIT-CONVERT", "KEY-LOOKUP", "SCAN"], plan_rules("ef_bad.xml"))
check("ef_good.xml (IsUnicode(false))", ["KEY-LOOKUP"], plan_rules("ef_good.xml"))

# ------------------------------------------------------------------ 4. hook
print("\n== 4. Hook ef-post-edit.py (JSON na stdin jak w PostToolUse) ==")


def run_hook(payload, raw=None):
    data = raw if raw is not None else json.dumps(payload)
    r = subprocess.run([sys.executable, HOOK], input=data, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def edit(path, tool="Edit"):
    return {"tool_name": tool, "tool_input": {"file_path": path}}


rc, out, err = run_hook(edit(os.path.join(DEMO, "BadQueries.cs")))
check("BadQueries.cs -> exit 2 + stderr z N-PLUS-1", (2, True), (rc, "N-PLUS-1" in err and "TOLIST-BEFORE-FILTER" in err))
rc, out, err = run_hook(edit(os.path.join(DEMO, "BadQueries.cs"), "MultiEdit"))
check("MultiEdit na BadQueries.cs -> exit 2", 2, rc)
rc, out, err = run_hook(edit(os.path.join(DEMO, "GoodQueries.cs")))
check("GoodQueries.cs -> exit 0, cisza", (0, "", ""), (rc, out, err))
rc, out, err = run_hook(edit(os.path.join(DEMO, "BadShopContext.cs")))
ctx = json.loads(out)["hookSpecificOutput"] if out.strip() else {}
check("BadShopContext.cs -> exit 0 + additionalContext (INFO)", (0, "PostToolUse", True),
      (rc, ctx.get("hookEventName"), "STRING-UNICODE" in ctx.get("additionalContext", "")))
rc, out, err = run_hook(edit(os.path.join(SKILL, "SKILL.md")))
check("plik .md -> exit 0", (0, "", ""), (rc, out, err))
rc, out, err = run_hook(edit("/nie/ma/takiego/Plik.cs"))
check("nieistniejacy .cs -> exit 0", 0, rc)
rc, out, err = run_hook({"tool_name": "Read", "tool_input": {"file_path": os.path.join(DEMO, "BadQueries.cs")}})
check("tool_name=Read -> exit 0", 0, rc)
rc, out, err = run_hook(None, raw="to nie jest json")
check("niepoprawny JSON -> exit 0", 0, rc)
d = tempfile.mkdtemp(prefix="efhook-")
try:
    p = os.path.join(d, "NoEf.cs")
    with open(p, "w") as fh:
        fh.write("class A { int M(System.Collections.Generic.List<int> l) { return l.ToList().Where(x => x > 1).Count(); } }\n")
    rc, out, err = run_hook(edit(p))
    check(".cs bez EF Core -> exit 0", 0, rc)
finally:
    shutil.rmtree(d, ignore_errors=True)

passed = sum(results)
print(f"\nWYNIK: {passed}/{len(results)} sprawdzen zgodnych")
sys.exit(0 if passed == len(results) else 1)
