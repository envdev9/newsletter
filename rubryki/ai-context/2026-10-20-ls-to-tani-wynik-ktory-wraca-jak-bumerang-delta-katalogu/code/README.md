# Kod do wydania z 20.10 — deduplikacja wyników `ls` (delta katalogu, rzut `-1A` z `-lA`)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Wymagania: **python3** (sprawdzono na 3.10.4), brak zależności pip,
GNU `ls` w PATH (sprawdzono z coreutils 8.32; używane flagi: `-1A`, `-lAog --time-style=long-iso`, `LC_ALL=C`).
Skrypt tworzy katalog w `/tmp`, robi tam prawdziwe edycje/create/delete/rename, woła prawdziwy `ls` i sprząta.

## Fragment artykułu, którego dotyczy ten kod

> Na prawdziwym katalogu (152 wpisy) delta zamiast pełnych kopii wyniku `ls` daje 4,12× mniej tokenów (2,46× w token-turach,
> 3,18× w koszcie ważonym cache) i 0 błędów odtworzenia listingu z tekstu okna. Samo „identyczny → stub” daje tylko 1,22×.
> Polityka `evented` (nie wołam `ls`, bo sam nic nie zmieniłem) oszczędza 0,1% i myli się raz na 11, bo build zmienił katalog
> poza wiedzą agenta. `ls -l` nie widzi edycji o tym samym rozmiarze w tej samej minucie.
>
> **Sesja skryptowana (17 tur); filesystem i `ls` prawdziwe; żaden model nie był uruchamiany; tokeny = bajty/4; mnożniki cache
> 0,10/1,25 to założenia z #9.** Zachowanie modelu i możliwość wpięcia takiej warstwy w `claude` — niezweryfikowane.

## Pliki

- [`lsdelta.py`](lsdelta.py) — sesja na prawdziwym katalogu, 6 polityk (`none`/`same`/`setdiff`/`namekey`/`state`/`evented`),
  `Window` odtwarzający listing wyłącznie z tekstu wyników, koszty (tokeny, token-tury, koszt ważony), komendy `run`, `show`,
  `sweep`, `verify`, `demo`.
- [`test_lsdelta.py`](test_lsdelta.py) — 4 545 asercji, w tym fuzz (60 losowych sesji) i test negatywny (`evented` MUSI zawieść).

## Jak odpalić

Z katalogu `code/` (flaga `-B` nie zostawia `__pycache__/`):

```bash
python3 -B lsdelta.py run              # tabela polityk, katalog 152 wpisy
python3 -B lsdelta.py run --n 500      # inny rozmiar katalogu src
python3 -B lsdelta.py show namekey     # tura po turze: forma wyniku, tokeny, ewentualny BLAD
python3 -B lsdelta.py sweep            # skala: 22 / 152 / 502 / 2002 wpisow
python3 -B lsdelta.py demo             # edycja tego samego rozmiaru niewidoczna w ls -l
python3 -B lsdelta.py verify           # exit 0: bezpieczne polityki bez bledow, evented z bledem
python3 -B test_lsdelta.py             # kilkadziesiat sekund
```

## Prawdziwy, uruchomiony output

`run`:

```
katalog src: 152 wpisow, sesja 17 tur; mnozniki cache 0.1/1.25 (zalozenie)
| none | 10557 | 1.00x | 95990 | 1.00x | 21740 | 1.00x | 11/11 | 0/0/11/0 | - |
| same | 8626 | 1.22x | 92358 | 1.04x | 19156 | 1.13x | 11/11 | 2/0/9/0 | - |
| setdiff | 2612 | 4.04x | 39252 | 2.45x | 6929 | 3.14x | 11/11 | 2/6/3/0 | - |
| namekey | 2572 | 4.10x | 38975 | 2.46x | 6855 | 3.17x | 11/11 | 2/6/3/0 | - |
| state | 2564 | 4.12x | 38943 | 2.46x | 6843 | 3.18x | 11/11 | 2/6/3/0 | - |
| evented | 2564 | 4.12x | 38901 | 2.47x | 6839 | 3.18x | 10/11 | 1/5/3/2 | [9] |
```

(kolumny: tokeny, vs none, token-tury, vs none, koszt ważony, vs none, listingi odtworzone/wszystkie, stub/delta/full/skip,
tury z błędem)

`sweep`:

```
| 22 | 2107 | 809 | 2.60x | 4255 | 1984 | 2.14x |
| 152 | 10557 | 2564 | 4.12x | 21740 | 6843 | 3.18x |
| 502 | 33310 | 7290 | 4.57x | 68822 | 19927 | 3.45x |
| 2002 | 133066 | 28042 | 4.75x | 275320 | 77394 | 3.56x |
```

`demo`: linia `Mod007.cs` przed i po edycji identyczna, sha256 treści różny. `verify`: `OK`.
Test: `fuzz: 60 sesji, 4528 porownan listing==okno` oraz `OK: 4545 asercji, 0 niepowodzen`.

## Uczciwe ograniczenia

- Sesja skryptowana, 11 listingów w 17 turach dobranych przeze mnie; rozkład w prawdziwych sesjach nieznany.
- Żaden model nie był uruchamiany: „odtwarzalność” to test mechaniczny (listing==okno), nie dowód, że model się nie pomyli.
- Delta nie zachowuje kolejności (listing porównywany jako posortowany zbiór linii); `ls -t`/`-S`, `ls -R`, symlinki,
  nazwy z nową linią, BSD `ls` i inne systemy plików — nietestowane. Kompakcja okna dla delt `ls` — niemodelowana.
- Zmiana mtime w teście „tej samej minuty” wymuszona `os.utime` (symulacja).
- Mnożniki cache 0,10/1,25 i model kosztu append-only — założenia z #9.
