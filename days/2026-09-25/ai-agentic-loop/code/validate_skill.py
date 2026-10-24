#!/usr/bin/env python3
"""Minimalny lint skilla (bez zaleznosci): frontmatter, wymagane pola, dlugosc opisu,
zgodnosc nazwy z katalogiem, istnienie skryptow wymienionych w tresci.
Uzycie: validate_skill.py <katalog_skilla>. Exit 1 = problemy.
"""
import re
import sys
from pathlib import Path


def main() -> int:
    d = Path(sys.argv[1])
    text = (d / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    problems = []
    if not m:
        print("BLAD: brak frontmattera ---")
        return 1
    meta = dict(re.findall(r"^([a-z-]+):\s*(.+)$", m.group(1), re.M))
    for key in ("name", "description"):
        if key not in meta:
            problems.append(f"brak pola {key}")
    if meta.get("name") and meta["name"] != d.name:
        problems.append(f"name={meta['name']!r} != katalog {d.name!r}")
    desc = meta.get("description", "")
    if len(desc) < 60:
        problems.append("description za krotki - model nie rozpozna kiedy uzyc")
    if not re.search(r"(?i)uzyj|use when|gdy", desc):
        problems.append("description nie mowi KIEDY uzyc skilla")
    for script in set(re.findall(r"([A-Za-z0-9_]+\.py)", text)):
        if not (d / script).exists():
            problems.append(f"tresc wspomina {script}, ale pliku nie ma")
    for p in problems:
        print("BLAD:", p)
    if not problems:
        print(f"OK: {d.name} (opis: {len(desc)} znakow)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
