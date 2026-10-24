#!/usr/bin/env python3
"""PostToolUse hook Claude Code: po edycji pliku .cs z EF Core uruchamia scan_ef.py.

Wpinany pod PostToolUse z matcherem "Write|Edit|MultiEdit". Na stdin dostaje JSON
  {"tool_name": "Edit", "tool_input": {"file_path": "/abs/Queries.cs", ...}, ...}

Zachowanie:
  * plik nie jest .cs / nie istnieje / bin|obj / nie wyglada na EF Core   -> exit 0, cisza
  * sa znaleziska WARN  -> stderr = lista, exit 2 (Claude dostaje ja z powrotem i poprawia)
  * tylko INFO          -> exit 0, JSON z `additionalContext` na stdout (podpowiedz bez blokowania)
  * brak czystego skanera / blad skanera -> exit 0 (nigdy nie blokujemy pracy awarią narzedzia)

Szukanie skanera: $EF_REVIEW_SCANNER, potem $CLAUDE_PROJECT_DIR/.claude/skills/ef-core-review/scan_ef.py,
potem ../claude-skills/ef-core-review/scan_ef.py wzgledem tego pliku.
(#15: bez zmian wzgledem #14 - nowe reguly skanera dzialaja przez ten sam hook.)
"""
import importlib.util
import json
import os
import re
import sys

EF_HINT = re.compile(r"Microsoft\.EntityFrameworkCore|\bDbContext\b|\bDbSet<|\bIQueryable<")


def find_scanner():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.environ.get("EF_REVIEW_SCANNER", ""),
        os.path.join(os.environ.get("CLAUDE_PROJECT_DIR", ""), ".claude", "skills", "ef-core-review", "scan_ef.py"),
        os.path.join(here, "..", "claude-skills", "ef-core-review", "scan_ef.py"),
        os.path.join(here, "..", "skills", "ef-core-review", "scan_ef.py"),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def load_scanner(path):
    spec = importlib.util.spec_from_file_location("scan_ef", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if payload.get("tool_name") not in ("Write", "Edit", "MultiEdit"):
        return 0
    path = (payload.get("tool_input") or {}).get("file_path", "")
    if not path.endswith(".cs") or not os.path.isfile(path):
        return 0
    norm = path.replace("\\", "/")
    if "/obj/" in norm or "/bin/" in norm:
        return 0
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        if not EF_HINT.search(fh.read()):
            return 0
    scanner = find_scanner()
    if scanner is None:
        return 0
    try:
        findings = load_scanner(scanner).scan_paths([path])
    except Exception as exc:  # noqa: BLE001 - awaria skanera nie moze blokowac edycji
        print(f"ef-post-edit: blad skanera ({exc.__class__.__name__}: {exc}) - pomijam")
        return 0
    warns = [f for f in findings if f[2] == "WARN"]
    infos = [f for f in findings if f[2] == "INFO"]
    name = os.path.basename(path)
    if warns:
        sys.stderr.write(f"EF-REVIEW: {len(warns)} problem(ow) w {name} po ostatniej edycji:\n")
        for _, line, sev, rule, msg in warns + infos:
            sys.stderr.write(f"  {name}:{line} [{sev}] {rule}: {msg}\n")
        sys.stderr.write("Popraw je albo, jesli to swiadoma decyzja, dodaj komentarz "
                         "`// ef-review: ignore REGULA` nad instrukcja.\n")
        return 2
    if infos:
        text = "EF-REVIEW (informacyjnie) " + name + ": " + " | ".join(
            f"linia {line} {rule}: {msg}" for _, line, _, rule, msg in infos)
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}},
                         ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
