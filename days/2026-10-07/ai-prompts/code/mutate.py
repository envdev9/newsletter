#!/usr/bin/env python3
"""Mini-test mutacyjny dla Billing/Prorator.cs (stdlib, bez pip).

Kopiuje projekt do katalogu tymczasowego, dla kazdego mutanta podmienia JEDEN fragment w
Prorator.cs i uruchamia zestawy testow (`dotnet run --project ...`, TUnit/MTP).
Mutant "zabity"  = zestaw testow sie wywalil (exit != 0, brak bledu kompilacji).
Mutant "przezyl" = wszystkie testy zielone mimo zmiany zachowania => dziura w testach.
Mutant "niekompilowalny" = nie liczy sie do wyniku.

Uzycie (z dowolnego katalogu):
  python3 -B mutate.py                       # tabela dla obu zestawow
  python3 -B mutate.py --survivors-out F.md  # + raport przezylych mutantow gotowy do wklejenia do promptu
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SUBJECT = os.path.join("Billing", "Prorator.cs")
SUITES = ["Billing.NaiveTests", "Billing.GoodTests"]

# (id, opis, fragment oryginalny, zamiennik, uwaga o rownowaznosci)
MUTANTS = [
    ("M01", "Charge: `activation <= first` -> `<` (aktywacja 1. dnia)",
     "activation <= first", "activation < first",
     "ROWNOWAZNY: dla 1. dnia wzor daje cena*dni/dni == cena, wynik identyczny"),
    ("M02", "Charge: `activation > last` -> `>=` (ostatni dzien => 0)",
     "activation > last", "activation >= last", ""),
    ("M03", "Charge: usuniete `+ 1` (dni liczone wlacznie)",
     "- activation.DayNumber + 1;", "- activation.DayNumber;", ""),
    ("M04", "Charge: AwayFromZero -> ToEven",
     "Math.Round(v, 2, MidpointRounding.AwayFromZero)", "Math.Round(v, 2, MidpointRounding.ToEven)", ""),
    ("M05", "Charge: `monthlyPrice < 0` -> `<= 0` (cena 0 rzuca)",
     "if (monthlyPrice < 0)", "if (monthlyPrice <= 0)", ""),
    ("M06", "Charge: stala liczba dni 30 zamiast DaysInMonth",
     "DateTime.DaysInMonth(year, month)", "30", ""),
    ("M07", "Charge: zaokraglenie do 3 miejsc zamiast 2",
     "Math.Round(v, 2, MidpointRounding", "Math.Round(v, 3, MidpointRounding", ""),
    ("M08", "Charge: kolejnosc dzialan cena/dni*pozostale zamiast cena*pozostale/dni",
     "monthlyPrice * remaining / daysInMonth", "monthlyPrice / daysInMonth * remaining",
     "MOZE BYC ROWNOWAZNY po zaokragleniu do groszy (decimal ma 28 cyfr)"),
    ("M09", "Split: `i < rem` -> `i <= rem` (jedna pozycja z nadwyzka za duzo)",
     "i < rem ? 1 : 0", "i <= rem ? 1 : 0", ""),
    ("M10", "Split: reszta groszy do OSTATNICH pozycji zamiast pierwszych",
     "i < rem ? 1 : 0", "i >= parts - rem ? 1 : 0",
     "Suma i rozrzut <= 1 gr zachowane - tylko kontrakt 'do pierwszych' to odroznia"),
    ("M11", "Split: `parts <= 0` -> `parts < 0` (parts=0 => DivideByZero zamiast ArgumentOutOfRange)",
     "if (parts <= 0)", "if (parts < 0)", ""),
    ("M12", "Split: usunieta walidacja >2 miejsc po przecinku",
     "if (total != Round(total))", "if (false)", ""),
    ("M13", "Split: `total < 0` -> `total < -1000` (walidacja kwoty ujemnej oslabiona)",
     "if (total < 0)", "if (total < -1000)", ""),
    ("M14", "Split: `cents % parts` -> `cents % (parts + 1)` (zla reszta)",
     "cents % parts", "cents % (parts + 1)", ""),
]


def run_suite(workdir, suite):
    p = subprocess.run(
        ["dotnet", "run", "--project", os.path.join(workdir, suite),
         "--results-directory", os.path.join(workdir, "results")],
        capture_output=True, text=True, timeout=600)
    out = p.stdout + p.stderr
    if re.search(r"error CS\d+", out):
        return "build-error", out
    return ("pass" if p.returncode == 0 else "fail"), out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--survivors-out", help="zapisz raport przezylych mutantow (Markdown) do pliku")
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="mutation-")
    work = os.path.join(tmp, "code")
    shutil.copytree(HERE, work, ignore=shutil.ignore_patterns("bin", "obj", "__pycache__", "prompts"))
    src_path = os.path.join(work, SUBJECT)
    with open(src_path, encoding="utf-8") as f:
        original = f.read()

    for old_id, desc, old, new, _ in MUTANTS:
        if original.count(old) != 1:
            sys.exit(f"{old_id}: fragment musi wystapic dokladnie raz ({original.count(old)}x): {old!r}")

    print(f"katalog roboczy: {tmp}")
    print("baseline (kod bez mutacji):")
    for s in SUITES:
        status, out = run_suite(work, s)
        print(f"  {s}: {status}")
        if status != "pass":
            print(out)
            sys.exit("baseline musi byc zielony - przerywam")

    results = {s: {} for s in SUITES}
    for mid, desc, old, new, _ in MUTANTS:
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(original.replace(old, new, 1))
        row = []
        for s in SUITES:
            status, _ = run_suite(work, s)
            results[s][mid] = status
            row.append(status)
        print(f"{mid}  naive={row[0]:<11} good={row[1]:<11} {desc}", flush=True)

    with open(src_path, "w", encoding="utf-8") as f:
        f.write(original)

    print()
    print("PODSUMOWANIE (mutanty niekompilowalne pominiete)")
    for s in SUITES:
        valid = [m for m in results[s] if results[s][m] != "build-error"]
        killed = [m for m in valid if results[s][m] == "fail"]
        surv = [m for m in valid if results[s][m] == "pass"]
        score = 100.0 * len(killed) / len(valid) if valid else 0.0
        print(f"  {s}: zabite {len(killed)}/{len(valid)} = {score:.0f}%  przezyly: {', '.join(surv) or '-'}")

    if args.survivors_out:
        write_survivors(args.survivors_out, results)
        print(f"raport przezylych mutantow (naive): {args.survivors_out}")


def write_survivors(path, results):
    lines = ["# Raport mutacyjny (zestaw: Billing.NaiveTests)", "",
             "Ponizsze zmiany w kodzie produkcyjnym NIE zostaly wykryte przez zaden test.",
             "Dla kazdej: dopisz test, ktory na oryginale jest zielony, a na zmutowanym kodzie czerwony.",
             "Jesli uwazasz, ze mutant jest rownowazny (zachowanie identyczne), uzasadnij to w jednym zdaniu",
             "zamiast pisac test. Nie zmieniaj kodu produkcyjnego.", ""]
    n = 0
    for mid, desc, old, new, note in MUTANTS:
        if results["Billing.NaiveTests"].get(mid) == "pass":
            n += 1
            lines += [f"## {mid}: {desc}", "```diff", f"- {old}", f"+ {new}", "```", ""]
    lines.insert(2, f"Przezylo {n} mutantow.")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
