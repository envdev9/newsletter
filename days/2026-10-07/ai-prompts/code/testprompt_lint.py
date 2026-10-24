#!/usr/bin/env python3
"""Lint promptow do generowania testow (stdlib, bez pip). Rodzaj regul z prefiksu pliku
(tests_ / mutfix_), oczekiwanie z sufiksu (_bad / _good).

Roznica wzgledem lintow z poprzednich wydan: czesc regul SPRAWDZA PROMPT WZGLEDEM KODU
(czy wskazany plik istnieje, czy wskazany projekt istnieje, czy wyjatki z kontraktu sa
w XML-doc kodu produkcyjnego, czy wskazane metody istnieja). Reszta to regexy po slowach
kluczowych - heurystyka, nie dowod jakosci odpowiedzi modelu.

Uzycie:
  python3 -B testprompt_lint.py                 # samotest na prompts/
  python3 -B testprompt_lint.py plik.txt ...    # wskazane pliki
  python3 -B testprompt_lint.py --strict plik   # exit 1, gdy ktorykolwiek oblany
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "Billing", "Prorator.cs")


def words(t):
    return len(re.findall(r"\w+", t))


def backticks(t):
    return re.findall(r"`([^`]+)`", t)


def src_text():
    with open(SRC, encoding="utf-8") as f:
        return f.read()


def r_file_exists(t):
    paths = [b for b in backticks(t) if b.endswith(".cs") and "/" in b]
    return bool(paths) and all(os.path.exists(os.path.join(HERE, p.split()[0])) for p in paths)


def r_project_exists(t):
    projs = re.findall(r"dotnet (?:run|test|build) --project (\S+?)[`\s]", t + " ")
    projs = [p.strip("`") for p in projs]
    return bool(projs) and all(os.path.isdir(os.path.join(HERE, p)) for p in projs)


def r_methods_exist(t):
    named = set(re.findall(r"metody `?(\w+)`? i `?(\w+)`?", t))
    if not named:
        return False
    s = src_text()
    return all(re.search(r"\b" + m + r"\(", s) for pair in named for m in pair)


def r_exceptions_match(t):
    mentioned = set(re.findall(r"\b(Argument\w*Exception)\b", t))
    if not mentioned:
        return False
    documented = set(re.findall(r'<exception cref="(\w+)"', src_text()))
    return mentioned <= documented


def r_edge_categories(t):
    kw = ["granic", "ostatni dzie", "przestepn", "przestępn", "zaokr", "zero", "ujemn", "parts = 1",
          "polowk", "połowk", "okresow", "wiecej niz", "więcej niż"]
    return sum(1 for k in kw if k in t.lower()) >= 6


def r_property_seed_iters(t):
    low = t.lower()
    has_prop = "wlasciwo" in low or "właściwo" in low or "property" in low or "niezmiennik" in low
    has_seed = "ziarn" in low or "seed" in low
    iters = re.search(r"min\.?\s*(\d{3,})\s*iteracji", low)
    return has_prop and has_seed and bool(iters)


def r_forbid_weak(t):
    low = t.lower()
    return bool(re.search(r"nie u[zż]ywaj s[lł]abych asercji", low)) and ("isnotnull" in low)


def r_no_prod_change(t):
    return bool(re.search(r"nie zmieniaj kodu produkcyjnego", t.lower()))


def r_verify_mut(t):
    low = t.lower()
    return ("zmien" in low or "zmień" in low or "zmutuj" in low) and "czerwieni" in low


def r_format(t):
    return bool(re.search(r"format odpowiedzi|format:", t.lower()))


def r_contract(t):
    return "KONTRAKT" in t or "specyfikacj" in t.lower()


def r_expected_by_hand(t):
    return bool(re.search(r"nie kopiuj wzoru z implementacji", t.lower()))


def r_mutants_tag(t):
    return "<mutants>" in t and "</mutants>" in t


def r_one_by_one(t):
    return bool(re.search(r"jeden mutant po kolei|po jednym mutancie|jeden po drugim", t.lower()))


def r_equiv_ask(t):
    low = t.lower()
    return "rownowazn" in low and ("czekaj" in low or "zapytaj" in low)


def r_green_red(t):
    low = t.lower()
    return "zielony" in low and "czerwony" in low


def r_dont_weaken(t):
    return bool(re.search(r"nie usuwaj ani nie os[lł]abiaj", t.lower()))


def r_done_cmd(t):
    return bool(re.search(r"gotowe, gdy", t.lower())) and "dotnet run" in t


RULES = {
    "tests": [
        ("min. 40 słów", lambda t: words(t) >= 40, "Zbyt krótko - model musi zgadywać kontekst."),
        ("wskazany plik .cs istnieje w repo", r_file_exists, "Podaj ścieżkę `Billing/Prorator.cs` (lint sprawdza, czy plik istnieje)."),
        ("polecenie `dotnet run --project X` z istniejącym projektem", r_project_exists, "Podaj komendę uruchomienia testów z realnym projektem."),
        ("wskazane metody istnieją w kodzie", r_methods_exist, "Napisz „metody `A` i `B`” - lint sprawdzi je w źródle."),
        ("kontrakt/specyfikacja", r_contract, "Opisz oczekiwane zachowanie - inaczej model testuje implementację."),
        ("wyjątki z kontraktu = wyjątki z XML-doc", r_exceptions_match, "Nazwij typy wyjątków zgodnie z <exception cref> w kodzie."),
        (">= 6 kategorii przypadków brzegowych", r_edge_categories, "Wypisz granice, rok przestępny, zaokrąglanie, zero, ujemne, ostatni dzień..."),
        ("właściwości + ziarno + min. N iteracji", r_property_seed_iters, "Zażądaj testów właściwości z ziarnem i liczbą iteracji."),
        ("zakaz słabych asercji (z przykładem)", r_forbid_weak, "Zakaż `IsNotNull`/samej liczby elementów wprost."),
        ("oczekiwanie liczone ręcznie, nie z implementacji", r_expected_by_hand, "Zakaż kopiowania wzoru z implementacji do asercji."),
        ("zakaz zmiany kodu produkcyjnego", r_no_prod_change, "Bez tego model „naprawi” kod pod swoje testy."),
        ("weryfikacja: zmień operator -> test czerwony", r_verify_mut, "Każ sprawdzić, że test czerwieni się na zmutowanym kodzie."),
        ("format odpowiedzi", r_format, "Narzuć format (jeden plik, komentarz przy przypadku)."),
    ],
    "mutfix": [
        ("min. 40 słów", lambda t: words(t) >= 40, "Zbyt krótko."),
        ("wskazany plik .cs istnieje w repo", r_file_exists, "Podaj istniejące pliki."),
        ("raport mutantów w znaczniku <mutants>", r_mutants_tag, "Oddziel dane (raport) od instrukcji."),
        ("jeden mutant po kolei", r_one_by_one, "Mała jednostka pracy = recenzowalny diff."),
        ("test zielony na oryginale, czerwony na mutancie", r_green_red, "Podaj kryterium poprawności testu."),
        ("mutant równoważny: nie pisz testu, czekaj na decyzję", r_equiv_ask, "Bez tego model napisze test, którego nie da się spełnić."),
        ("zakaz zmiany kodu i osłabiania testów", lambda t: r_no_prod_change(t) and r_dont_weaken(t), "Zakaż obu skrótów."),
        ("warunek „gotowe, gdy” z komendą", r_done_cmd, "Zapisz, jak sprawdzić efekt."),
        ("format odpowiedzi", r_format, "Narzuć format."),
    ],
}


def check(path):
    kind = os.path.basename(path).split("_")[0]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    ok, miss = 0, []
    for name, fn, hint in RULES[kind]:
        if fn(text):
            ok += 1
        else:
            miss.append((name, hint))
    return kind, ok, len(RULES[kind]), miss


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    strict = "--strict" in sys.argv
    files = args or sorted(glob.glob(os.path.join(HERE, "prompts", "*.txt")))
    good_expected = not args
    agree = failed = 0
    for p in files:
        kind, ok, n, miss = check(p)
        verdict = "PASS" if ok == n else "FAIL"
        name = os.path.basename(p)
        flag = ""
        if good_expected:
            exp = "PASS" if name.endswith("_good.txt") else "FAIL"
            if exp == verdict:
                agree += 1
            else:
                flag = f"  <-- NIEZGODNE Z OCZEKIWANIEM ({exp})"
        if verdict == "FAIL":
            failed += 1
        print(f"{name:<24} [{kind:<6}] {ok}/{n}  {verdict}{flag}")
        for m, hint in miss:
            print(f"    brak: {m:<52} -> {hint}")
    if good_expected:
        print(f"\nSAMOTEST: {agree}/{len(files)} wyników zgodnych z sufiksem _bad/_good.")
        sys.exit(0 if agree == len(files) else 1)
    if strict:
        print(f"\nSTRICT: {failed} z {len(files)} promptów oblanych.")
        sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
