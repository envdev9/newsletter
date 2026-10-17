"""Indeks symboli oparty na regexach - FUNKCJA build_index SKOPIOWANA z chain.py (wydanie #18).

Jedyna zmiana: parametr `sub` (nazwa podkatalogu z plikami .cs; w #18 na sztywno "Billing"),
zeby ten sam kod dalo sie puscic na drugim korpusie. Reguly regexow bez zmian.
"""
import os
import re


def build_index(root: str, sub: str = "Billing") -> dict[str, str]:
    """symbol ('Typ' albo 'Typ.Skladowa') -> plik wzgledem root. Regexy, nie Roslyn."""
    index: dict[str, str] = {}
    base = os.path.join(root, sub)
    for name in sorted(os.listdir(base)):
        if not name.endswith(".cs"):
            continue
        rel = f"{sub}/{name}"
        current = None
        with open(os.path.join(base, name), encoding="utf-8") as fh:
            for line in fh:
                m = re.search(r"\b(?:class|record|struct|interface)\s+(\w+)", line)
                if m:
                    current = m.group(1)
                    index[current] = rel
                    continue
                m = re.search(r"\bpublic\s+(?:static\s+)?[\w<>\[\],? ]+?\s+(\w+)\s*(?:\(|=>)", line)
                if m and current:
                    index[f"{current}.{m.group(1)}"] = rel
    return index
