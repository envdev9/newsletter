#!/usr/bin/env python3
"""ctxaudit - audyt STAŁEGO kosztu kontekstu: pamięć (CLAUDE.md) i definicje narzędzi MCP.

Dwa podpolecenia, zero zależności (python3 >= 3.8):

  python3 -B ctxaudit.py memory --root DIR [--cwd DIR] [--home DIR] [--root-file NAME]
                                 [--turns 40] [--window 200000] [--json]
  python3 -B ctxaudit.py mcp FILE.json [--turns 40] [--window 200000]
                                 [--desc-max 300] [--json]

Tokeny = bajty/4 (heurystyka, NIE tokenizer Claude'a). Model ładowania pamięci to
MOJE ODTWORZENIE zachowania opisanego w dokumentacji Claude Code (patrz README:
sekcja "Czego nie zweryfikowano") - nie jest wynikiem obserwacji żywego klienta.
Skrypt czyta tylko wskazane katalogi/pliki i drukuje agregaty (nazwy plików, liczby).
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict

MAX_HOPS = 5  # limit zagnieżdżenia importów @plik (wg dokumentacji z pamięci - niezweryfikowane)
MEMORY_NAMES = ("CLAUDE.md", "CLAUDE.local.md")

FENCE = re.compile(r"^\s*(```|~~~)")
IMPORT = re.compile(r"(?<![\w`/@])@([^\s`()<>\"']+)")
TREE_LINE = re.compile(r"[├└│]|^\s*\|--|^\s*`--")
PLATITUDES = [
    r"clean code", r"best practices?", r"high[- ]quality", r"be careful",
    r"think step by step", r"well[- ]tested", r"maintainable code",
    r"\bproduction[- ]ready\b", r"as an expert",
]
PLATITUDE_RE = re.compile("|".join(PLATITUDES), re.I)


def tok(nbytes: int) -> int:
    return nbytes // 4


def strip_code(text: str):
    """Zwraca linie poza blokami ``` (z numerami) i listę bloków (start, długość)."""
    lines, blocks, out = text.splitlines(), [], []
    in_fence, start = False, 0
    for i, line in enumerate(lines):
        if FENCE.match(line):
            if in_fence:
                blocks.append((start, i - start + 1))
            else:
                start = i
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append((i, line))
    return out, blocks


def find_imports(text: str):
    """Ścieżki po @ poza blokami kodu i span-ami `...`; token musi mieć '/' lub '.'."""
    found = []
    for _i, line in strip_code(text)[0]:
        line = re.sub(r"`[^`]*`", "", line)
        for m in IMPORT.finditer(line):
            p = m.group(1).rstrip(".,;:!?")
            if "/" in p or "." in p:
                found.append(p)
    return found


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def resolve(base_file, ref, home):
    if ref.startswith("~/"):
        return os.path.normpath(os.path.join(home or os.path.expanduser("~"), ref[2:]))
    return os.path.normpath(os.path.join(os.path.dirname(base_file), ref))


def load_with_imports(path, source, home, loaded, missing, hop=0, chain=()):
    """Dodaje plik i (rekurencyjnie) jego importy do `loaded` (lista słowników)."""
    real = os.path.realpath(path)
    if real in chain:
        return  # cykl
    text = read(path)
    loaded.append({"path": path, "source": source, "hop": hop,
                   "bytes": len(text.encode()), "text": text})
    if hop >= MAX_HOPS:
        # importy z pliku na granicy limitu nie są rozwijane
        for ref in find_imports(text):
            missing.append((path, ref, f"ponad limit {MAX_HOPS} skoków"))
        return
    for ref in find_imports(text):
        target = resolve(path, ref, home)
        if os.path.isfile(target):
            load_with_imports(target, f"import@{hop + 1}", home, loaded, missing,
                              hop + 1, chain + (real,))
        else:
            missing.append((path, ref, "brak pliku"))


def ancestors(root, cwd):
    root, cwd = os.path.abspath(root), os.path.abspath(cwd)
    rel = os.path.relpath(cwd, root)
    if rel.startswith(".."):
        raise SystemExit("--cwd musi leżeć wewnątrz --root")
    dirs, cur = [root], root
    if rel != ".":
        for part in rel.split(os.sep):
            cur = os.path.join(cur, part)
            dirs.append(cur)
    return dirs


def sections(text):
    """[(nagłówek, bajty)] - podział wg nagłówków # (poza blokami kodu)."""
    res, title, buf, in_fence = [], "(początek pliku)", [], False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
        if not in_fence and re.match(r"^#{1,6}\s", line):
            res.append((title, len("\n".join(buf).encode())))
            title, buf = line.strip("# ").strip(), []
        buf.append(line)
    res.append((title, len("\n".join(buf).encode())))
    return [(t, b) for t, b in res if b > 0]


def lint_memory(loaded):
    """Kandydaci do przycięcia. Heurystyki - wskazują, gdzie patrzeć, nie wydają wyroków."""
    findings, seen = [], {}
    for f in loaded:
        name = os.path.basename(f["path"])
        code_lines, blocks = strip_code(f["text"])
        for start, n in blocks:
            body = "\n".join(f["text"].splitlines()[start:start + n])
            if TREE_LINE.search(body):
                findings.append(("drzewo katalogów (agent zrobi ls)", name, start + 1, tok(len(body.encode()))))
            elif n > 15:
                findings.append(("blok kodu >15 linii (wskaż plik zamiast wklejać)", name, start + 1,
                                 tok(len(body.encode()))))
        for i, line in code_lines:
            t = len(line.encode())
            if TREE_LINE.search(line):
                findings.append(("drzewo katalogów (agent zrobi ls)", name, i + 1, tok(t)))
            elif PLATITUDE_RE.search(line):
                findings.append(("ogólnik bez sprawdzalnej treści", name, i + 1, tok(t)))
            key = re.sub(r"^[\s>*+-]+", "", line).strip().lower()
            if len(key) >= 25:
                if key in seen:
                    findings.append((f"duplikat linii z {seen[key]}", name, i + 1, tok(t)))
                else:
                    seen[key] = name
    return findings


def cmd_memory(a):
    root = os.path.abspath(a.root)
    cwd = os.path.abspath(a.cwd or a.root)
    loaded, missing = [], []
    if a.home:
        h = os.path.join(a.home, "CLAUDE.md")
        if os.path.isfile(h):
            load_with_imports(h, "user", a.home, loaded, missing)
    for d in ancestors(root, cwd):
        for n in MEMORY_NAMES:
            p = os.path.join(d, a.root_file if (d == root and n == "CLAUDE.md") else n)
            if os.path.isfile(p):
                load_with_imports(p, "local" if "local" in n else "hierarchia", a.home, loaded, missing)
    eager = {os.path.realpath(f["path"]) for f in loaded}

    lazy = []
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if not d.startswith(".") and d not in ("node_modules", "bin", "obj"))
        for n in MEMORY_NAMES:
            p = os.path.join(dp, n)
            if n in fn and os.path.realpath(p) not in eager and os.path.basename(p) == n \
                    and not (dp == root and n == "CLAUDE.md" and a.root_file != "CLAUDE.md"):
                lazy.append({"path": p, "bytes": os.path.getsize(p)})

    total_b = sum(f["bytes"] for f in loaded)
    findings = lint_memory(loaded)
    prune = sum(f[3] for f in findings)
    res = {
        "eager_files": [{"file": os.path.relpath(f["path"], root) if f["path"].startswith(root)
                         else ("~/" + os.path.basename(f["path"]) if f["source"] == "user" else f["path"]),
                         "source": f["source"], "bytes": f["bytes"], "tokens": tok(f["bytes"])} for f in loaded],
        "eager_tokens": tok(total_b),
        "lazy": [{"file": os.path.relpath(x["path"], root), "tokens": tok(x["bytes"])} for x in lazy],
        "missing": [{"in": os.path.relpath(p, root) if p.startswith(root) else p, "ref": r, "why": w}
                    for p, r, w in missing],
        "prune_candidates_tokens": prune,
        "findings": [{"rule": r, "file": n, "line": ln, "tokens": t} for r, n, ln, t in findings],
        "token_turns": tok(total_b) * a.turns,
        "window_share_pct": round(100 * tok(total_b) / a.window, 2),
    }
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return res

    print(f"Katalog projektu (root) = {os.path.basename(root)}, cwd = "
          f"{os.path.relpath(cwd, root) if cwd != root else '.'}")
    print()
    print("1) Ładowane na starcie sesji (stały koszt, płacony w KAŻDEJ turze)")
    print(f"{'plik':<34}{'źródło':<13}{'bajtów':>8}{'~tok':>7}")
    for f in res["eager_files"]:
        print(f"{f['file']:<34}{f['source']:<13}{f['bytes']:>8}{f['tokens']:>7}")
    print(f"{'RAZEM':<47}{total_b:>8}{res['eager_tokens']:>7}")
    print(f"= {res['window_share_pct']}% okna {a.window} tok.; przez {a.turns} tur: "
          f"{res['token_turns']} token-tur (zanim padnie pierwsze słowo o zadaniu)")

    print()
    print("2) Największe sekcje (top 6 po tokenach)")
    secs = []
    for f in loaded:
        for title, b in sections(f["text"]):
            secs.append((tok(b), os.path.basename(f["path"]), title))
    secs.sort(reverse=True)
    print(f"{'~tok':>6}  {'plik':<20}sekcja")
    for t, n, title in secs[:6]:
        print(f"{t:>6}  {n:<20}{title[:48]}")

    print()
    print("3) Kandydaci do przycięcia (heurystyki regex)")
    by_rule = defaultdict(lambda: [0, 0])
    for r, _n, _ln, t in findings:
        rule = r.split(" z ")[0] if r.startswith("duplikat") else r
        by_rule[rule][0] += 1
        by_rule[rule][1] += t
    if not by_rule:
        print("(brak)")
    for rule, (n, t) in sorted(by_rule.items(), key=lambda kv: -kv[1][1]):
        print(f"  {n:>3} x {rule:<40} ~{t} tok.")
    print(f"  RAZEM do zbadania: ~{prune} tok. ({100 * prune // max(tok(total_b), 1)}% pamięci; "
          "linie mogą się nakładać)")

    print()
    print("4) Ładowane leniwie (dopiero gdy sesja dotknie plików w tym katalogu - wg dokumentacji)")
    for x in res["lazy"] or [{"file": "(brak)", "tokens": 0}]:
        print(f"  {x['file']:<40}~{x['tokens']} tok.")
    if missing:
        print()
        print("5) Importy nierozwiązane / ponad limit")
        for m in res["missing"]:
            print(f"  {m['in']}: @{m['ref']} ({m['why']})")
    return res


# ---------------------------------------------------------------- MCP

def tool_tokens(tool):
    return tok(len(json.dumps(tool, separators=(",", ":"), ensure_ascii=False).encode()))


def params_of(tool):
    schema = tool.get("inputSchema") or {}
    return schema.get("properties") or {}


def cmd_mcp(a):
    with open(a.file, encoding="utf-8") as f:
        data = json.load(f)
    servers = data.get("servers", data)
    rows, findings, name_owner = [], [], {}
    for sname, sdef in servers.items():
        tools = sdef.get("tools", [])
        toks = [(tool_tokens(t), t) for t in tools]
        rows.append({"server": sname, "tools": len(tools), "tokens": sum(x for x, _ in toks),
                     "max": max((x for x, _ in toks), default=0)})
        prefixes = defaultdict(int)
        for t in tools:
            d = t.get("description", "")
            prefixes[d[:40]] += 1
            if len(d) > a.desc_max:
                findings.append((sname, t["name"], f"opis {len(d)} znaków (> {a.desc_max})"))
            bare = [p for p, v in params_of(t).items() if not v.get("description")]
            if bare:
                findings.append((sname, t["name"], f"parametry bez opisu: {', '.join(bare)}"))
            if len(params_of(t)) > 8:
                findings.append((sname, t["name"], f"{len(params_of(t))} parametrów (> 8)"))
            if t["name"] in name_owner:
                findings.append((sname, t["name"], f"nazwa jak w serwerze {name_owner[t['name']]}"))
            name_owner.setdefault(t["name"], sname)
        for p, n in prefixes.items():
            if n >= 3 and p:
                findings.append((sname, "(kilka narzędzi)", f"{n} opisów zaczyna się tak samo: \"{p}...\""))
    total = sum(r["tokens"] for r in rows)
    res = {"servers": rows, "total_tokens": total, "window_share_pct": round(100 * total / a.window, 2),
           "token_turns": total * a.turns, "findings": [{"server": s, "tool": t, "issue": i} for s, t, i in findings]}
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return res

    print(f"Narzędzi łącznie: {sum(r['tools'] for r in rows)} w {len(rows)} serwerach")
    print()
    print("1) Koszt definicji (nazwa + opis + schemat JSON) per serwer")
    print(f"{'serwer':<14}{'narzędzi':>9}{'~tok':>8}{'~tok/narz.':>12}{'max':>7}{'udział':>8}")
    for r in sorted(rows, key=lambda r: -r["tokens"]):
        print(f"{r['server']:<14}{r['tools']:>9}{r['tokens']:>8}{r['tokens'] // max(r['tools'], 1):>12}"
              f"{r['max']:>7}{100 * r['tokens'] / max(total, 1):>7.1f}%")
    print(f"{'RAZEM':<14}{sum(r['tools'] for r in rows):>9}{total:>8}")
    print(f"= {res['window_share_pct']}% okna {a.window} tok. i {res['token_turns']} token-tur "
          f"przez {a.turns} tur - niezależnie od tego, czy użyjesz choć jednego narzędzia")

    print()
    print("2) Najdroższe narzędzia (top 5)")
    allt = sorted(((tool_tokens(t), s, t["name"]) for s, d in servers.items() for t in d.get("tools", [])),
                  reverse=True)
    for t, s, n in allt[:5]:
        print(f"  {t:>5} tok.  {s}/{n}")

    print()
    print("3) What-if: wyłącz serwer")
    for r in sorted(rows, key=lambda r: -r["tokens"]):
        print(f"  bez {r['server']:<12} -> {total - r['tokens']:>6} tok. "
              f"(oszczędność {r['tokens'] * a.turns} token-tur / {a.turns} tur)")

    print()
    print("4) Zastrzeżenia do definicji (heurystyki)")
    for s, t, i in findings or [("-", "-", "(brak)")]:
        print(f"  {s}/{t}: {i}")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("memory")
    m.add_argument("--root", required=True)
    m.add_argument("--cwd")
    m.add_argument("--home")
    m.add_argument("--root-file", default="CLAUDE.md")
    m.add_argument("--turns", type=int, default=40)
    m.add_argument("--window", type=int, default=200000)
    m.add_argument("--json", action="store_true")
    s = sub.add_parser("mcp")
    s.add_argument("file")
    s.add_argument("--turns", type=int, default=40)
    s.add_argument("--window", type=int, default=200000)
    s.add_argument("--desc-max", type=int, default=300)
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    return cmd_memory(a) if a.cmd == "memory" else cmd_mcp(a)


if __name__ == "__main__":
    main()
    sys.exit(0)
