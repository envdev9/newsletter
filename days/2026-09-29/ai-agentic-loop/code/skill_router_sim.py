#!/usr/bin/env python3
"""Symulacja mechanizmu wyboru skilla po `description`.

UWAGA - CZYTAJ PRZED UZYCIEM: to NIE jest model, ktory rozumie jezyk. Prawdziwy
Claude Code odczytuje frontmatter kazdego zainstalowanego skilla (samo pole
`description`, nie cala trese SKILL.md - to sie laduje pozniej, tylko dla
wybranego skilla) i SEMANTYCZNIE ocenia, czy opis pasuje do aktualnego zadania -
rozumie synonimy, parafrazy, kontekst. Ten skrypt liczy tylko **nakladanie sie
slow** (bag-of-words, bez stemmingu, bez synonimow) miedzy tekstem zadania a
opisem skilla. To wystarcza, by pokazac SAM MECHANIZM (czytaj-opis -> oceń
trafnosc -> zaladuj-albo-nie) i jego typowa pulapke (opis ogolny "wygrywa"
przez przypadkowe wspolne slowo), ale NIE dowodzi niczego o tym, jak model
faktycznie ocenia trafnosc. Traktuj wyniki jako ilustracje, nie pomiar.

Uzycie:
    python3 skill_router_sim.py "<tekst zadania>" [--skills-dir skills] [--threshold 0.12]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

STOPWORDS = {
    "i", "w", "z", "ze", "za", "na", "do", "od", "po", "u", "a", "o", "sie",
    "nie", "to", "jest", "sa", "byl", "byla", "bylo", "ma", "moze", "mozna",
    "albo", "czy", "gdy", "gdzie", "jak", "jaka", "jaki", "jakie", "ale",
    "tez", "tam", "mimo", "nic", "nikt", "co", "kto", "ktora", "ktory",
    "ktore", "moj", "moje", "twoj", "ich", "ta", "ten", "te", "bo", "lub",
    "ani", "oraz", "jednak", "juz", "sam", "sama", "samo", "przy", "dla",
    "wgraniu", "kazdym", "kazde", "kazdy", "tego", "tej", "tym", "ktoregos",
    "tylko", "jesli", "tak", "nawet", "bez", "przed", "pod", "nad", "byc",
}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
FIELD_RE = re.compile(r"^([a-z-]+):\s*(.+)$", re.M)
WORD_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> set[str]:
    words = WORD_RE.findall(text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def load_skills(skills_dir: Path) -> list[dict]:
    skills = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            continue
        meta = dict(FIELD_RE.findall(m.group(1)))
        name = meta.get("name", skill_md.parent.name)
        description = meta.get("description", "")
        skills.append({
            "name": name,
            "description": description,
            "tokens": tokenize(description),
            "path": skill_md,
        })
    return skills


def word_weights(skills: list[dict]) -> dict[str, float]:
    """Waga slowa = 1 / (liczba skilli, w ktorych opisie to slowo sie pojawia).

    Bez tego "dotnet"/"core"/"net" - obecne w opisach kilku roznych skilli tego
    samego stacku - waga taka sama jak "pipeline" czy "migracje", ktore
    identyfikuja JEDEN konkretny skill. To wciaz nie jest rozumienie znaczenia
    (to zwykle odwrotna-czestosc-w-dokumentach, TF-IDF-lite) - tylko lata
    prostej heurystyki, zeby ogolne slowa nie decydowaly o wyniku tak samo jak
    rzadkie, specyficzne slowa.
    """
    df: dict[str, int] = {}
    for sk in skills:
        for w in sk["tokens"]:
            df[w] = df.get(w, 0) + 1
    return {w: 1.0 / c for w, c in df.items()}


def rank(task: str, skills: list[dict], threshold: float) -> list[dict]:
    """Zwraca skille posortowane po score (wazony recall slow zadania w opisie
    wagami 1/df - patrz word_weights), razem z decyzja LOAD/SKIP wzgledem progu."""
    task_tokens = tokenize(task)
    weights = word_weights(skills)
    task_weight_sum = sum(weights.get(w, 1.0) for w in task_tokens)
    results = []
    for sk in skills:
        overlap = task_tokens & sk["tokens"]
        overlap_weight = sum(weights.get(w, 1.0) for w in overlap)
        score = overlap_weight / task_weight_sum if task_weight_sum else 0.0
        results.append({
            "name": sk["name"],
            "score": round(score, 3),
            "overlap": sorted(overlap),
            "load": score >= threshold,
        })
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def print_table(task: str, results: list[dict], threshold: float) -> None:
    print(f'zadanie: "{task}"')
    print(f"prog (threshold): {threshold}")
    print(f"{'skill':32} {'score':>6} {'decyzja':>8}  wspolne slowa")
    for r in results:
        decyzja = "LOAD" if r["load"] else "skip"
        overlap_preview = ", ".join(r["overlap"]) if r["overlap"] else "-"
        print(f"{r['name']:32} {r['score']:>6} {decyzja:>8}  {overlap_preview}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("task", help="tekst zadania uzytkownika")
    parser.add_argument("--skills-dir", default="skills", type=Path)
    parser.add_argument("--threshold", default=0.12, type=float)
    args = parser.parse_args()

    if not args.skills_dir.exists():
        print(f"BLAD: katalog skilli nie istnieje: {args.skills_dir}", file=sys.stderr)
        return 2

    skills = load_skills(args.skills_dir)
    if not skills:
        print(f"BLAD: brak SKILL.md w {args.skills_dir}", file=sys.stderr)
        return 2

    results = rank(args.task, skills, args.threshold)
    print_table(args.task, results, args.threshold)
    return 0


if __name__ == "__main__":
    sys.exit(main())
