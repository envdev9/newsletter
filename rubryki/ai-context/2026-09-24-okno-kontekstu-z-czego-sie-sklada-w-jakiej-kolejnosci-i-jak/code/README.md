# Kod do wydania #1 — ile realnie kosztuje `cat` vs `grep`/`head` w kontekście

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam fragment + jak to
odpalić od zera i prawdziwy, faktycznie uruchomiony output.

Wymagania: **python3**, **bash** (żadnych zewnętrznych zależności).

## Fragment prasówki, którego dotyczy ten kod

> **`grep` zużył 619× mniej kontekstu niż `cat` całego pliku - i to `grep`, nie `head`,
> faktycznie znalazł sygnał.** To jest cała lekcja tej sekcji w jednej liczbie:
> intuicyjny odruch "wezmę pierwsze N linii, żeby nie przesadzić" bywa gorszy niż wzięcie
> całego pliku, bo nie trafia w to, co ważne - **filtrowanie pod kątem treści** (`grep`),
> nie **pozycji** (`head`), jest właściwym narzędziem do ograniczania kontekstu bez
> utraty sygnału.

## Pliki

- [`generate_log.py`](generate_log.py) — generuje deterministyczny (seed=42), syntetyczny
  log builda CI: 4000 linii szumu (restore/compile/testy OK) + 3 linie prawdziwego
  sygnału (2 błędy kompilacji, 1 nieudany test) wstrzyknięte w środek pliku.
- [`token_budget.py`](token_budget.py) — czyta tekst ze `stdin`, liczy znaki/linie i
  szacuje przybliżoną liczbę tokenów heurystyką ~4 znaki/token (**to nie jest** prawdziwy
  tokenizer Claude'a — ten jest zamknięty i oparty o BPE; to zgrubny, ale użyteczny rząd
  wielkości).
- [`compare_context_cost.sh`](compare_context_cost.sh) — generuje log i porównuje
  `cat`/`head -n 50`/`grep` pod kątem tego, ile z niego trafiłoby do kontekstu modelu.

## Jak odpalić od zera

```bash
cd code/
chmod +x compare_context_cost.sh generate_log.py token_budget.py
./compare_context_cost.sh
```

## Prawdziwy, uruchomiony output (bez skrótów)

```
== Generowanie syntetycznego logu builda ==
Wygenerowano: 4003 linii, 206086 bajtów -> build.log

==================================================================
1) cat całego pliku - tak jakby ktoś wrzucił cały log do kontekstu
==================================================================
linii:                  4003
znaków:               206086
~tokenów (heurystyka, 4 znaki/token):    51522

==================================================================
2) head -n 50 - pierwsze 50 linii pliku
==================================================================
linii:                    50
znaków:                 2570
~tokenów (heurystyka, 4 znaki/token):      642
--- czy w pierwszych 50 liniach jest jakikolwiek sygnał błędu? ---
(brak - sygnał jest głębiej w pliku, head go nie widzi)

==================================================================
3) grep -E 'error |FAILED' - tylko linie z faktycznym sygnałem
==================================================================
linii:                     3
znaków:                  333
~tokenów (heurystyka, 4 znaki/token):       83
--- treść, którą faktycznie widzi model ---
error CS0246: The type or namespace name 'IEmailSender' could not be found (are you missing a using directive or an assembly reference?) [Newsletter.Infra.csproj]
error CS1002: ; expected [Newsletter.Api.csproj]
Test 'Newsletter.Tests.Should_RejectInvalidSlug' FAILED: Expected <ArgumentException> but no exception was thrown (8 ms)

==================================================================
Podsumowanie: o ile mniej znaków trafia do kontekstu z grep niż z cat
==================================================================
cat:  206086 znaków
grep: 333 znaków
grep zużywa 619x mniej kontekstu niż cat całego pliku
```

## Użycie `token_budget.py` samodzielnie na dowolnym pliku

```bash
cat dowolny_plik.log | python3 token_budget.py
grep -n "ERROR" dowolny_plik.log | python3 token_budget.py
head -n 100 dowolny_plik.log | python3 token_budget.py
```

## Weryfikacja

Dokładne komendy uruchomione przy pisaniu tego wydania:

```bash
bash -n compare_context_cost.sh                     # składnia OK
python3 -m py_compile generate_log.py                # kompiluje się OK
python3 -m py_compile token_budget.py                 # kompiluje się OK
./compare_context_cost.sh                             # pełny, realny przebieg -> output wyżej
```

Plik `build.log` generowany przez `generate_log.py` **nie jest** trzymany w repo (to
wygenerowany artefakt, ~200 KB) — odtwarzalny w jednej komendzie, patrz wyżej.
