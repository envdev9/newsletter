#!/usr/bin/env python3
"""scan_ef.py - deterministyczny skaner antywzorcow EF Core w plikach .cs (tylko stdlib).

Uzycie:
    python3 scan_ef.py <plik.cs|katalog> [...]

Wyjscie: `plik:linia | WARN/INFO | REGULA | opis`. Kod wyjscia 1 gdy jest choc jedno WARN.

Reguly (kandydaci do review, nie werdykt - skaner jest tekstowy, nie zna typow z kompilatora):
  N-PLUS-1              wywolanie zapytania na DbContext (ToList/Count/Any/First/Find/Load...) w petli
  SAVECHANGES-IN-LOOP   SaveChanges(Async) w petli
  TOLIST-BEFORE-FILTER  ToList()/ToArray() (lub AsEnumerable()) i dopiero potem Where/Count/Any/...
  INCLUDE-NO-SPLIT      >= 2 x Include w jednym zapytaniu bez AsSplitQuery/AsSingleQuery
  FUNC-ON-COLUMN        ToLower/Trim/Substring/Year... na kolumnie w predykacie (nie-sargowalne)
  NO-ASNOTRACKING (INFO)odczyt przez ToList/First... bez AsNoTracking, w metodzie bez zapisu
  STRING-UNICODE  (INFO)indeksowana kolumna string bez IsUnicode(false)/varchar -> parametr nvarchar

Wylaczenie reguly w kodzie:  // ef-review: ignore REGULA[, REGULA2]   (ta sama linia lub linia wyzej)
"""
import bisect
import os
import re
import sys

DB_ROOT = re.compile(r"\b_?(?:db|ctx|context|dbContext|dbCtx|\w+Context|\w+Db)\s*\.")
LOOP_RE = re.compile(r"^(foreach|for|while)\s*\(")
MATERIALIZE = r"(?:ToList|ToArray|First|FirstOrDefault|Single|SingleOrDefault|Last|LastOrDefault)"
NPLUS1_CALL = re.compile(
    r"\.(?:ToList|ToArray|First|FirstOrDefault|Single|SingleOrDefault|Last|LastOrDefault|Count|LongCount|"
    r"Any|All|Sum|Min|Max|Average|Find|Load|ExecuteSql|FromSql|FromSqlRaw|SqlQuery|SqlQueryRaw)(?:Async)?\s*[(<]")
SAVE_CALL = re.compile(r"\.SaveChanges(?:Async)?\s*\(")
TOLIST_RE = re.compile(
    r"\.(ToList|ToArray|AsEnumerable)(?:Async)?\s*\(\s*[\w\.]*\s*\)\s*\)?\s*\.\s*"
    r"(Where|Count|LongCount|Any|All|First|FirstOrDefault|Single|SingleOrDefault|Select|OrderBy|"
    r"OrderByDescending|Skip|Take|Sum|Max|Min|Average|GroupBy|Distinct)\b")
PREDICATE_CALLS = re.compile(
    r"\.(?:Where|Any|All|First|FirstOrDefault|Single|SingleOrDefault|Count|LongCount|Last|LastOrDefault|"
    r"SkipWhile|TakeWhile)(?:Async)?\s*\(")
STR_FUNCS = "ToLower|ToUpper|ToLowerInvariant|ToUpperInvariant|Trim|TrimStart|TrimEnd|Substring|Replace"
NOTRACK_SUPPRESS = re.compile(
    r"AsNoTracking|AsTracking|\.Select\s*\(|\.Count|\.LongCount|\.Any|\.All|\.Sum|\.Max|\.Min|\.Average|"
    r"GroupBy|ExecuteUpdate|ExecuteDelete|\.Find")
WRITES_RE = re.compile(r"SaveChanges|\.Entry\s*\(|\.(?:Remove|RemoveRange|Update|UpdateRange|Attach)\s*\(")
CONTROL_WORDS = {"if", "for", "foreach", "while", "switch", "using", "lock", "catch", "else", "try",
                 "do", "fixed", "unchecked", "checked", "namespace", "get", "set", "init"}
DBCONTEXT_RE = re.compile(r":\s*(?:[\w\.]*)DbContext\b")
IGNORE_RE =re.compile(r"ef-review:\s*ignore\s+([A-Z0-9,\- ]+)")

SEVERITY = {
    "N-PLUS-1": "WARN", "SAVECHANGES-IN-LOOP": "WARN", "TOLIST-BEFORE-FILTER": "WARN",
    "INCLUDE-NO-SPLIT": "WARN", "FUNC-ON-COLUMN": "WARN",
    "NO-ASNOTRACKING": "INFO", "STRING-UNICODE": "INFO",
}


# --------------------------------------------------------------------------- tokenizacja
def mask(text):
    """Zwraca (kod bez komentarzy, maska 'jestem w stringu/znaku'). Dlugosc i znaki nowej linii zachowane."""
    out, instr = [], []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        nx = text[i + 1] if i + 1 < n else ""
        if c == "/" and nx == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i)); instr.extend([False] * (j - i)); i = j
            continue
        if c == "/" and nx == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            seg = text[i:j]
            out.append(re.sub(r"[^\n]", " ", seg)); instr.extend([False] * len(seg)); i = j
            continue
        if c in '@$"':
            k = i
            while k < n and text[k] in "@$":
                k += 1
            if k < n and text[k] == '"':
                verbatim = "@" in text[i:k]
                if text.startswith('"""', k):
                    j = text.find('"""', k + 3)
                    j = n if j < 0 else j + 3
                else:
                    j = k + 1
                    while j < n:
                        if verbatim:
                            if text[j] == '"':
                                if j + 1 < n and text[j + 1] == '"':
                                    j += 2; continue
                                j += 1; break
                        else:
                            if text[j] == "\\":
                                j += 2; continue
                            if text[j] == '"':
                                j += 1; break
                        j += 1
                seg = text[i:j]
                out.append(seg); instr.extend([True] * len(seg)); i = j
                continue
        if c == "'":
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2; continue
                if text[j] == "'":
                    j += 1; break
                j += 1
            seg = text[i:j]
            out.append(seg); instr.extend([True] * len(seg)); i = j
            continue
        out.append(c); instr.append(False); i += 1
    return "".join(out), instr


def split_statements(code, instr):
    """Dzieli kod na 'instrukcje' (do ; lub { lub }, poza nawiasami) i zbiera bloki {...}."""
    stmts, blocks, stack = [], [], []
    start, depth = None, 0
    for i, ch in enumerate(code):
        if instr[i]:
            if start is None:
                start = i
            continue
        if start is None:
            if ch.isspace():
                continue
            if ch not in "{};":
                start = i
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        elif depth == 0 and ch in ";{}":
            header = code[start:i] if start is not None else ""
            if start is not None:
                end = i + 1 if ch == ";" else i
                stmts.append({"start": start, "end": end, "text": code[start:end], "term": ch})
            if ch == "{":
                stack.append((i, header))
            elif ch == "}" and stack:
                o, h = stack.pop()
                blocks.append((o, i, h))
            start = None
    if start is not None and code[start:].strip():
        stmts.append({"start": start, "end": len(code), "text": code[start:], "term": ""})
    return stmts, blocks


def match_paren(s, open_idx):
    depth = 0
    for k in range(open_idx, len(s)):
        if s[k] in "([":
            depth += 1
        elif s[k] in ")]":
            depth -= 1
            if depth == 0:
                return k
    return -1


def call_args(text, call_re):
    for m in call_re.finditer(text):
        o = m.end() - 1
        c = match_paren(text, o)
        if c > 0:
            yield text[o + 1:c]


# --------------------------------------------------------------------------- skaner jednego pliku
class FileInfo:
    def __init__(self, path, text):
        self.path = path
        self.orig = text
        self.code, self.instr = mask(text)
        self.stmts, self.blocks = split_statements(self.code, self.instr)
        # wersja bez tresci stringow: reguly szukajace wywolan metod nie moga reagowac na tekst w "..."
        self.ns = "".join(" " if (b and ch != "\n") else ch for ch, b in zip(self.code, self.instr))
        for s in self.stmts:
            s["ns"] = self.ns[s["start"]:s["end"]]
        self.line_starts = [0] + [m.end() for m in re.finditer(r"\n", text)]
        self.ignores = {}
        for ln, line in enumerate(text.split("\n"), 1):
            m = IGNORE_RE.search(line)
            if m:
                self.ignores[ln] = {r.strip() for r in m.group(1).split(",")}

    def line(self, pos):
        return bisect.bisect_right(self.line_starts, pos)

    def ignored(self, rule, first_line, last_line):
        for ln in range(first_line - 1, last_line + 1):
            if rule in self.ignores.get(ln, ()):
                return True
        return False


def string_props(code):
    return set(re.findall(r"\bpublic\s+(?:required\s+)?string\??\s+(\w+)\s*(?:\{|=>|=)", code))


def varchar_props(info):
    props = set()
    attr = r"((?:\[[^\]]*\]\s*)*)public\s+(?:required\s+)?string\??\s+(\w+)"
    for m in re.finditer(attr, info.code):
        a = m.group(1)
        if re.search(r"Unicode\s*\(\s*false\s*\)|TypeName\s*=\s*\"(?:var)?char", a):
            props.add(m.group(2))
    for s in info.stmts:
        t = s["text"]
        pm = re.search(r"\.Property\s*\(\s*\w+\s*=>\s*\w+\.(\w+)\s*\)", t)
        if pm and re.search(r"IsUnicode\s*\(\s*false\s*\)|HasColumnType\s*\(\s*\"(?:var)?char", t):
            props.add(pm.group(1))
    return props


def indexed_props(info):
    found = []  # (prop, pozycja)
    for s in info.stmts:
        t = s["text"]
        for m in re.finditer(r"HasIndex\s*\(\s*\w+\s*=>\s*(?:new\s*\{([^}]*)\}|\w+\.(\w+))", t):
            if m.group(1):
                names = re.findall(r"\w+\.(\w+)", m.group(1))
            else:
                names = [m.group(2)]
            for nme in names:
                found.append((nme, s["start"], s["end"]))
    for m in re.finditer(r"\[\s*Index\s*\(([^\]]*)\)\s*\]", info.code):
        names = re.findall(r"nameof\s*\(\s*\w+\.(\w+)\s*\)", m.group(1)) + re.findall(r"\"(\w+)\"", m.group(1))
        for nme in names:
            found.append((nme, m.start(), m.end()))
    return found


def enclosing_method_text(info, st):
    best = None
    for o, c, h in info.blocks:
        if o <= st["start"] < c:
            hn = " ".join(h.split())
            first = re.match(r"[\w@]+", hn)
            if first and first.group(0) in CONTROL_WORDS:
                continue
            if re.search(r"\b(class|record|struct|interface|enum)\b", hn) or not hn.endswith(")") \
                    and not re.search(r"\)\s*where\s", hn):
                continue
            if best is None or o > best[0]:
                best = (o, c)
    if best:
        return info.ns[best[0]:best[1]]
    return st["ns"]


def scan_info(info, string_names, varchar_names, global_split, global_notrack):
    findings, seen = [], set()

    def add(rule, pos_start, pos_end, msg, key=""):
        l1, l2 = info.line(pos_start), info.line(max(pos_start, pos_end - 1))
        if info.ignored(rule, l1, l2) or (l1, rule, key) in seen:
            return
        seen.add((l1, rule, key))
        findings.append((info.path, l1, SEVERITY[rule], rule, msg))

    def check_loop_body(kind, it, start, end):
        if SAVE_CALL.search(it):
            add("SAVECHANGES-IN-LOOP", start, end,
                f"SaveChanges w petli `{kind}` - kazda iteracja to osobna runda do bazy; "
                "zbierz zmiany i zapisz raz po petli")
        elif DB_ROOT.search(it) and NPLUS1_CALL.search(it):
            add("N-PLUS-1", start, end,
                f"zapytanie do bazy wewnatrz petli `{kind}` (N+1): "
                "`" + " ".join(info.code[start:end].split())[:90] + "` - zamien na jedno zapytanie (Include / "
                "Select / GroupBy / Where(ids.Contains(...)))")

    # --- petle: N+1, SaveChanges w petli
    block_by_open = {o: c for o, c, _ in info.blocks}
    for st in info.stmts:
        t = st["ns"]
        loop_kind = None
        body = None
        if st["term"] == "{" and t.strip() == "do":
            loop_kind = "do"
            body = (st["end"], block_by_open.get(st["end"], st["end"]))
        else:
            m = LOOP_RE.match(t)
            if m:
                loop_kind = m.group(1)
                pc = match_paren(t, t.index("("))
                if pc > 0:
                    if st["term"] == "{" and not t[pc + 1:].strip():
                        body = (st["end"], block_by_open.get(st["end"], st["end"]))
                    elif t[pc + 1:].strip():
                        # cialo to reszta tej samej instrukcji (petla bez klamer)
                        check_loop_body(loop_kind, t[pc + 1:], st["start"] + pc + 1, st["end"])
        if not body:
            continue
        for inner in info.stmts:
            if inner is st or not (body[0] <= inner["start"] < body[1]):
                continue
            it = inner["ns"]
            if LOOP_RE.match(it):
                # zagniezdzona petla: jej cialo sprawdzi wlasna iteracja (naglowek wykonuje sie raz)
                continue
            check_loop_body(loop_kind, it, inner["start"], inner["end"])

    # --- reguly na poziomie instrukcji
    for st in info.stmts:
        t = st["ns"]
        if not DB_ROOT.search(t):
            continue
        if TOLIST_RE.search(t):
            m = TOLIST_RE.search(t)
            add("TOLIST-BEFORE-FILTER", st["start"], st["end"],
                f"`.{m.group(1)}()` przed `.{m.group(2)}()` - tabela jest materializowana w pamieci, a filtr/agregat "
                "dziala w C#; przenies Where/Count/... przed materializacje")
        n_inc = len(re.findall(r"\.Include\s*\(", t))
        if n_inc >= 2 and not re.search(r"AsSplitQuery|AsSingleQuery", t) and not global_split:
            add("INCLUDE-NO-SPLIT", st["start"], st["end"],
                f"{n_inc} x Include w jednym zapytaniu bez AsSplitQuery/AsSingleQuery - przy dwoch kolekcjach "
                "wiersze sie mnoza (iloczyn kartezjanski); dodaj .AsSplitQuery() albo ustaw "
                "UseQuerySplittingBehavior globalnie")
        for arg in call_args(t, PREDICATE_CALLS):
            pm = re.match(r"\s*\(?\s*(\w+)\s*\)?\s*=>", arg)
            if not pm:
                continue
            p = pm.group(1)
            fm = re.search(rf"\b{p}\.[A-Za-z_]\w*(?:\.\w+)*?\.({STR_FUNCS})\s*\(", arg)
            dm = re.search(rf"\b{p}\.[A-Za-z_]\w*\.(Year|Month|Day|Date)\b", arg)
            if fm or dm:
                what = f".{fm.group(1)}()" if fm else f".{dm.group(1)}"
                add("FUNC-ON-COLUMN", st["start"], st["end"],
                    f"`{what}` na kolumnie w predykacie - SQL dostaje funkcje na kolumnie (nie-sargowalne, "
                    "indeks nie zadziala jako Seek); porownaj bez funkcji lub przepisz zakres dat")
                break
        mm = re.search(rf"\.{MATERIALIZE}(?:Async)?\s*\(", t)
        if mm and not global_notrack and not NOTRACK_SUPPRESS.search(t) and not LOOP_RE.match(t) \
                and not WRITES_RE.search(enclosing_method_text(info, st)):
            add("NO-ASNOTRACKING", st["start"], st["end"],
                "odczyt bez AsNoTracking() w metodzie, ktora nic nie zapisuje - encje trafiaja do ChangeTrackera "
                "(pamiec + snapshot); jesli nie modyfikujesz ich dalej, dodaj .AsNoTracking()")

    # --- konfiguracja modelu: indeksowany string bez varchar
    for prop, ps, pe in indexed_props(info):
        if prop in string_names and prop not in varchar_names:
            add("STRING-UNICODE", ps, pe,
                f"indeksowana kolumna string `{prop}` bez IsUnicode(false)/varchar - EF wysle parametr jako "
                "nvarchar; jesli w bazie kolumna jest varchar: CONVERT_IMPLICIT po stronie kolumny i Index Scan "
                "zamiast Seek. Sprawdz typ kolumny w bazie", key=prop)
    return findings


def collect_files(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, names in os.walk(p):
                dirs[:] = [d for d in dirs if d not in ("bin", "obj", ".git", "node_modules")]
                files += [os.path.join(root, n) for n in sorted(names) if n.endswith(".cs")]
        elif p.endswith(".cs") and os.path.isfile(p):
            files.append(p)
    return files


def scan_paths(paths):
    files = collect_files(paths)
    infos = []
    for f in files:
        with open(f, encoding="utf-8-sig", errors="replace") as fh:
            infos.append(FileInfo(f, fh.read()))
    # kontekst globalny: wlasne pliki + sasiednie .cs z tych samych katalogow (encje, Program.cs obok kontekstu)
    context_infos = list(infos)
    seen = {os.path.abspath(f) for f in files}
    for d in sorted({os.path.dirname(os.path.abspath(f)) for f in files}):
        for n in sorted(os.listdir(d)):
            full = os.path.abspath(os.path.join(d, n))
            if n.endswith(".cs") and full not in seen:
                with open(full, encoding="utf-8-sig", errors="replace") as fh:
                    context_infos.append(FileInfo(full, fh.read()))
    # Konfiguracja varchar jest dopasowywana po NAZWIE wlasciwosci (skaner nie zna typow). Zeby dwa rozne
    # DbContexty z tym samym Email nie "zasloniły" sie nawzajem, konfiguracje z plikow DbContext bierzemy
    # tylko z samego skanowanego pliku; z pozostalych plikow (encje z atrybutami, IEntityTypeConfiguration)
    # - ze wszystkich.
    string_names, shared_varchar = set(), set()
    for info in context_infos:
        string_names |= string_props(info.code)
        if not DBCONTEXT_RE.search(info.code):
            shared_varchar |= varchar_props(info)
    global_split = any(re.search(r"UseQuerySplittingBehavior\s*\(", i.code) for i in context_infos)
    global_notrack = any(re.search(r"UseQueryTrackingBehavior\s*\(\s*QueryTrackingBehavior\.NoTracking", i.code)
                         for i in context_infos)
    out = []
    for info in infos:
        varchar_names = shared_varchar | varchar_props(info)
        out += scan_info(info, string_names, varchar_names, global_split, global_notrack)
    return sorted(out, key=lambda f: (f[0], f[1], f[3]))


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    findings = scan_paths(argv)
    for path, line, sev, rule, msg in findings:
        print(f"{path}:{line} | {sev} | {rule} | {msg}")
    n_warn = sum(1 for f in findings if f[2] == "WARN")
    print(f"scan_ef: {len(findings)} znalezisk ({n_warn} WARN, {len(findings) - n_warn} INFO) "
          f"w {len(collect_files(argv))} plikach", file=sys.stderr)
    return 1 if n_warn else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
