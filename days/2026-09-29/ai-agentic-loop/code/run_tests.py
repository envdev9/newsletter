#!/usr/bin/env python3
"""Uruchamia wszystkie scenariusze z scenarios.py przez skill_router_sim.rank(),
drukuje pelna tabele dla kazdego (ten output trafia do ARTICLE.md) i sprawdza
zestaw asercji opisujacych, na czym polega mechanizm i gdzie sa jego granice.

Uzycie: python3 run_tests.py
Exit 0 = wszystkie asercje przeszly, Exit 1 = przynajmniej jedna nie.
"""
import sys
from pathlib import Path

from scenarios import SCENARIOS
from skill_router_sim import load_skills, print_table, rank

THRESHOLD = 0.12
SKILLS_DIR = Path(__file__).parent / "skills"


def by_name(results, name):
    for r in results:
        if r["name"] == name:
            return r
    raise KeyError(name)


def main() -> int:
    skills = load_skills(SKILLS_DIR)
    checks = []

    for sc in SCENARIOS:
        print(f"\n### {sc['id']}")
        print(f"# {sc['note']}")
        results = rank(sc["task"], skills, THRESHOLD)
        print_table(sc["task"], results, THRESHOLD)
        sc["_results"] = results

    def check(label, condition):
        checks.append((label, bool(condition)))

    rA = next(s for s in SCENARIOS if s["id"] == "A-literal-match")["_results"]
    check("A: ef-core-migration-safety = top1 i LOAD",
          rA[0]["name"] == "ef-core-migration-safety" and rA[0]["load"])
    check("A: dotnet-test-triage-v2-broad LOAD",
          by_name(rA, "dotnet-test-triage-v2-broad")["load"])
    check("A: dotnet-helper i general-code-assistant score=0",
          by_name(rA, "dotnet-helper")["score"] == 0
          and by_name(rA, "general-code-assistant")["score"] == 0)

    rB = next(s for s in SCENARIOS if s["id"] == "B-paraphrase")["_results"]
    check("B: dotnet-test-triage-v2-broad = top1 i LOAD (parafraza zlapana)",
          rB[0]["name"] == "dotnet-test-triage-v2-broad" and rB[0]["load"])
    check("B: dotnet-test-triage-v1-narrow score=0 (parafraza NIE zlapana - wazna granica)",
          by_name(rB, "dotnet-test-triage-v1-narrow")["score"] == 0)
    check("B: general-code-assistant score>0 ale skip (przypadkowe 'kodu', nie wygrywa)",
          0 < by_name(rB, "general-code-assistant")["score"] < THRESHOLD)

    rC = next(s for s in SCENARIOS if s["id"] == "C-migration-clear")["_results"]
    check("C: ef-core-migration-safety = top1, LOAD, score > 0.5",
          rC[0]["name"] == "ef-core-migration-safety" and rC[0]["load"] and rC[0]["score"] > 0.5)
    check("C: wszystkie inne skille score=0",
          all(r["score"] == 0 for r in rC if r["name"] != "ef-core-migration-safety"))

    rD = next(s for s in SCENARIOS if s["id"] == "D-unrelated")["_results"]
    check("D: zaden skill nie przekracza progu (domyslnie nic sie nie laduje)",
          all(not r["load"] for r in rD))

    rE = next(s for s in SCENARIOS if s["id"] == "E-inflection-limit")["_results"]
    check("E: ef-core-migration-safety ma niezerowy, ale zbyt slaby sygnal (skip) - limit heurystyki",
          by_name(rE, "ef-core-migration-safety")["score"] > 0
          and not by_name(rE, "ef-core-migration-safety")["load"])
    check("E: wszystkie inne skille score=0",
          all(r["score"] == 0 for r in rE if r["name"] != "ef-core-migration-safety"))

    print("\n### Asercje")
    passed = 0
    for label, ok in checks:
        print(("OK  " if ok else "FAIL"), label)
        passed += int(ok)
    print(f"\nWYNIK: {passed}/{len(checks)}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
