#!/usr/bin/env python3
"""Testy skilla ef-core-review v2 (#15): regresja reguł z #14, nowe reguły, plany z interceptora, hook.

Uruchomienie z katalogu code/:   python3 run_tests.py
Tylko stdlib. Nie wymaga .NET ani SQL Server (plany w samples/ zostaly nagrane przez PlanCaptureInterceptor
z prawdziwego SQL Server 2022; patrz README).
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
V1 = os.path.join(HERE, "regression", "ef-v1")
DEMO = os.path.join(HERE, "ef-plan-demo")
results = []


def check(name, expected, actual):
    ok = expected == actual
    results.append(ok)
    print(f"{'OK  ' if ok else 'FAIL'}  {name:<62} oczekiwano: {expected}  otrzymano: {actual}")


def rules(findings):
    out = {}
    for f in findings:
        out[f[3]] = out.get(f[3], 0) + 1
    return dict(sorted(out.items()))


def scan_text(files):
    """files: {nazwa: tresc} -> lista znalezisk (w katalogu tymczasowym). Jesli jest plik 'a.cs', skanowany jest tylko
    on, a pozostale sa kontekstem (model), tak jak sasiednie .cs w prawdziwym repo; inaczej skanowane sa wszystkie."""
    d = tempfile.mkdtemp(prefix="efscan-")
    try:
        paths = []
        for name, body in files.items():
            p = os.path.join(d, name)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body)
            paths.append(p)
        if "a.cs" in files:
            paths = [os.path.join(d, "a.cs")]
        return scan_ef.scan_paths(paths)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def wrap(body, usings="using Microsoft.EntityFrameworkCore;"):
    return usings + "\nclass T {\n" + body + "\n}\n"


# ------------------------------------------------------------------ 1. regresja: kod z #14
print("== 1. Regresja: skaner v2 na kodzie ef-demo z #14 (regression/ef-v1) ==")
check("BadQueries.cs", {"FUNC-ON-COLUMN": 1, "INCLUDE-NO-SPLIT": 1, "N-PLUS-1": 1, "NO-ASNOTRACKING": 2,
                        "SAVECHANGES-IN-LOOP": 1, "TOLIST-BEFORE-FILTER": 1},
      rules(scan_ef.scan_paths([os.path.join(V1, "BadQueries.cs")])))
check("GoodQueries.cs", {}, rules(scan_ef.scan_paths([os.path.join(V1, "GoodQueries.cs")])))
check("BadShopContext.cs", {"STRING-UNICODE": 1}, rules(scan_ef.scan_paths([os.path.join(V1, "BadShopContext.cs")])))
check("GoodShopContext.cs", {}, rules(scan_ef.scan_paths([os.path.join(V1, "GoodShopContext.cs")])))
check("Entities.cs (cisza)", {}, rules(scan_ef.scan_paths([os.path.join(V1, "Entities.cs")])))

# ------------------------------------------------------------------ 2. kod ef-plan-demo
print("\n== 2. Skaner v2 na kodzie ef-plan-demo (zapytania mierzone na SQL Server) ==")
check("Queries.cs", {"CONTAINS-CONSTANT": 1, "CONTAINS-LIST": 1, "LIKE-LEADING-WILDCARD": 2},
      rules(scan_ef.scan_paths([os.path.join(DEMO, "Queries.cs")])))
check("ShopContext.cs (cisza)", {}, rules(scan_ef.scan_paths([os.path.join(DEMO, "ShopContext.cs")])))
check("PlanCaptureInterceptor.cs (cisza)", {}, rules(scan_ef.scan_paths([os.path.join(DEMO, "PlanCaptureInterceptor.cs")])))
check("Program.cs (tryb Constant porownywany celowo)", {"CONTAINS-CONSTANT": 1},
      rules(scan_ef.scan_paths([os.path.join(DEMO, "Program.cs")])))

# ------------------------------------------------------------------ 3. fixtury inline: reguly z #14
print("\n== 3. Fixtury inline: przypadki brzegowe regul z #14 ==")
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

# ------------------------------------------------------------------ 4. fixtury inline: v2
print("\n== 4. Fixtury inline: nowe reguly i dopasowanie po typie (v2) ==")
MODEL = (
    "using Microsoft.EntityFrameworkCore;\n"
    "public class Cust { public int Id {get;set;} public string Email {get;set;} = \"\"; public string Note {get;set;} = \"\";\n"
    "  public List<Ord> Orders {get;set;} = new(); }\n"
    "public class Ord { public int Id {get;set;} public string Email {get;set;} = \"\"; }\n"
    "public class ShopCtx : DbContext {\n"
    "  public DbSet<Cust> Customers => Set<Cust>();\n"
    "  public DbSet<Ord> Orders => Set<Ord>();\n"
    "  protected override void OnModelCreating(ModelBuilder b) { b.Entity<Cust>().HasIndex(c => c.Email); }\n"
    "}\n")


def v2(body):
    return scan_text({"model.cs": MODEL, "a.cs": wrap(body)})


check("Email.Contains na indeksowanej -> LIKE", {"LIKE-LEADING-WILDCARD": 1}, rules(v2(
    'List<Cust> M(AppDb db, string t) { return db.Customers.AsNoTracking().Where(c => c.Email.Contains(t)).ToList(); }')))
check("Email.EndsWith na indeksowanej -> LIKE", {"LIKE-LEADING-WILDCARD": 1}, rules(v2(
    'List<Cust> M(AppDb db, string t) { return db.Customers.AsNoTracking().Where(c => c.Email.EndsWith(t)).ToList(); }')))
check("Email.StartsWith (sargowalne) -> cisza", {}, rules(v2(
    'List<Cust> M(AppDb db, string t) { return db.Customers.AsNoTracking().Where(c => c.Email.StartsWith(t)).ToList(); }')))
check("Note.Contains (kolumna BEZ indeksu) -> cisza", {}, rules(v2(
    'List<Cust> M(AppDb db, string t) { return db.Customers.AsNoTracking().Where(c => c.Note.Contains(t)).ToList(); }')))
check("TYP: Email.Contains na Ord (Email bez indeksu na tej encji)", {}, rules(v2(
    'List<Ord> M(AppDb db, string t) { return db.Orders.AsNoTracking().Where(o => o.Email.Contains(t)).ToList(); }')))
check("EF.Functions.Like(c.Email, \"%x\") -> LIKE", {"LIKE-LEADING-WILDCARD": 1}, rules(v2(
    'List<Cust> M(AppDb db) { return db.Customers.AsNoTracking().Where(c => EF.Functions.Like(c.Email, "%abc")).ToList(); }')))
check("EF.Functions.Like(c.Email, \"abc%\") -> cisza", {}, rules(v2(
    'List<Cust> M(AppDb db) { return db.Customers.AsNoTracking().Where(c => EF.Functions.Like(c.Email, "abc%")).ToList(); }')))
check("kolekcja nawigacyjna c.Orders.Contains(x) -> cisza", {}, rules(v2(
    'List<Cust> M(AppDb db, Ord x) { return db.Customers.AsNoTracking().Where(c => c.Orders.Contains(x)).ToList(); }')))
check("LIKE w komentarzu i stringu -> cisza", {}, rules(v2(
    'int M(AppDb db) {\n  // db.Customers.Where(c => c.Email.Contains("x"));\n'
    '  var s = "db.Customers.Where(c => c.Email.Contains(t))";\n  return s.Length;\n}')))
check("ef-review: ignore LIKE-LEADING-WILDCARD", {}, rules(v2(
    'List<Cust> M(AppDb db, string t) {\n  // ef-review: ignore LIKE-LEADING-WILDCARD\n'
    '  return db.Customers.AsNoTracking().Where(c => c.Email.Contains(t)).ToList();\n}')))
check("ids.Contains(c.Id) -> CONTAINS-LIST (INFO)", {"CONTAINS-LIST": 1}, rules(v2(
    'List<Cust> M(AppDb db, List<int> ids) { return db.Customers.AsNoTracking().Where(c => ids.Contains(c.Id)).ToList(); }')))
check("request.Ids.Contains(c.Id) -> CONTAINS-LIST", {"CONTAINS-LIST": 1}, rules(v2(
    'List<Cust> M(AppDb db, Req request) { return db.Customers.AsNoTracking().Where(c => request.Ids.Contains(c.Id)).ToList(); }')))
check("EF.Constant(ids).Contains -> CONTAINS-CONSTANT", {"CONTAINS-CONSTANT": 1}, rules(v2(
    'List<Cust> M(AppDb db, List<int> ids) { return db.Customers.AsNoTracking().Where(c => EF.Constant(ids).Contains(c.Id)).ToList(); }')))
check("ParameterTranslationMode.Constant -> CONTAINS-CONSTANT", {"CONTAINS-CONSTANT": 1}, rules(v2(
    'void Cfg(DbContextOptionsBuilder b) { b.UseSqlServer("x", o => o.UseParameterizedCollectionMode(ParameterTranslationMode.Constant)); }')))
check("ParameterTranslationMode.Parameter -> cisza", {}, rules(v2(
    'void Cfg(DbContextOptionsBuilder b) { b.UseSqlServer("x", o => o.UseParameterizedCollectionMode(ParameterTranslationMode.Parameter)); }')))
check("TYP: `Repo repo` + DbSet Orders -> TOLIST (dawna luka z #14)", {"TOLIST-BEFORE-FILTER": 1}, rules(v2(
    'int M(Repo repo) {\n  return repo.Orders.ToList().Where(o => o.Id > 1).Count();\n}')))
check("TYP: pole `ShopCtx _store` -> TOLIST", {"TOLIST-BEFORE-FILTER": 1}, rules(v2(
    'private readonly ShopCtx _store;\nint M() {\n  return _store.Orders.ToList().Where(o => o.Id > 1).Count();\n}')))
check("TYP: `Repo repo` w petli -> N+1", {"N-PLUS-1": 1}, rules(v2(
    'void M(Repo repo, int[] ids) {\n  foreach (var i in ids) {\n    var o = repo.Orders.AsNoTracking().FirstOrDefault(x => x.Id == i);\n  }\n}')))
check("TYP: `Thing thing` (typ bez nazwy kontekstowej) -> cisza", {}, rules(v2(
    'int M(Thing thing) {\n  return thing.Orders.ToList().Where(o => o.Id > 1).Count();\n}')))
check("TYP: nawigacja `Cust c` -> c.Orders.Count() w petli to nie N+1", {}, rules(v2(
    'int M(Cust c, int[] ids) {\n  var t = 0;\n  foreach (var i in ids) { t += c.Orders.Count(); }\n  return t;\n}')))
check("TYP: `var c` z foreach po db.Customers -> c.Orders.Count() cisza", {}, rules(v2(
    'int M(AppDb db) {\n  var t = 0;\n  foreach (var c in db.Customers.AsNoTracking().ToList()) { t += c.Orders.Count(); }\n  return t;\n}')))

# ------------------------------------------------------------------ 5. plany z interceptora (prawdziwy SQL Server 2022)
print("\n== 5. scan_plan.py na planach zapisanych przez PlanCaptureInterceptor (SQL Server 2022) ==")


def plan_rules(name):
    r = subprocess.run([sys.executable, os.path.join(SKILL, "scan_plan.py"), os.path.join(HERE, "samples", name)],
                       capture_output=True, text=True)
    return sorted(set(re.findall(r"\| (?:WARN|INFO) \| ([A-Z\-]+) \|", r.stdout)))


PLAN_EXPECT = {"eq": ["KEY-LOOKUP"], "startswith": ["KEY-LOOKUP"], "contains": ["SCAN"], "endswith": ["SCAN"]}
for label, exp in PLAN_EXPECT.items():
    check(f"like_{label}.xml", exp, plan_rules(f"like_{label}.xml"))

# spojnosc: skaner KODU oznacza dokladnie te metody Queries.cs, ktorych PLAN ma SCAN
qs_path = os.path.join(DEMO, "Queries.cs")
qs_lines = open(qs_path, encoding="utf-8").read().split("\n")
flagged = {f[1] for f in scan_ef.scan_paths([qs_path]) if f[3] == "LIKE-LEADING-WILDCARD"}
method_of = {"eq": "EmailEquals", "startswith": "EmailStartsWith", "contains": "EmailContains", "endswith": "EmailEndsWith"}


def flagged_method(name):
    start = next(i for i, l in enumerate(qs_lines, 1) if f" {name}(" in l)
    return any(start <= ln <= start + 2 for ln in flagged)


check("kod i plan zgodne: metody z LIKE-LEADING-WILDCARD == plany ze SCAN",
      {k: ("SCAN" in v) for k, v in PLAN_EXPECT.items()},
      {k: flagged_method(m) for k, m in method_of.items()})

# ------------------------------------------------------------------ 6. hook
print("\n== 6. Hook ef-post-edit.py (JSON na stdin jak w PostToolUse) ==")


def run_hook(payload, raw=None):
    data = raw if raw is not None else json.dumps(payload)
    r = subprocess.run([sys.executable, HOOK], input=data, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def edit(path, tool="Edit"):
    return {"tool_name": tool, "tool_input": {"file_path": path}}


rc, out, err = run_hook(edit(os.path.join(V1, "BadQueries.cs")))
check("BadQueries.cs -> exit 2 + stderr z N-PLUS-1", (2, True), (rc, "N-PLUS-1" in err and "TOLIST-BEFORE-FILTER" in err))
rc, out, err = run_hook(edit(os.path.join(V1, "BadQueries.cs"), "MultiEdit"))
check("MultiEdit na BadQueries.cs -> exit 2", 2, rc)
rc, out, err = run_hook(edit(os.path.join(V1, "GoodQueries.cs")))
check("GoodQueries.cs -> exit 0, cisza", (0, "", ""), (rc, out, err))
rc, out, err = run_hook(edit(os.path.join(V1, "BadShopContext.cs")))
ctx = json.loads(out)["hookSpecificOutput"] if out.strip() else {}
check("BadShopContext.cs -> exit 0 + additionalContext (INFO)", (0, "PostToolUse", True),
      (rc, ctx.get("hookEventName"), "STRING-UNICODE" in ctx.get("additionalContext", "")))
rc, out, err = run_hook(edit(os.path.join(DEMO, "Queries.cs")))
check("ef-plan-demo/Queries.cs -> exit 2 + LIKE-LEADING-WILDCARD", (2, True, True),
      (rc, "LIKE-LEADING-WILDCARD" in err, "CONTAINS-CONSTANT" in err))
rc, out, err = run_hook(edit(os.path.join(SKILL, "SKILL.md")))
check("plik .md -> exit 0", (0, "", ""), (rc, out, err))
rc, out, err = run_hook(edit("/nie/ma/takiego/Plik.cs"))
check("nieistniejacy .cs -> exit 0", 0, rc)
rc, out, err = run_hook({"tool_name": "Read", "tool_input": {"file_path": os.path.join(V1, "BadQueries.cs")}})
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
    # v2 przez hook: `repo.Orders` rozpoznane po typie zadeklarowanym + DbSet z sasiedniego pliku
    with open(os.path.join(d, "Model.cs"), "w") as fh:
        fh.write(MODEL)
    p2 = os.path.join(d, "RepoUse.cs")
    with open(p2, "w") as fh:
        fh.write("using Microsoft.EntityFrameworkCore;\nclass U { int M(Repo repo) { return repo.Orders.ToList().Where(o => o.Id > 1).Count(); } }\n")
    rc, out, err = run_hook(edit(p2))
    check("hook: `Repo repo` + DbSet w sasiednim pliku -> exit 2 (TOLIST)", (2, True), (rc, "TOLIST-BEFORE-FILTER" in err))
finally:
    shutil.rmtree(d, ignore_errors=True)

passed = sum(results)
print(f"\nWYNIK: {passed}/{len(results)} sprawdzen zgodnych")
sys.exit(0 if passed == len(results) else 1)
