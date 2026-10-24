#!/usr/bin/env python3
"""Testy ctxaudit na ręcznie zbudowanych, tymczasowych drzewach. Uruchom: python3 -B test_ctxaudit.py"""
import contextlib
import io
import json
import os
import sys
import tempfile

sys.dont_write_bytecode = True
import ctxaudit  # noqa: E402

checks = 0


def check(cond, msg):
    global checks
    if not cond:
        print("BŁĄD:", msg)
        sys.exit(1)
    checks += 1


def put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def run(argv):
    with contextlib.redirect_stdout(io.StringIO()):
        return ctxaudit.main(argv + ["--json"])


with tempfile.TemporaryDirectory() as t:
    # 1) import: jawny @ ładuje plik; wzmianka bez @ nie; @ w bloku kodu i w `span` nie; e-mail nie
    put(f"{t}/CLAUDE.md",
        "# R\nzob @docs/a.md\nnie ładuj: docs/b.md, `@docs/c.md`, mail me@example.com\n"
        "```\n@docs/d.md\n```\n")
    for n in "abcd":
        put(f"{t}/docs/{n}.md", f"# {n}\n" + "x" * 400 + "\n")
    r = run(["memory", "--root", t])
    files = [f["file"] for f in r["eager_files"]]
    check(files == ["CLAUDE.md", os.path.join("docs", "a.md")], f"tylko a.md jest importem: {files}")

    # 2) leniwe vs hierarchia: pod-katalog poza ścieżką cwd jest 'lazy'; na ścieżce cwd - eager
    put(f"{t}/x/CLAUDE.md", "# x\n")
    put(f"{t}/y/CLAUDE.md", "# y\n")
    r = run(["memory", "--root", t, "--cwd", f"{t}/x"])
    check(any(f["file"] == os.path.join("x", "CLAUDE.md") for f in r["eager_files"]), "x eager")
    check([l["file"] for l in r["lazy"]] == [os.path.join("y", "CLAUDE.md")], f"y lazy: {r['lazy']}")

    # 3) limit skoków: łańcuch 8 plików -> ładujemy root + MAX_HOPS importów
    with tempfile.TemporaryDirectory() as c:
        put(f"{c}/CLAUDE.md", "@h1.md\n")
        for i in range(1, 8):
            put(f"{c}/h{i}.md", f"@h{i + 1}.md\n" if i < 7 else "koniec\n")
        r = run(["memory", "--root", c])
        check(len(r["eager_files"]) == 1 + ctxaudit.MAX_HOPS, f"limit skoków: {len(r['eager_files'])}")
        check(any("ponad limit" in m["why"] for m in r["missing"]), "zgłoszono ucięcie łańcucha")

    # 4) cykl nie zapętla się
    with tempfile.TemporaryDirectory() as c:
        put(f"{c}/CLAUDE.md", "@a.md\n")
        put(f"{c}/a.md", "@CLAUDE.md\n")
        r = run(["memory", "--root", c])
        check(len(r["eager_files"]) == 2, f"cykl: {len(r['eager_files'])}")

    # 5) lint: ogólnik, duplikat, drzewo, duży blok
    with tempfile.TemporaryDirectory() as c:
        big = "```csharp\n" + "\n".join(f"var line{i} = {i};" for i in range(20)) + "\n```\n"
        put(f"{c}/CLAUDE.md",
            "- Write clean code and follow best practices.\n"
            "- Never commit directly to main branch, ever.\n"
            "- Never commit directly to main branch, ever.\n"
            "```\nsrc/\n├── a\n└── b\n```\n" + big)
        rules = {f["rule"].split(" (")[0].split(" z ")[0] for f in run(["memory", "--root", c])["findings"]}
        for want in ("ogólnik bez sprawdzalnej treści", "duplikat linii", "drzewo katalogów", "blok kodu >15 linii"):
            check(want in rules, f"lint zna regułę: {want} (jest: {rules})")

    # 6) MCP: liczenie i zastrzeżenia
    mcp = {"servers": {
        "s1": {"tools": [{"name": "a", "description": "d" * 400,
                          "inputSchema": {"type": "object", "properties": {"p": {"type": "string"}}}}]},
        "s2": {"tools": [{"name": "a", "description": "ok",
                          "inputSchema": {"type": "object", "properties": {}}}]}}}
    put(f"{t}/m.json", json.dumps(mcp))
    r = run(["mcp", f"{t}/m.json", "--turns", "10"])
    s1 = next(x for x in r["servers"] if x["server"] == "s1")
    expect = len(json.dumps(mcp["servers"]["s1"]["tools"][0], separators=(",", ":")).encode()) // 4
    check(s1["tokens"] == expect, f"tokeny s1 {s1['tokens']} == {expect}")
    check(r["token_turns"] == r["total_tokens"] * 10, "token-tury = tokeny x tury")
    issues = " | ".join(f["issue"] for f in r["findings"])
    check("opis 400" in issues and "parametry bez opisu: p" in issues and "nazwa jak w serwerze s1" in issues,
          f"zastrzeżenia: {issues}")

print(f"OK: {checks}/{checks} asercji przeszło")
