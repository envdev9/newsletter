#!/usr/bin/env python3
"""Lint pliku subagenta (claude-agents/*.md): frontmatter, nazwa, opis, lista narzedzi.

Uzycie: python3 validate_agent.py <plik.md> [--read-only]
Exit 0 = OK (ewentualne ostrzezenia na stdout), 1 = bledy.
Lista znanych narzedzi pochodzi z pamieci (patrz artykul) - nieznana nazwa to tylko OSTRZEZENIE.
"""
import re
import sys
from pathlib import Path

KNOWN_TOOLS = {"Read", "Grep", "Glob", "Edit", "Write", "Bash", "WebFetch", "WebSearch",
               "NotebookEdit", "TodoWrite"}
WRITING_TOOLS = {"Edit", "Write", "Bash", "NotebookEdit"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
WHEN_RE = re.compile(r"\b(use|when|after|before|proactively)\b", re.I)


def parse(text: str):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return None, None
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, m.group(2)


def lint(path: Path, read_only: bool):
    errors, warns = [], []
    fm, body = parse(path.read_text(encoding="utf-8"))
    if fm is None:
        return ["brak frontmattera (--- ... ---) na poczatku pliku"], []
    name, desc = fm.get("name", ""), fm.get("description", "")
    if not name:
        errors.append("brak pola name")
    elif not NAME_RE.match(name):
        errors.append(f"name '{name}' musi byc kebab-case (male litery, cyfry, myslniki)")
    elif name != path.stem:
        warns.append(f"name '{name}' != nazwa pliku '{path.stem}'")
    if not desc:
        errors.append("brak pola description (to ono decyduje o delegowaniu)")
    else:
        if len(desc) < 40:
            errors.append(f"description za krotki ({len(desc)} zn.) - powiedz CO robi i KIEDY uzyc")
        if not WHEN_RE.search(desc):
            errors.append("description nie mowi kiedy uzyc (brak 'use'/'when'/'after'...)")
    tools_raw = fm.get("tools")
    if tools_raw is None:
        warns.append("brak pola tools -> agent dziedziczy WSZYSTKIE narzedzia rodzica")
        tools = set()
    else:
        tools = {t.strip() for t in tools_raw.split(",") if t.strip()}
        for t in sorted(tools - KNOWN_TOOLS):
            warns.append(f"nieznane narzedzie '{t}' (literowka?)")
        if read_only and tools & WRITING_TOOLS:
            errors.append("agent ma byc read-only, a ma: " + ", ".join(sorted(tools & WRITING_TOOLS)))
    if len(body.strip()) < 80:
        errors.append("tresc (prompt systemowy) za krotka - agent nie dostaje nic poza opisem")
    if not re.search(r"(?i)output|format|return|answer", body):
        warns.append("tresc nie opisuje formatu odpowiedzi - rodzic dostanie wolny tekst")
    return errors, warns


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 1
    path = Path(args[0])
    errors, warns = lint(path, "--read-only" in sys.argv)
    for w in warns:
        print(f"WARN: {w}")
    for e in errors:
        print(f"BLAD: {e}")
    if errors:
        print(f"FAIL: {path.name} ({len(errors)} bledow)")
        return 1
    print(f"OK: {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
