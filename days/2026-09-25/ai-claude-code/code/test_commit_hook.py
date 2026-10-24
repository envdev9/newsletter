#!/usr/bin/env python3
"""Odpala hook check-commit-message.py na zestawie realnych komend i porownuje
kod wyjscia z oczekiwanym. Payload JSON budowany jest tu (zeby nie walczyc z
escapowaniem cudzyslowow w plikach), a hook dostaje go na stdin - tak jak od Claude Code."""
import json
import os
import subprocess
import sys

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "claude-hooks", "check-commit-message.py")

HEREDOC_OK = 'git commit -m "$(cat <<\'EOF\'\nfeat(api): dodaj endpoint zamowien\n\nOpis zmiany.\nEOF\n)"'
HEREDOC_BAD = 'git commit -m "$(cat <<\'EOF\'\nDodalem endpoint zamowien.\nEOF\n)"'

# (opis, tool_name, command, oczekiwany exit)
CASES = [
    ("poprawny commit",                  "Bash", 'git commit -m "feat(orders): dodaj filtrowanie po statusie"', 0),
    ("poprawny, breaking (!)",           "Bash", 'git commit -m "refactor(db)!: usun kolumne legacy_id"', 0),
    ("zly typ / wielka litera",          "Bash", 'git commit -m "Dodalem filtrowanie zamowien"', 2),
    ("brak spacji po dwukropku",         "Bash", 'git commit -m "fix:napraw null"', 2),
    ("kropka na koncu",                  "Bash", 'git commit -m "fix(api): napraw null."', 2),
    ("subject za dlugi",                 "Bash", 'git commit -m "feat: ' + "x" * 80 + '"', 2),
    ("flagi sklejone -am",               "Bash", 'git commit -am "wip"', 2),
    ("--message=...",                    "Bash", 'git commit --message="bugfix"', 2),
    ("git -C repo commit",               "Bash", 'git -C ../repo commit -m "zle"', 2),
    ("w lancuchu && (add + commit)",     "Bash", 'git add -A && git commit -m "zmiany"', 2),
    ("heredoc poprawny",                 "Bash", HEREDOC_OK, 0),
    ("heredoc zly",                      "Bash", HEREDOC_BAD, 2),
    ("brak pustej linii przed body",     "Bash", 'git commit -m "fix(a): b\nbody bez pustej linii"', 2),
    ("wiele -m (paragrafy) poprawne",    "Bash", 'git commit -m "fix(a): b" -m "dluzszy opis"', 0),
    ("merge commit przepuszczony",       "Bash", 'git commit -m "Merge branch \'x\' into main"', 0),
    ("--amend --no-edit przepuszczony",  "Bash", "git commit --amend --no-edit", 0),
    ("-F plik przepuszczony",            "Bash", "git commit -F msg.txt", 0),
    ("zmienna powloki przepuszczona",    "Bash", 'git commit -m "$MSG"', 0),
    ("inna komenda git",                 "Bash", 'git log --oneline -5', 0),
    ("komenda z 'commit' w tekscie",     "Bash", 'echo "git commit -m zle"', 0),
    ("inne narzedzie niz Bash",          "Write", 'git commit -m "zle"', 0),
]


def run(tool, command):
    payload = {"tool_name": tool, "tool_input": {"command": command}}
    return subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                          capture_output=True, text=True)


def main():
    failed = 0
    for desc, tool, command, expected in CASES:
        r = run(tool, command)
        ok = r.returncode == expected
        failed += 0 if ok else 1
        print("%-4s exit=%d (oczekiwano %d)  %s" % ("OK" if ok else "FAIL", r.returncode, expected, desc))
    print("\nWYNIK: %d/%d przypadkow zgodnych" % (len(CASES) - failed, len(CASES)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
