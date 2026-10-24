# Kod do wydania #1 — pary zły/dobry prompt

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam materiał w formie
uruchamialnej + jak go zweryfikować.

## Fragment prasówki, którego dotyczy ten kod

> Poniżej 5 par zły/dobry prompt, każda z jedną konkretną przyczyną, dlaczego druga
> wersja działa lepiej. Wszystkie pary są w `code/examples.yaml`, zwalidowane i
> wypisane skryptem `code/print_examples.py`.

## Struktura

```
code/
├── examples.yaml        # 5 par zły/dobry prompt + kategoria + uzasadnienie
└── print_examples.py    # waliduje examples.yaml i (bez --check) ładnie je wypisuje
```

`examples.yaml` to lista wpisów, każdy z polami: `id`, `kategoria`, `zly`, `dobry`,
`dlaczego` — wszystkie muszą być obecne i niepuste, inaczej skrypt kończy się
błędem (kod wyjścia != 0) zamiast cichego pominięcia braku.

## Jak uruchomić

Wymaganie: Python 3 + PyYAML (`pip install pyyaml`, u nas już zainstalowane —
`PyYAML 5.4.1`).

```bash
cd days/2026-09-24/ai-prompts/code

# Tylko walidacja (przydatne w CI) - bez pełnego wydruku
python3 print_examples.py --check

# Pełny, sformatowany wydruk wszystkich par
python3 print_examples.py
```

## Weryfikacja — rzeczywisty output

### `python3 print_examples.py --check`

```
$ python3 print_examples.py --check
WYNIK: 5/5 przykładów poprawnych.
$ echo "exit: $?"
exit: 0
```

### `python3 print_examples.py` (pełny wydruk, fragment)

```
Znaleziono 5 przykładów w examples.yaml

========================================================================================
[1] Konkretność + wskazanie plików/linii
----------------------------------------------------------------------------------------
    ❌ ZŁY PROMPT:
    Popraw bug w serwisie userów.

    ✅ DOBRY PROMPT:
    W src/Services/UserService.cs, metoda GetActiveUsersAsync (linie 42-58) zwraca też
    użytkowników z IsDeleted=true, bo w zapytaniu LINQ brakuje warunku. Dodaj .Where(u
    => !u.IsDeleted) przed .ToListAsync() i pokaż diff.

    💡 DLACZEGO:
    "Serwis userów" i "bug" to dwie niewiadome naraz - model musi najpierw przeszukać
    repo i zgadnąć, o który plik i o jaki objaw chodzi. Konkretny plik, zakres linii i
    dokładny opis efektu (co dokładnie wraca, a nie powinno) zmieniają to w zadanie
    jednoznaczne do wykonania za pierwszym razem, bez rundy pytań.

========================================================================================
[2] Podawanie 'dlaczego', nie tylko 'co'
----------------------------------------------------------------------------------------
    ❌ ZŁY PROMPT:
    Zmień timeout w HttpClient na 30 sekund.

    ✅ DOBRY PROMPT:
    Zwiększ timeout HttpClient w OrderApiClient.cs z 10s na 30s - integracja z API
    dostawcy potrafi odpowiadać 15-20s przy dużych zamówieniach, obecny timeout powoduje
    false-positive TimeoutException na produkcji (log w Seq, correlationId widoczny w
    tickecie). Zmień tylko dla tego klienta, nie globalnie w Program.cs.

    💡 DLACZEGO:
    Sama wartość liczbowa bez przyczyny zamienia model w maszynkę do znajdź-i-zamień -
    nie może ocenić, czy 30s to bezpieczna wartość, czy lepszym rozwiązaniem byłaby
    retry policy zamiast samego zwiększenia timeoutu, ani czy zmiana ma dotyczyć jednego
    klienta czy całej aplikacji. Podanie przyczyny daje modelowi dane do podjęcia
    właściwej decyzji, nie tylko wykonania polecenia.

[... pary 3, 4, 5 analogicznie - pełny output identyczny z ARTICLE.md ...]

========================================================================================

WYNIK: 5/5 przykładów poprawnych (pola id/kategoria/zly/dobry/dlaczego obecne i niepuste).
```

Pełny, nieskrócony output (wszystkie 5 par) został uruchomiony lokalnie przed
publikacją (`python3 3.10.4`, `PyYAML 5.4.1`) i jest identyczny co do treści z
przykładami w [`../ARTICLE.md`](../ARTICLE.md).

### Test negatywny — walidacja faktycznie wykrywa błędy

Żeby potwierdzić, że `--check` nie jest atrapą, uruchomiono go na kopii
`examples.yaml` z wyczyszczonym polem `dlaczego` w pierwszym wpisie (plik
tymczasowy poza repo, nieujęty w commicie):

```
$ python3 print_examples_test.py --check
WALIDACJA NIEUDANA: 1 błąd(ów):
  - przykład #0 (id=1): brak/puste pole 'dlaczego'
$ echo "exit: $?"
exit: 1
```

Potwierdza, że skrypt realnie sprawdza kompletność każdego przykładu, a nie tylko
parsuje YAML.
