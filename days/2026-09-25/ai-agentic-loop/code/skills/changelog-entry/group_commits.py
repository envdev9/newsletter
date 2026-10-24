#!/usr/bin/env python3
"""Grupuje tematy commitow (Conventional Commits, stdin) w wpis Keep a Changelog.

Uzycie: git log <tag>..HEAD --pretty=format:%s | group_commits.py --version X --date YYYY-MM-DD
Exit: 0 = ok, 3 = pusty stdin.
"""
import argparse
import re
import sys

SUBJECT = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<bang>!)?: (?P<desc>.+)$")
SECTION = {"feat": "Added", "fix": "Fixed", "perf": "Changed", "refactor": "Changed"}
ORDER = ["Breaking", "Added", "Fixed", "Changed", "Other"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--input", help="plik z tematami commitow zamiast stdin")
    args = ap.parse_args()

    groups = {name: [] for name in ORDER}
    raw = open(args.input, encoding="utf-8").read() if args.input else sys.stdin.read()
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not lines:
        sys.stderr.write("brak commitow na stdin\n")
        return 3
    for ln in lines:
        m = SUBJECT.match(ln)
        if not m:
            groups["Other"].append(ln)
            continue
        text = f"**{m['scope']}**: {m['desc']}" if m["scope"] else m["desc"]
        groups[SECTION.get(m["type"], "Other")].append(text)
        if m["bang"]:
            groups["Breaking"].append(text)

    out = [f"## [{args.version}] - {args.date}", ""]
    for name in ORDER:
        if groups[name]:
            out.append(f"### {name}")
            out.extend(f"- {item}" for item in groups[name])
            out.append("")
    print("\n".join(out).rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
