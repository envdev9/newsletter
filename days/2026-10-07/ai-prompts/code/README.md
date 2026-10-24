# Kod do wydania #14 — prompty do generowania testów, oceniane mutacjami

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Prompt „napisz testy" daje zielone testy ścieżki szczęśliwej. Dobry prompt zawiera **kontrakt**
> (testuj specyfikację, nie implementację), **listę przypadków brzegowych**, **typy wyjątków**,
> **testy właściwości ze stałym ziarnem i liczbą iteracji**, **zakaz słabych asercji**, zakaz zmiany
> kodu produkcyjnego i **weryfikację zmianą operatora**. Jakość testów mierzymy mutacjami: `mutate.py`
> podmienia po jednym fragmencie `Prorator.cs` i sprawdza, czy któryś test się czerwieni. Dla 14 mutantów
> „naiwny" zestaw (5 testów) zabił 2 (14%), „dobry" (24 testy) 12 (86%); dwa przeżyte (M01, M08) uznane
> za równoważne (M08 — z domysłu). **Obie paczki testów napisałem ręcznie — żaden model nie był
> uruchamiany**, więc wynik mówi o testach, nie o promptach.

## Struktura

```
code/
├── global.json                 # runner Microsoft.Testing.Platform (dla `dotnet test`)
├── Billing/                    # kod pod testami: Prorator.Charge / Prorator.Split
├── Billing.NaiveTests/         # 5 testów — symulacja wyniku promptu „napisz testy" (ręczna!)
├── Billing.GoodTests/          # 24 testy — wg listy z dobrego promptu (ręczne!)
├── mutate.py                   # test mutacyjny: 14 mutantów, kopiuje projekt do /tmp
├── testprompt_lint.py          # lint promptów tests_/mutfix_ (część reguł sprawdza prompt vs kod)
├── prompts/                    # tests_bad/good, mutfix_bad/good
└── negative/                   # prompt „pusty w środku" (hasła bez treści)
```

## Jak uruchomić

Wymagania: .NET SDK (użyto 10.0.400), Python 3 (stdlib), dostęp do NuGet (TUnit 1.72.16). Ścieżki
względem katalogu głównego repo; `-B` = bez `__pycache__`.

```bash
dotnet run --project days/2026-10-07/ai-prompts/code/Billing.NaiveTests --results-directory /tmp/prompts-results
dotnet run --project days/2026-10-07/ai-prompts/code/Billing.GoodTests --results-directory /tmp/prompts-results

python3 -B days/2026-10-07/ai-prompts/code/mutate.py
python3 -B days/2026-10-07/ai-prompts/code/mutate.py --survivors-out /tmp/survivors.md

python3 -B days/2026-10-07/ai-prompts/code/testprompt_lint.py
python3 -B days/2026-10-07/ai-prompts/code/testprompt_lint.py --strict days/2026-10-07/ai-prompts/code/negative/tests_hollow_good.txt
```

`mutate.py` trwa kilka–kilkanaście minut (28 przebiegów `dotnet run` z budowaniem). Nie rusza
plików w repo — pracuje na kopii w katalogu tymczasowym. Alternatywa `dotnet test --project ...`
działa tylko z katalogu `code/` (tam jest `global.json`); w tej sesji użyto `dotnet run`.

## Weryfikacja — rzeczywisty output (uruchomione 2026-10-07, .NET 10.0.400)

### Testy (exit 0)

```
Test run summary: Passed! - .../Billing.NaiveTests.dll (net10.0|x64)
  total: 5
  failed: 0
  succeeded: 5
  skipped: 0
  duration: 1s 322ms
```

```
Test run summary: Passed! - .../Billing.GoodTests.dll (net10.0|x64)
  total: 24
  failed: 0
  succeeded: 24
  skipped: 0
  duration: 1s 809ms
```

### Test mutacyjny (`mutate.py`, exit 0)

```
baseline (kod bez mutacji):
  Billing.NaiveTests: pass
  Billing.GoodTests: pass
M01  naive=pass        good=pass        Charge: `activation <= first` -> `<` (aktywacja 1. dnia)
M02  naive=pass        good=fail        Charge: `activation > last` -> `>=` (ostatni dzien => 0)
M03  naive=fail        good=fail        Charge: usuniete `+ 1` (dni liczone wlacznie)
M04  naive=pass        good=fail        Charge: AwayFromZero -> ToEven
M05  naive=pass        good=fail        Charge: `monthlyPrice < 0` -> `<= 0` (cena 0 rzuca)
M06  naive=pass        good=fail        Charge: stala liczba dni 30 zamiast DaysInMonth
M07  naive=pass        good=fail        Charge: zaokraglenie do 3 miejsc zamiast 2
M08  naive=pass        good=pass        Charge: kolejnosc dzialan cena/dni*pozostale zamiast cena*pozostale/dni
M09  naive=fail        good=fail        Split: `i < rem` -> `i <= rem` (jedna pozycja z nadwyzka za duzo)
M10  naive=pass        good=fail        Split: reszta groszy do OSTATNICH pozycji zamiast pierwszych
M11  naive=pass        good=fail        Split: `parts <= 0` -> `parts < 0` (parts=0 => DivideByZero zamiast ArgumentOutOfRange)
M12  naive=pass        good=fail        Split: usunieta walidacja >2 miejsc po przecinku
M13  naive=pass        good=fail        Split: `total < 0` -> `total < -1000` (walidacja kwoty ujemnej oslabiona)
M14  naive=pass        good=fail        Split: `cents % parts` -> `cents % (parts + 1)` (zla reszta)

PODSUMOWANIE (mutanty niekompilowalne pominiete)
  Billing.NaiveTests: zabite 2/14 = 14%  przezyly: M01, M02, M04, M05, M06, M07, M08, M10, M11, M12, M13, M14
  Billing.GoodTests: zabite 12/14 = 86%  przezyly: M01, M08
```

### Lint promptów — samotest (exit 0)

```
mutfix_bad.txt           [mutfix] 0/9  FAIL
mutfix_good.txt          [mutfix] 9/9  PASS
tests_bad.txt            [tests ] 0/13  FAIL
tests_good.txt           [tests ] 13/13  PASS

SAMOTEST: 4/4 wyników zgodnych z sufiksem _bad/_good.
```

(Pełny output zawiera też listę brakujących reguł dla każdego „złego" promptu — uruchom skrypt.)

### Test negatywny — prompt „pusty w środku" (`--strict`, exit 1)

```
tests_hollow_good.txt    [tests ] 2/13  FAIL
    brak: wskazany plik .cs istnieje w repo
    brak: polecenie `dotnet run --project X` z istniejącym projektem
    brak: wskazane metody istnieją w kodzie
    brak: kontrakt/specyfikacja
    brak: wyjątki z kontraktu = wyjątki z XML-doc
    brak: >= 6 kategorii przypadków brzegowych
    brak: właściwości + ziarno + min. N iteracji
    brak: zakaz słabych asercji (z przykładem)
    brak: oczekiwanie liczone ręcznie, nie z implementacji
    brak: zakaz zmiany kodu produkcyjnego
    brak: weryfikacja: zmień operator -> test czerwony

STRICT: 1 z 1 promptów oblanych.
```

(Skrócone: pominięto dopiski „-> podpowiedź" z każdej linii.)

## Co NIE jest zweryfikowane

- Że model z `tests_good.txt` napisze testy zbliżone do `Billing.GoodTests` — **żaden model nie był uruchamiany**;
  obie paczki testów napisał człowiek (autor), naiwny zestaw znając listę mutantów (obciążenie wyniku).
- Że 14 mutantów jest reprezentatywne (to mój wybór; nie użyto Stryker.NET). M01 jest równoważny
  z analizy, M08 uznany za równoważny z domysłu — nie dowiedziony.
- Treść pliku `--survivors-out` (zapisał się w `/tmp`, ale jego odczyt został odrzucony przez środowisko).
- `dotnet test` z `global.json` (użyto `dotnet run`; pierwsza próba `dotnet test --project` spoza katalogu
  `code/` dała `MSB1001: Unknown switch`).
- Czas całego przebiegu `mutate.py` — nie zmierzony dokładnie.
- Wartość lintu: reguły dobrane pod własne prompty i własny kod, łatwo je oszukać.
- Generowanie dokumentacji (XML-doc, README, ADR) — nieporuszone.
