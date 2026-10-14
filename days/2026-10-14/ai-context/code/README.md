# Kod do wydania z 14.10 — powtórzone odczyty plików: dedupikacja przy zapisie vs retroaktywna (a cache)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Wymagania: **python3** (sprawdzono na 3.10.4), brak
zależności. Skrypt kopiuje `fixture/` do katalogu tymczasowego, wykonuje tam prawdziwe edycje i uruchamia
prawdziwe testy (`subprocess`), po czym sprząta. Pliki w `fixture/` to kopie z
[#20](../../../2026-10-13/ai-context/code/).

## Fragment artykułu, którego dotyczy ten kod

> Na 17-krokowej sesji (prawdziwe pliki, edycje, testy) wycinanie starych kopii pliku z kontekstu daje
> 2,44× mniej token-tur niż nic nie robić, ale po uwzględnieniu cache tylko 1,11× mniej kosztu. Polityka,
> która nie rusza historii, a przy ponownym odczycie zwraca stub („bez zmian”) albo unified diff, daje
> 1,94× mniej token-tur i 2,65× mniejszy koszt ważony cache. Przy tanim odczycie z cache (mnożnik ≤ 0,5)
> mutowanie historii się nie opłaca; bez cache — tak.
>
> **Sesja skryptowana, żaden model nie był uruchamiany; mnożniki cache (0,10/1,25) i baza 8000 tok. to
> założenia.** Zachowanie modelu z diffem/stubem — niezweryfikowane.

## Pliki

- [`ctxdedup.py`](ctxdedup.py) — sesja, polityki `none`/`retro`/`append`/`append+`, model kosztów cache,
  weryfikacja odtwarzalności, własny `make_diff`/`apply_diff` (na `difflib`).
- [`test_ctxdedup.py`](test_ctxdedup.py) — 30 asercji (diff, fuzz 300 edycji, polityki, niezmienniki,
  test negatywny).
- [`fixture/`](fixture/) — `ctxsearch.py`, `test_ctxsearch.py` (prawdziwe pliki robocze sesji).

## Jak odpalić

Z katalogu `code/` (flaga `-B` nie zostawia `__pycache__/`):

```bash
python3 -B ctxdedup.py run
python3 -B ctxdedup.py trace
python3 -B ctxdedup.py verify
python3 -B ctxdedup.py sweep
python3 -B ctxdedup.py cache
python3 -B ctxdedup.py show append
python3 -B test_ctxdedup.py
```

## Prawdziwy, uruchomiony output

`run`:

```
sesja: 17 krokow (8 odczytow, 4 edycji, 5 uruchomien testow), baza 8000 tok.
  ctxsearch.py           7962 tok. (31846 bajtow)
  test_ctxsearch.py      1289 tok. (5156 bajtow)

| polityka | kontekst koncowy | token-tury | vs none | zapis do cache (tok.) | koszt wazony | vs none | odtworzenie odczytow | stare pelne kopie (tok.) |
|---|---|---|---|---|---|---|---|---|
| none | 51915 | 574604 | 1.00x | 43915 | 107963 | 1.00x | 8/8 | 34390 |
| retro | 17611 | 235431 | 2.44x | 64228 | 97405 | 1.11x | 8/8 | 0 |
| append | 17763 | 295676 | 1.94x | 9763 | 40795 | 2.65x | 8/8 | 9238 |
| append+ | 17769 | 295705 | 1.94x | 9769 | 40805 | 2.65x | 8/8 | 9238 |
```

`sweep` (dodatkowe odczyty bez zmian): przy 20 powtórzeniach token-tury `none` 3 285 974, `append`/`none` 0,20,
`retro`/`none` 0,18; koszt ważony `append`/`none` 0,14, `retro`/`none` 0,56.

`cache` (mnożnik odczytu → najtańsza): 1,00 retro · 0,75 retro · 0,50 append · 0,25 append · 0,10 append ·
0,05 append (tu `retro` 88 845 > `none` 81 428).

`verify`: 8/8 odczytów odtworzonych z samego kontekstu dla każdej polityki, stan końcowy plików zgodny.

Test: `OK: 30 asercji, 0 niepowodzen`.

## Uczciwe ograniczenia

- Sesja skryptowana przez jednego autora; rozkład powtórzeń w prawdziwych sesjach nieznany (odczyt
  transkryptów odrzucony).
- Brak modelu: nie wiadomo, czy czyta diff poprawnie ani jak reaguje na stub. Kod sprawdza tylko
  mechaniczną odtwarzalność.
- Wyniki testów w sesji ważą 10 tok. (testy są zielone nawet po zmianie `k`) — `append+` nic tu nie zmienia.
- Zachowanie po `/compact` (wiszący stub) i narzędzia `claude` — niezweryfikowane. Próg diffu (50%) umowny;
  CRLF, brak końcowego `\n`, binaria nietestowane.
