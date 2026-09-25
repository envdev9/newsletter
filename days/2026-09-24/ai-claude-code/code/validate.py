#!/usr/bin/env python3
"""Waliduje pliki konfiguracyjne Claude Code z tego katalogu.

Te pliki (slash command .md, skill SKILL.md) nie są "uruchamialne" same w sobie -
wykonuje je dopiero asystent Claude Code w swojej pętli. To, co da się faktycznie
zweryfikować bez uruchamiania samego Claude Code, to:
  - poprawność frontmatter (YAML) i obecność wymaganych kluczy,
  - spójność nazwy skilla z nazwą katalogu,
  - poprawność składniowa hooka (ast.parse) + bit wykonywalności.

Hook (`claude-hooks/check-sql-rollback.py`) jest natomiast w pełni uruchamialny -
jego faktyczne przebiegi na przykładowych danych są w code/README.md.
"""
import ast
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
failures = []


def parse_frontmatter(path):
    text = open(path, encoding="utf-8").read()
    if not text.startswith("---"):
        raise ValueError("brak frontmatter (plik nie zaczyna się od '---')")
    end = text.find("\n---", 3)
    if end == -1:
        raise ValueError("niezamknięty blok frontmatter")
    raw = text[3:end]
    return yaml.safe_load(raw) or {}


def check_command(path):
    print(f"[command] {os.path.relpath(path, ROOT)}")
    fm = parse_frontmatter(path)
    for key in ("description", "argument-hint", "allowed-tools"):
        val = fm.get(key)
        if not val or not str(val).strip():
            failures.append(f"{path}: brak/pusty klucz '{key}' we frontmatter")
        else:
            print(f"    {key}: OK ({str(val)[:60]})")


def check_skill(path):
    print(f"[skill]   {os.path.relpath(path, ROOT)}")
    fm = parse_frontmatter(path)
    dir_name = os.path.basename(os.path.dirname(path))
    name = fm.get("name")
    desc = fm.get("description")
    if not name or not str(name).strip():
        failures.append(f"{path}: brak/pusty klucz 'name'")
    elif name != dir_name:
        failures.append(f"{path}: name='{name}' != nazwa katalogu '{dir_name}'")
    else:
        print(f"    name: OK ({name})")
    if not desc or not str(desc).strip():
        failures.append(f"{path}: brak/pusty klucz 'description'")
    else:
        print(f"    description: OK ({len(desc)} znaków)")


def check_hook_syntax(path):
    print(f"[hook]    {os.path.relpath(path, ROOT)}")
    src = open(path, encoding="utf-8").read()
    try:
        ast.parse(src, filename=path)
        print("    składnia Pythona: OK")
    except SyntaxError as e:
        failures.append(f"{path}: błąd składni: {e}")
    if os.access(path, os.X_OK):
        print("    bit wykonywalności: OK")
    else:
        failures.append(f"{path}: brak bitu wykonywalności (chmod +x)")


def main():
    check_command(os.path.join(ROOT, "claude-commands", "gen-csharp-tests.md"))
    check_skill(os.path.join(ROOT, "claude-skills", "angular-component-review", "SKILL.md"))
    check_hook_syntax(os.path.join(ROOT, "claude-hooks", "check-sql-rollback.py"))

    print()
    if failures:
        print(f"WYNIK: {len(failures)} błąd(ów):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("WYNIK: wszystkie pliki poprawne.")


if __name__ == "__main__":
    main()
