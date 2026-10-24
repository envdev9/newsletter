#!/usr/bin/env python3
"""Statyczny skaner plikow .sql pod katalog antywzorcow wydajnosciowych (T-SQL).

Uzycie:  python3 scan_sql.py plik.sql [plik2.sql ...]
Wyjscie: plik:linia | POZIOM | REGULA | opis        (exit 1 gdy jest WARN)

To heurystyka na regexach, nie parser T-SQL. Nie zna typow kolumn ani statystyk -
znaleziska to KANDYDACI do oceny, nie werdykt. Tylko stdlib.
"""
import re
import sys

WARN, INFO = "WARN", "INFO"

FUNCS = (r"YEAR|MONTH|DAY|DATEPART|DATEDIFF|DATEADD|LOWER|UPPER|LEFT|RIGHT|SUBSTRING|"
         r"ISNULL|COALESCE|CONVERT|CAST|LTRIM|RTRIM|TRIM|REPLACE|FORMAT")
CMP = r"(?:=|<>|!=|<=|>=|<|>|\bLIKE\b|\bIN\b|\bBETWEEN\b)"


def mask(text, keep_strings):
    """Zamienia komentarze (i opcjonalnie tresc stringow) na spacje, zachowujac dlugosc i \\n."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("--", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i)); i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("".join(ch if ch == "\n" else " " for ch in text[i:j])); i = j
        elif c == "'":
            j = i + 1
            while j < n:
                if text[j] == "'":
                    if j + 1 < n and text[j + 1] == "'":
                        j += 2; continue
                    break
                j += 1
            j = min(j + 1, n)
            seg = text[i:j]
            out.append(seg if keep_strings else "".join(ch if ch == "\n" else ("'" if k in (0, len(seg) - 1) else " ") for k, ch in enumerate(seg)))
            i = j
        else:
            out.append(c); i += 1
    return "".join(out)


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def scan(path):
    raw = open(path, encoding="utf-8-sig").read()
    code = mask(raw, keep_strings=True)     # bez komentarzy, ze stringami
    nostr = mask(raw, keep_strings=False)   # bez komentarzy i tresci stringow
    found = []

    def add(pos, level, rule, msg):
        found.append((line_of(raw, pos), level, rule, msg))

    for m in re.finditer(r"\bSELECT\s+(?:DISTINCT\s+)?(?:TOP\s*\(?\s*\d+\s*\)?\s+)?(?:\w+\.)?\*", nostr, re.I):
        # EXISTS (SELECT * ...) jest OK
        before = nostr[max(0, m.start() - 20):m.start()]
        if re.search(r"EXISTS\s*\(\s*$", before, re.I):
            continue
        add(m.start(), WARN, "SELECT-STAR", "SELECT * - zwraca zbedne kolumny, uniemozliwia indeks pokrywajacy (covering) i psuje sie przy zmianie schematu")

    for m in re.finditer(r"\b(%s)\s*\(\s*[\w.\[\]]+\s*(?:,[^()]*)?\)\s*%s" % (FUNCS, CMP), nostr, re.I):
        add(m.start(), WARN, "NON-SARGABLE", "funkcja %s(...) na kolumnie w predykacie - blokuje Index Seek (przepisz na zakres po surowej kolumnie)" % m.group(1).upper())

    for m in re.finditer(r"\bLIKE\s+N?'%", code, re.I):
        add(m.start(), WARN, "LEADING-WILDCARD", "LIKE '%...' - wiodacy wildcard wymusza skan; rozwaz full-text lub inne modelowanie")

    for m in re.finditer(r"\bNOT\s+IN\s*\(\s*SELECT\b", nostr, re.I):
        add(m.start(), WARN, "NOT-IN-SUBQUERY", "NOT IN (SELECT ...) - jedna wartosc NULL w podzapytaniu zwraca 0 wierszy; uzyj NOT EXISTS")

    for m in re.finditer(r"\bWITH\s*\(\s*NOLOCK\s*\)|\bREADPAST\b|\bTABLOCK\b", nostr, re.I):
        if "NOLOCK" in m.group(0).upper():
            add(m.start(), WARN, "NOLOCK", "NOLOCK = READ UNCOMMITTED: brudne odczyty, pominiete/zdublowane wiersze; rozwaz RCSI")

    for m in re.finditer(r"\bDECLARE\s+@?\w+\s+CURSOR\b", nostr, re.I):
        add(m.start(), WARN, "CURSOR", "kursor - przetwarzanie wiersz po wierszu; sprawdz, czy nie da sie zapytaniem zbiorczym")

    for m in re.finditer(r"\bSELECT\s+TOP\b(?:(?!\bFROM\b).)*\bFROM\b(?:(?!;|\bORDER\s+BY\b|\bUNION\b).)*(?:;|$)", nostr, re.I | re.S):
        if not re.search(r"\bORDER\s+BY\b", m.group(0), re.I) and not re.search(r"\(\s*SELECT\s+TOP", m.group(0), re.I):
            add(m.start(), INFO, "TOP-NO-ORDER", "TOP bez ORDER BY - wynik niedeterministyczny")

    for m in re.finditer(r"[=<>]\s*N'", code):
        add(m.start(), INFO, "N-LITERAL", "literal N'...' - jesli kolumna jest varchar, SQL Server konwertuje KOLUMNE (typ o wyzszym priorytecie) -> mozliwy skan; sprawdz typ kolumny")

    for m in re.finditer(r"\bdbo\.\w+\s*\([^)]*\)\s*%s" % CMP, nostr, re.I):
        add(m.start(), INFO, "SCALAR-UDF", "wywolanie funkcji uzytkownika w predykacie - skalarne UDF czesto blokuja paralelizm i seek")

    # DDL: klucz obcy bez indeksu wiodacego na tej kolumnie
    idx_lead = set()
    for m in re.finditer(r"\bCREATE\s+(?:UNIQUE\s+)?(?:(?:NON)?CLUSTERED\s+)?INDEX\s+\S+\s+ON\s+[\w.\[\]]+\s*\(\s*\[?(\w+)\]?", nostr, re.I):
        idx_lead.add(m.group(1).lower())
    for m in re.finditer(r"\bPRIMARY\s+KEY\s*(?:(?:NON)?CLUSTERED\s*)?\(\s*\[?(\w+)\]?", nostr, re.I):
        idx_lead.add(m.group(1).lower())
    for m in re.finditer(r"\bFOREIGN\s+KEY\s*\(\s*\[?(\w+)\]?", nostr, re.I):
        col = m.group(1)
        if col.lower() not in idx_lead:
            add(m.start(), WARN, "FK-NO-INDEX", "klucz obcy na kolumnie '%s' bez indeksu z ta kolumna na pierwszym miejscu - JOIN-y i kasowanie rodzica beda skanowac" % col)

    found.sort()
    return found


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    bad = False
    for p in argv[1:]:
        for line, level, rule, msg in scan(p):
            print("%s:%d | %s | %s | %s" % (p, line, level, rule, msg))
            bad = bad or level == WARN
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
