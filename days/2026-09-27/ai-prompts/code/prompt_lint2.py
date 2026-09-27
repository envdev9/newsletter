#!/usr/bin/env python3
"""Lint promptów #2: refaktoryzacja, migracja, few-shot, CLAUDE.md (stdlib, bez pip).

UWAGA: to HEURYSTYKA (regexy po słowach kluczowych), nie dowód jakości odpowiedzi modelu.
Jedyna reguła, która NIE jest heurystyką słów-kluczy, to ZGODNOSC dla promptów few-shot:
parsuje blok <schema> i naprawdę waliduje JSON w każdym <example><output> względem niego.
(To dalej sprawdza tylko spójność przykładów ze schematem, nie to, co zrobi model.)

Rodzaj promptu wynika z prefiksu nazwy pliku: refactor_*, migrate_*, fewshot_*, claudemd_*.
Oczekiwanie z sufiksu: *_bad.txt (lint ma znaleźć braki), *_good.txt (ma przejść).

Użycie:
    python3 -B prompt_lint2.py                 # samotest: prompts/*.txt
    python3 -B prompt_lint2.py plik.txt ...    # wskazane pliki
    python3 -B prompt_lint2.py --strict plik   # exit 1, jeśli którykolwiek oblany
"""
import json
import re
import sys
from pathlib import Path

FILE_RX = r"[\w./\\-]+\.(cs|ts|html|sql|csproj|json|yaml|yml|props|sln)\b"
GRANICE_RX = r"(nie zmieniaj|nie dotykaj|nie refaktoryzuj|nie ruszaj|nie dodawaj|nie edytuj)"
FORMAT_RX = r"(format|tabel\w*|lista|w punktach|diff|json|maks(ymalnie)?\.? ?\d+)"

# (opis, regex | None, podpowiedź). Reguły z regex=None mają własną funkcję niżej.
RULES = {
    # --- wspólne
    "DLUGOSC": ("min. 15 słów", None, "Zbyt krótko - model musi zgadywać kontekst."),
    "PLIK": ("wskazany plik", FILE_RX, "Podaj plik (np. `src/Foo.cs`)."),
    "GRANICE": ("granice (czego nie ruszać)", GRANICE_RX, "Napisz wprost, czego model NIE ma robić."),
    "FORMAT": ("format odpowiedzi", FORMAT_RX, "Narzuć format (lista kroków/tabela/diff)."),
    # --- refaktoryzacja
    "ZAKRES": ("zakres kodu (metoda/linie)", r"(\blinie\s*\d+|\blinii\s*\d+|\bmetod\w*\s+`|`\w+`\s+w\s+`)",
               "Wskaż metodę i linie; „zrefaktoryzuj serwis” to setki decyzji."),
    "CEL": ("konkretny cel refaktoryzacji", r"(\bcel\s*:|wydzieli|wyodr[eę]bni|rozdziel|zast[aą]p)",
            "Napisz CO ma być inaczej po refaktoryzacji (nie „czyściej”)."),
    "BEZ_ZMIAN": ("zachowanie bez zmian", r"(zachowanie[^.]{0,40}(bez zmian|pozostać)|bez zmiany zachowania)",
                  "Zadeklaruj, że zachowanie ma zostać identyczne."),
    "SIATKA": ("siatka bezpieczeństwa (testy przed zmianą)",
               r"(testy charakteryzuj|golden master|najpierw[^.]{0,80}test|zielone na starym)",
               "Każ napisać testy charakteryzujące ZANIM ruszy kod produkcyjny."),
    "KROKI": ("małe kroki + test po każdym", r"(po ka[żz]dym|ma[łl]ymi porcjami|jedn\w+ regu[łl]\w*|po jednej)",
              "Wymuś małe kroki i uruchomienie testów po każdym."),
    # --- migracja
    "OD_DO": ("kierunek migracji (z X na Y)", r"\bz\s+[\w.`]+\s+na\s+[\w.`]+", "Napisz z czego na co."),
    "INWENTARZ": ("etap inwentarza przed zmianą", r"(inwentarz|przeszukaj|grep|lista użyć)",
                  "Najpierw poproś o inwentarz użyć, potem o zmiany."),
    "ETAPY": ("etapy / zakaz zaczynania od kodu", r"(etap\s*1|nie zaczynaj|zanim cokolwiek|po mojej akceptacji)",
              "Podziel na etapy z punktem akceptacji."),
    "ROZNICE": ("różnice zachowania do sprawdzenia", r"(r[óo]żnic\w+ zachowania|zmienić kontrakt|rozjazd)",
                "Wypisz, co w nowej bibliotece/wersji zachowuje się inaczej."),
    "KRYTERIUM": ("kryterium sukcesu", r"(kryterium|dotnet test|zielon|bajt w bajt)", "Napisz po czym poznać, że gotowe."),
    "STOP": ("kiedy się zatrzymać i zapytać", r"(zatrzymaj si[ęe]|zapytaj|zamiast zgadywa)",
             "Wskaż moment, w którym model ma przerwać i spytać."),
    # --- few-shot (własne funkcje)
    "SCHEMA": ("jawny blok <schema>", None, "Opisz format wyjścia schematem, nie tylko przykładem."),
    "PRZYKLADY": ("min. 2 przykłady <example>", None, "Daj co najmniej 2-3 przykłady."),
    "ZGODNOSC": ("przykłady zgodne ze schematem", None, "Każde <output> musi przechodzić schemat."),
    "ROZNORODNOSC": ("przykłady różnicują wartości enuma", None, "Przykłady muszą pokrywać różne wartości enum."),
    "DELIMITERY": ("dane w znacznikach <input>", r"<input>", "Oddziel dane od instrukcji znacznikami."),
    "WYLACZNIE": ("polecenie „odpowiedz wyłącznie…”", r"(wy[łl][aą]cznie|tylko\s+(tablic|obiekt|json))",
                  "Zakaż tekstu poza formatem."),
    # --- CLAUDE.md
    "KOMENDY": ("min. 2 komendy w backtickach", None, "Podaj dokładne komendy build/test."),
    "POWOD": ("reguły z uzasadnieniem", None, "Przy regułach dopisz „bo/ponieważ”."),
    "KROTKI": ("<= 60 linii", None, "Trwały prompt jest w każdej sesji - trzymaj go krótkim."),
    "BEZ_OGOLNIKOW": ("brak ogólników (clean code/SOLID/best practices)", None,
                      "Usuń ogólniki - model już je zna; zostaw to, czego nie da się wywnioskować."),
    "BEZ_HISTORII": ("brak historii firmy/zespołu", None, "Historia i personalia zjadają kontekst bez pożytku."),
    "WERYFIKACJA": ("warunek „gotowe” (build+testy)", r"(przed zako[ńn]czeniem|nie m[óo]wisz\W+gotowe|zanim powiesz)",
                    "Zapisz, jak agent ma sprawdzić własną pracę."),
}

REQUIRED = {
    "refactor": ["DLUGOSC", "PLIK", "ZAKRES", "CEL", "BEZ_ZMIAN", "SIATKA", "KROKI", "GRANICE", "FORMAT"],
    "migrate": ["DLUGOSC", "PLIK", "OD_DO", "INWENTARZ", "ETAPY", "ROZNICE", "KRYTERIUM", "STOP", "GRANICE", "FORMAT"],
    "fewshot": ["DLUGOSC", "SCHEMA", "PRZYKLADY", "ZGODNOSC", "ROZNORODNOSC", "DELIMITERY", "WYLACZNIE"],
    "claudemd": ["KOMENDY", "POWOD", "GRANICE", "KROTKI", "BEZ_OGOLNIKOW", "BEZ_HISTORII", "WERYFIKACJA"],
}


# ---------- walidacja few-shot: schema vs przykłady ----------

def parse_schema(text):
    """<schema> z liniami `nazwa: string|int|enum(a|b|c)` -> {nazwa: typ} albo None."""
    m = re.search(r"<schema>(.*?)</schema>", text, re.S)
    if not m:
        return None
    schema = {}
    for line in m.group(1).strip().splitlines():
        km = re.match(r"\s*(\w+)\s*:\s*(string|int|enum\(([^)]*)\))\s*$", line)
        if not km:
            return None
        name, typ, enum = km.group(1), km.group(2), km.group(3)
        schema[name] = ("enum", enum.split("|")) if enum is not None else (typ, None)
    return schema or None


def parse_examples(text):
    """Lista surowych treści <output> z bloków <example>."""
    return [m.group(1).strip() for m in re.finditer(r"<example>.*?<output>(.*?)</output>.*?</example>", text, re.S)]


def validate_output(raw, schema):
    """Zwraca listę błędów (pusta = zgodne)."""
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        return [f"to nie jest JSON ({e.msg})"]
    if not isinstance(obj, dict):
        return ["korzeń nie jest obiektem"]
    errs = []
    for key in schema:
        if key not in obj:
            errs.append(f"brak pola `{key}`")
    for key in obj:
        if key not in schema:
            errs.append(f"pole spoza schematu `{key}`")
    for key, (typ, enum) in schema.items():
        if key not in obj:
            continue
        v = obj[key]
        if typ == "string" and not isinstance(v, str):
            errs.append(f"`{key}` ma być string")
        elif typ == "int" and (not isinstance(v, int) or isinstance(v, bool)):
            errs.append(f"`{key}` ma być int, jest {type(v).__name__} ({v!r})")
        elif typ == "enum" and v not in enum:
            errs.append(f"`{key}` = {v!r} spoza enum {enum}")
    return errs


def fewshot_rule(rid, text):
    schema = parse_schema(text)
    outs = parse_examples(text)
    if rid == "SCHEMA":
        return schema is not None
    if rid == "PRZYKLADY":
        return len(outs) >= 2
    if rid == "ZGODNOSC":
        return bool(schema) and bool(outs) and all(not validate_output(o, schema) for o in outs)
    if rid == "ROZNORODNOSC":
        if not schema:
            return False
        enums = [k for k, (t, _) in schema.items() if t == "enum"]
        if not enums:
            return False
        for k in enums:
            vals = set()
            for o in outs:
                try:
                    vals.add(json.loads(o).get(k))
                except (json.JSONDecodeError, AttributeError):
                    pass
            if len(vals) < 2:
                return False
        return True
    raise KeyError(rid)


def fewshot_details(text):
    """Konkretne błędy przykładów (dla czytelnego outputu)."""
    schema = parse_schema(text)
    if not schema:
        return []
    out = []
    for i, o in enumerate(parse_examples(text), 1):
        for e in validate_output(o, schema):
            out.append(f"przykład #{i}: {e}")
    return out


# ---------- reguły CLAUDE.md ----------

def claudemd_rule(rid, text):
    if rid == "KOMENDY":
        return len(re.findall(r"`(dotnet|npm|npx|ng|git|docker)\s[^`]+`", text)) >= 2
    if rid == "POWOD":
        rules = [l for l in text.splitlines() if l.lstrip().startswith("- ") and re.search(r"\bnie\b", l, re.I)]
        return bool(rules) and all(re.search(r"(\bbo\b|ponieważ|żeby|, a )", l + " ") or "`" in l for l in rules) \
            and any(re.search(r"(\bbo\b|ponieważ|żeby)", l) for l in rules)
    if rid == "KROTKI":
        return len([l for l in text.splitlines() if l.strip()]) <= 60
    if rid == "BEZ_OGOLNIKOW":
        return re.search(r"(czysty kod|best practices|\bSOLID\b|\bDRY\b|nowoczesn|myśl zanim)", text, re.I) is None
    if rid == "BEZ_HISTORII":
        return re.search(r"(została założona|historia projektu|szef|zespół składa się)", text, re.I) is None
    raise KeyError(rid)


def check(text, kind):
    out = []
    for rid in REQUIRED[kind]:
        _, rx, _ = RULES[rid]
        if rid == "DLUGOSC":
            ok = len(text.split()) >= 15
        elif kind == "fewshot" and rid in ("SCHEMA", "PRZYKLADY", "ZGODNOSC", "ROZNORODNOSC"):
            ok = fewshot_rule(rid, text)
        elif kind == "claudemd" and rid in ("KOMENDY", "POWOD", "KROTKI", "BEZ_OGOLNIKOW", "BEZ_HISTORII"):
            ok = claudemd_rule(rid, text)
        else:
            ok = re.search(rx, text, re.IGNORECASE) is not None
        out.append((rid, ok))
    return out


def kind_of(name):
    prefix = name.split("_", 1)[0]
    if prefix not in REQUIRED:
        raise SystemExit(f"Nieznany rodzaj promptu (prefiks {prefix!r}); użyj: {', '.join(REQUIRED)}_*.txt")
    return prefix


def main(argv):
    strict = "--strict" in argv
    args = [a for a in argv if not a.startswith("--")]
    files = [Path(a) for a in args] or sorted((Path(__file__).parent / "prompts").glob("*.txt"))
    if not files:
        print("Brak plików do sprawdzenia.", file=sys.stderr)
        return 2
    mismatches = failed = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        kind = kind_of(path.name)
        results = check(text, kind)
        passed = sum(1 for _, ok in results if ok)
        ok_all = passed == len(results)
        failed += 0 if ok_all else 1
        expected = "good" if path.stem.endswith("_good") else "bad" if path.stem.endswith("_bad") else None
        note = ""
        if expected and ((expected == "good") != ok_all):
            mismatches += 1
            note = f"  <-- NIEZGODNE Z OCZEKIWANIEM ({expected})"
        print(f"{path.name:<24} [{kind:<8}] {passed}/{len(results)}  {'PASS' if ok_all else 'FAIL'}{note}")
        for rid, ok in results:
            if not ok:
                print(f"    brak: {RULES[rid][0]:<50} -> {RULES[rid][2]}")
        if kind == "fewshot":
            for d in fewshot_details(text):
                print(f"    walidator: {d}")
    print()
    if strict:
        print(f"STRICT: {failed} z {len(files)} promptów oblanych.")
        return 1 if failed else 0
    print(f"SAMOTEST: {len(files) - mismatches}/{len(files)} wyników zgodnych z sufiksem _bad/_good.")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
