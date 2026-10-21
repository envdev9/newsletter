# Kod do wydania z 21.10 — `ls -R`: delta per sekcja, projekcja poddrzewa, kompakcja okna (chain vs carry)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Wymagania: **python3** (sprawdzono na 3.10.4), brak zależności pip,
GNU `ls` w PATH (sprawdzono z coreutils 8.32; flagi: `-R`, `-lAog --time-style=long-iso`, `LC_ALL=C`, `TZ=UTC`).
Skrypt tworzy drzewo w `/tmp/lsepoch-*`, robi na nim prawdziwe edycje/create/delete/rename/symlinki/„build”, woła prawdziwy
`ls` i sprząta (`rmtree` w `finally`; brak pozostałości nie został osobno sprawdzony).

## Fragment artykułu, którego dotyczy ten kod

> Na prawdziwym drzewie (17 katalogów, 167 wpisów, pełny `ls -R` = 1 954 tok.) sesja 18 tur kosztuje 30 011 tok. bez
> optymalizacji, 5 231 z deltą (5,74×) i 3 162 z deltą + projekcją poddrzewa (9,49×), przy 0 błędów odtworzenia. Po
> kompakcji okna delty wiszą (42 z 51 scenariuszy z błędem); lenistwo („wyślij pełną sekcję przy następnym `ls`”, `chain`)
> naprawia to za 4,45×, a zaszycie stanu w podsumowaniu (`carry`) za 3,89× — oba z 0 błędów. `ls -t` z czasem w minutach nie da
> się odtworzyć z tekstu (0/40), `ls -S` da się (40/40).
>
> **Sesja skryptowana (18 tur), drzewo i `ls` prawdziwe, mtime ustawiany `os.utime`; żaden model nie był uruchamiany;
> tokeny = bajty/4.** Zachowanie modelu i możliwość wpięcia takiej warstwy w `claude` — niezweryfikowane.

## Pliki

- [`lsepoch.py`](lsepoch.py) — sandbox z prawdziwym drzewem, 7 polityk (`none`/`same`/`gdelta`/`sdelta`/`proj`/`chain`/`carry`),
  `Window` budowane wyłącznie z tekstu wyników (po kompakcji: z tego, co przeżyło), komendy `run`, `show`, `sweep`,
  `compsweep`, `order`, `verify`.
- [`test_lsepoch.py`](test_lsepoch.py) — 171 asercji: parser, `prune`, fuzz (25 losowych sesji, 127 przebiegów polityk, 1 778
  porównań listing==okno), testy negatywne (bez świadomości kompakcji MUSI się mylić), kolejność `-t`/`-S`.

## Jak odpalić

Z katalogu `code/` (`-B` nie zostawia `__pycache__/`):

```bash
python3 -B lsepoch.py run                          # 3 tabele: bez kompakcji, kompakcja ogon 0, kompakcja ogon 4
python3 -B lsepoch.py run --mods 40                # większe drzewo
python3 -B lsepoch.py show proj --text             # tura po turze, z treścią delt/stubów
python3 -B lsepoch.py show chain --comp 10 --tail 0   # kompakcja przed turą 10
python3 -B lsepoch.py sweep                        # skala: 4 / 12 / 40 / 120 modułów
python3 -B lsepoch.py compsweep                    # kompakcja przed każdą turą 2..18 x ogon {0,3,6}
python3 -B lsepoch.py compsweep --list chain       # które scenariusze zawodzą dla danej polityki
python3 -B lsepoch.py order                        # czy kolejność ls -t / -S da się odtworzyć z tekstu
python3 -B lsepoch.py verify                       # exit 0 = bezpieczne polityki bez błędów, negatywne się mylą
python3 -B test_lsepoch.py                         # kilkadziesiąt sekund
```

## Prawdziwy, uruchomiony output

`run` (fragment, bez kompakcji):

```
drzewo proj: 17 katalogow, 167 wpisow, pelny `ls -R` = 1954 tok.; sesja 18 tur
| none | 30011 | 1.00x | 284009 | 1.00x | 0/0/18 | - |
| same | 24134 | 1.24x | 241093 | 1.18x | 3/0/15 | - |
| gdelta | 5231 | 5.74x | 67694 | 4.20x | 3/9/6 | - |
| sdelta | 5231 | 5.74x | 67694 | 4.20x | 3/9/6 | - |
| proj | 3162 | 9.49x | 49343 | 5.76x | 5/12/1 | - |
```

Kompakcja przed turą 10, ogon 0 (kolumny: tokeny, vs none, token-tury, vs none, stub/delta/full, błędne tury):

```
| gdelta | 5741 | 5.32x | 41999 | 3.92x | 3/9/6 | [10,12,13,14,16,17,18] |
| proj | 3672 | 8.31x | 27320 | 6.02x | 5/12/1 | [10,11,12,13,14,15,16,17,18] |
| chain | 6368 | 4.79x | 51584 | 3.19x | 5/11/2 | - |
| carry | 6406 | 4.76x | 51926 | 3.17x | 5/12/1 | - |
```

`sweep`:

```
| 4 | 927 | 15973 | 2190 | 7.29x | 4.90x | 4.90x |
| 12 | 1954 | 30011 | 3162 | 9.49x | 5.74x | 5.74x |
| 40 | 5546 | 80288 | 6754 | 11.89x | 6.47x | 6.47x |
| 120 | 15817 | 224093 | 17026 | 13.16x | 6.80x | 6.80x |
```

`compsweep` (51 scenariuszy = kompakcja przed turą 2..18 × ogon {0,3,6}):

```
| none | 51 | 0 | 0 | 11665017 | 1.00x |
| same | 51 | 3 | 3 | 9970562 | 1.17x |
| gdelta | 51 | 42 | 243 | 2773572 | 4.21x |
| sdelta | 51 | 42 | 243 | 2773572 | 4.21x |
| proj | 51 | 42 | 324 | 1965408 | 5.94x |
| chain | 51 | 0 | 0 | 2619728 | 4.45x |
| carry | 51 | 0 | 0 | 2997312 | 3.89x |
```

`order`:

```
| ls -t | long-iso | 0/40 | 1558 |
| ls -S | long-iso | 40/40 | 1558 |
| ls -t | full-iso | 40/40 | 2280 |
| ls -S | full-iso | 40/40 | 2280 |
```

`verify`: `OK`. Test: `fuzz: 127 sesji, 1778 porownan listing==okno` oraz `OK: 171 asercji, 0 niepowodzen`.

## Uczciwe ograniczenia

- Sesja skryptowana, 18 tur dobranych przeze mnie; rozkład wywołań `ls -R` w prawdziwych sesjach nieznany.
- Żaden model nie był uruchamiany: „odtwarzalność” to test mechaniczny (listing==okno). Stub „identyczny z turą N” dla
  poddrzewa wskazuje turę ostatniej zmiany **całego** drzewa, a nie turę, z której pochodzi dana sekcja — model musi to
  poskładać sam; czy to robi — nie wiem.
- mtime ustawiany `os.utime` na `T0 + 60*tura` (także katalogów); w prawdziwym buildzie czasy są losowe.
- Kompakcja tylko modelowana (podsumowanie stałe 510 tok.; ogon = wyniki z ostatnich K tur); nie sprawdzałem, jak robi to `claude`.
- Remisy w testach `-t`/`-S` są wygenerowane losowo (≈152 plików w oknie 8 minut); to nie jest rozkład z prawdziwego repo.
- Nietestowane: nazwy z nową linią i z `" -> "`, BSD `ls`, inne systemy plików, `ls -R` z `-L`/`-d`, bardzo głębokie drzewa.
