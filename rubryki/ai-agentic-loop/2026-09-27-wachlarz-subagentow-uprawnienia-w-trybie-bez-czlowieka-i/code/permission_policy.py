#!/usr/bin/env python3
"""Lokalny MODEL decyzji o uprawnieniach narzedzi - do zrozumienia mechaniki, nie kopia Claude Code.

Zalozenia (Z PAMIECI, NIEZWERYFIKOWANE w zywym CLI):
  * regula ma postac 'Tool' lub 'Tool(wzorzec)', np. 'Bash(dotnet test*)';
  * deny wygrywa z allow; brak dopasowania -> tryb decyduje;
  * tryby: default (edycje i Bash pytaja), acceptEdits (edycje plikow bez pytania),
    plan (tylko odczyt), bypassPermissions (wszystko bez pytania);
  * w trybie NIEINTERAKTYWNYM 'ask' nie ma kto zatwierdzic -> traktujemy jako deny.
Wzorce dopasowujemy fnmatch (glob), w prawdziwym CLI semantyka wzorcow moze sie roznic.
"""
import fnmatch
import json
import re
import sys

READ_TOOLS = {"Read", "Grep", "Glob"}
EDIT_TOOLS = {"Edit", "Write"}
_RULE = re.compile(r"^(\w+)(?:\((.*)\))?$")


def _match(rule: str, tool: str, arg: str) -> bool:
    m = _RULE.match(rule)
    if not m:
        raise ValueError(f"zla regula: {rule!r}")
    name, pat = m.groups()
    if name != tool:
        return False
    return True if pat is None else fnmatch.fnmatchcase(arg, pat)


def decide(mode, allow, deny, tool, arg="", interactive=False):
    """Zwraca (decyzja, powod); decyzja: allow | deny | ask."""
    if any(_match(r, tool, arg) for r in deny):
        return "deny", "regula deny"
    if mode == "bypassPermissions":
        return "allow", "tryb bypassPermissions"
    if mode == "plan" and tool not in READ_TOOLS:
        return "deny", "tryb plan: tylko odczyt"
    if any(_match(r, tool, arg) for r in allow):
        return "allow", "regula allow"
    if tool in READ_TOOLS:
        return "allow", "odczyt"
    if mode == "acceptEdits" and tool in EDIT_TOOLS:
        return "allow", "tryb acceptEdits"
    if interactive:
        return "ask", "brak reguly - zapytaj czlowieka"
    return "deny", "brak reguly, a nie ma kogo zapytac (headless)"


def main() -> int:
    cfg = json.load(open(sys.argv[1], encoding="utf-8"))
    for case in cfg["calls"]:
        d, why = decide(cfg["mode"], cfg["allow"], cfg["deny"], case["tool"], case.get("arg", ""),
                        cfg.get("interactive", False))
        print(f"{d:5} {case['tool']}({case.get('arg', '')})  <- {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
