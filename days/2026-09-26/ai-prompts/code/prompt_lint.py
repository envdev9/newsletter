#!/usr/bin/env python3
"""Heurystyczny lint promptów dla asystenta kodu (bez zależności, sam stdlib).

UWAGA: to HEURYSTYKA (regexy po słowach kluczowych), nie dowód jakości odpowiedzi modelu.
Prompt może przejść lint i dać kiepską odpowiedź, a prompt bez słowa-klucza może być
świetny. Lint łapie typowe braki (brak pliku, brak logu, brak formatu odpowiedzi).

Rodzaj promptu wynika z prefiksu nazwy pliku: debug_*, review_*, iter_* (iter = debug).
Oczekiwanie wynika z sufiksu: *_bad.txt (lint ma znaleźć braki), *_good.txt (ma przejść).

Użycie:
    python3 prompt_lint.py                  # tryb samotestu: prompts/*.txt
    python3 prompt_lint.py plik.txt ...     # wskazane pliki
    python3 prompt_lint.py --strict plik    # exit 1, jeśli którykolwiek prompt oblany
Kod wyjścia (tryb samotestu): 0 gdy każdy wynik zgadza się z sufiksem _bad/_good.
"""
import re
import sys
from pathlib import Path

# (id, opis, regex, podpowiedź)
RULES = {
    "DLUGOSC": ("min. 15 słów", None, "Zbyt krótko - model musi zgadywać kontekst."),
    "PLIK": (
        "wskazany plik",
        r"[\w./\\-]+\.(cs|ts|html|sql|csproj|json|yaml|yml)\b",
        "Podaj plik (np. `src/Foo.cs`), inaczej model zacznie od szukania.",
    ),
    "LINIA": (
        "linia/zakres linii",
        r"\b(linie|linii|linia|wiersz\w*|line)\s*\d+|\.\w+:\d+",
        "Podaj linię lub zakres (np. linie 42-58) albo plik:linia.",
    ),
    "DOWOD": (
        "dowód błędu (wyjątek/kod błędu/stack trace)",
        r"(Exception|\bCS\d{4}\b|\bMsg \d+|\bNG\d{4}\b|\bTS\d{4}\b|\bat [\w.<>]+\(|```)",
        "Wklej treść błędu/stack trace w bloku kodu, nie opisuj go własnymi słowami.",
    ),
    "REPRO": (
        "warunki odtworzenia (kiedy występuje)",
        r"(repro|odtworz|kroki|za ka[żz]dym razem|sporadycz|tylko gdy|tylko przy|od (commita|wersji))",
        "Napisz kiedy występuje: zawsze/sporadycznie, od jakiej zmiany, jakie dane.",
    ),
    "HIPOTEZY": (
        "prośba o hipotezy przed poprawką",
        r"(hipotez|zanim\s+(cokolwiek\s+)?(zmienisz|popraw|zmodyfikujesz))",
        "Poproś o ranking hipotez i sposób ich sprawdzenia ZANIM model zmieni kod.",
    ),
    "KRYTERIUM": (
        "kryterium sukcesu",
        r"(kryterium|gotowe gdy|powinien|powinna|oczekuj|dotnet test|zielon)",
        "Napisz po czym poznać, że gotowe (np. test przechodzi, oczekiwany wynik).",
    ),
    "FORMAT": (
        "format odpowiedzi",
        r"(format|tabel\w*|lista numerowana|w punktach|diff|json|maks(ymalnie)?\.? ?\d+)",
        "Narzuć format (tabela/lista/diff/limit długości).",
    ),
    "ZAKRES": (
        "zakres i granice (czego nie ruszać)",
        r"(nie zmieniaj|nie dotykaj|nie refaktoryzuj|nie komentuj|nie proponuj)",
        "Napisz wprost czego model NIE ma robić.",
    ),
    "SKUPIENIE": (
        "wskazane kryteria przeglądu",
        r"(pod k[ąa]tem|skup si[ęe]|szukaj)",
        "Wypisz czego szukać (np. wyścigi, wycieki subskrypcji, N+1).",
    ),
    "WAGA": (
        "skala ważności uwag",
        r"(krytycz\w*|blocker|severity|waga|nit\b)",
        "Zdefiniuj skalę (np. krytyczne/ważne/nit), żeby dało się filtrować uwagi.",
    ),
}

REQUIRED = {
    "debug": ["DLUGOSC", "PLIK", "LINIA", "DOWOD", "REPRO", "HIPOTEZY", "KRYTERIUM", "FORMAT", "ZAKRES"],
    "review": ["DLUGOSC", "PLIK", "SKUPIENIE", "WAGA", "FORMAT", "ZAKRES"],
}


def kind_of(name):
    prefix = name.split("_", 1)[0]
    return "review" if prefix == "review" else "debug"


def check(text, kind):
    """Zwraca listę (id_reguły, zaliczona)."""
    out = []
    for rid in REQUIRED[kind]:
        _, rx, _ = RULES[rid]
        if rid == "DLUGOSC":
            ok = len(text.split()) >= 15
        else:
            ok = re.search(rx, text, re.IGNORECASE) is not None
        out.append((rid, ok))
    return out


def lint_file(path):
    text = path.read_text(encoding="utf-8")
    kind = kind_of(path.name)
    results = check(text, kind)
    passed = sum(1 for _, ok in results if ok)
    return kind, results, passed, len(results)


def main(argv):
    strict = "--strict" in argv
    args = [a for a in argv if not a.startswith("--")]
    files = [Path(a) for a in args] or sorted((Path(__file__).parent / "prompts").glob("*.txt"))
    if not files:
        print("Brak plików do sprawdzenia.", file=sys.stderr)
        return 2

    mismatches = 0
    failed = 0
    for path in files:
        kind, results, passed, total = lint_file(path)
        ok_all = passed == total
        verdict = "PASS" if ok_all else "FAIL"
        failed += 0 if ok_all else 1
        expected = "good" if path.stem.endswith("_good") else "bad" if path.stem.endswith("_bad") else None
        note = ""
        if expected and ((expected == "good") != ok_all):
            mismatches += 1
            note = f"  <-- NIEZGODNE Z OCZEKIWANIEM ({expected})"
        print(f"{path.name:<26} [{kind:<6}] {passed}/{total}  {verdict}{note}")
        for rid, ok in results:
            if not ok:
                print(f"    brak: {RULES[rid][0]:<45} -> {RULES[rid][2]}")

    print()
    if strict:
        print(f"STRICT: {failed} z {len(files)} promptów oblanych.")
        return 1 if failed else 0
    print(f"SAMOTEST: {len(files) - mismatches}/{len(files)} wyników zgodnych z sufiksem _bad/_good.")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
