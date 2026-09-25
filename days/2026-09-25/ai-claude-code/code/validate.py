#!/usr/bin/env python3
"""Walidacja statyczna plikow z wydania #2 (to, co da sie sprawdzic bez Claude Code):
  * SKILL.md: poprawny frontmatter YAML, name == nazwa katalogu, jest description
  * settings.snippet.json: poprawny JSON, hook wskazuje na istniejacy skrypt
  * skrypty .py: skladnia (ast.parse)
  * scan_migration.py: exit code 1 dla migracji ryzykownej i 0 dla bezpiecznej
"""
import ast
import json
import os
import subprocess
import sys

import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(ROOT, "claude-skills", "ef-migration-review")
failures = []


def check(cond, ok_msg, fail_msg):
    if cond:
        print("    OK  " + ok_msg)
    else:
        print("    FAIL " + fail_msg)
        failures.append(fail_msg)


def main():
    print("[skill] ef-migration-review/SKILL.md")
    text = open(os.path.join(SKILL_DIR, "SKILL.md"), encoding="utf-8").read()
    end = text.find("\n---", 3)
    fm = yaml.safe_load(text[3:end]) if text.startswith("---") and end != -1 else {}
    check(fm.get("name") == "ef-migration-review", "name == nazwa katalogu", "name != nazwa katalogu")
    check(bool(fm.get("description")), "description (%d znakow)" % len(fm.get("description", "")), "brak description")
    check("allowed-tools" in fm, "allowed-tools: " + str(fm.get("allowed-tools"))[:60], "brak allowed-tools")

    print("[hook] settings.snippet.json")
    snippet = json.load(open(os.path.join(ROOT, "claude-hooks", "settings.snippet.json"), encoding="utf-8"))
    entry = snippet["hooks"]["PreToolUse"][0]
    check(entry["matcher"] == "Bash", "matcher = Bash", "matcher != Bash")
    cmd = entry["hooks"][0]["command"]
    check("check-commit-message.py" in cmd and os.path.exists(os.path.join(ROOT, "claude-hooks", "check-commit-message.py")),
          "command wskazuje na istniejacy skrypt: " + cmd, "command nie wskazuje na skrypt")

    print("[py] skladnia")
    for rel in ("claude-hooks/check-commit-message.py", "claude-skills/ef-migration-review/scan_migration.py",
                "test_commit_hook.py"):
        try:
            ast.parse(open(os.path.join(ROOT, rel), encoding="utf-8").read())
            check(True, rel, "")
        except SyntaxError as exc:
            check(False, "", "%s: %s" % (rel, exc))

    print("[scan] exit code skanera")
    scan = os.path.join(SKILL_DIR, "scan_migration.py")
    for name, expected in (("20260925101500_RiskyChanges.cs", 1), ("20260925103000_SafeAddColumn.cs", 0)):
        r = subprocess.run([sys.executable, scan, os.path.join(SKILL_DIR, "test-fixtures", name)],
                           capture_output=True, text=True)
        check(r.returncode == expected, "%s -> exit %d" % (name, r.returncode),
              "%s: exit %d, oczekiwano %d" % (name, r.returncode, expected))

    print()
    if failures:
        print("WYNIK: %d blad(ow)" % len(failures))
        return 1
    print("WYNIK: wszystkie pliki poprawne.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
