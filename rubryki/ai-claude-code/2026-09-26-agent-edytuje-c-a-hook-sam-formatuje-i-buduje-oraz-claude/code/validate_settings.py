#!/usr/bin/env python3
"""Lint zespolowego settings.json (to, co da sie sprawdzic bez Claude Code):
  * poprawny JSON
  * permissions.allow/deny: listy stringow w formie Narzedzie lub Narzedzie(wzorzec)
  * zadna regula nie jest jednoczesnie w allow i deny
  * matcher hooka to poprawny regex
  * kazdy hook `command` z $CLAUDE_PROJECT_DIR/.claude/hooks/X wskazuje na plik claude-hooks/X
    (w tym repo katalog nazywa sie claude-hooks, w docelowym projekcie .claude/hooks)
  * gitignore.snippet zawiera .claude/settings.local.json
  * ostrzega o Bash(*) w allow
Uzycie: python3 validate_settings.py [sciezka/do/settings.json]. Kod wyjscia 1 przy bledach."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
RULE_RE = re.compile(r"^[A-Za-z_]\w*(\(.+\))?$")
errors, warnings = [], []


def ok(msg):
    print("    OK  " + msg)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "claude-config", "settings.json")
    print("[json] " + os.path.relpath(path, ROOT))
    try:
        cfg = json.load(open(path, encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print("BLAD: niepoprawny JSON: %s" % exc)
        return 1
    ok("poprawny JSON, klucze: " + ", ".join(cfg))

    print("[permissions]")
    perms = cfg.get("permissions", {})
    for kind in ("allow", "deny"):
        rules = perms.get(kind, [])
        bad = [r for r in rules if not isinstance(r, str) or not RULE_RE.match(r)]
        if bad:
            errors.append("zla skladnia regul %s: %r" % (kind, bad))
        else:
            ok("%s: %d regul o poprawnej skladni" % (kind, len(rules)))
    both = set(perms.get("allow", [])) & set(perms.get("deny", []))
    if both:
        errors.append("regula jednoczesnie w allow i deny: %r" % sorted(both))
    else:
        ok("brak regul wystepujacych w allow i w deny")
    for r in perms.get("allow", []):
        if r in ("Bash", "Bash(*)", "Bash(:*)"):
            warnings.append("allow zawiera " + r + " - wylacza pytanie o jakakolwiek komende")

    print("[hooks]")
    for event, entries in cfg.get("hooks", {}).items():
        for entry in entries:
            matcher = entry.get("matcher", "")
            try:
                re.compile(matcher)
                ok("%s matcher '%s' to poprawny regex" % (event, matcher))
            except re.error as exc:
                errors.append("matcher %r: %s" % (matcher, exc))
            for h in entry.get("hooks", []):
                cmd = h.get("command", "")
                m = re.search(r'\$CLAUDE_PROJECT_DIR/\.claude/hooks/([^\s"]+)', cmd)
                if m and os.path.exists(os.path.join(ROOT, "claude-hooks", m.group(1))):
                    ok("plik hooka istnieje: claude-hooks/" + m.group(1))
                else:
                    errors.append("hook wskazuje na nieistniejacy plik: " + cmd)

    print("[gitignore]")
    gi = open(os.path.join(ROOT, "claude-config", "gitignore.snippet"), encoding="utf-8").read().splitlines()
    if ".claude/settings.local.json" in gi:
        ok("settings.local.json jest ignorowany")
    else:
        errors.append("brak .claude/settings.local.json w gitignore.snippet")

    print()
    for w in warnings:
        print("UWAGA: " + w)
    for e in errors:
        print("BLAD: " + e)
    if errors:
        return 1
    print("WYNIK: konfiguracja poprawna.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
