# Kod do wydania z 19.10 — wiszący stub po kompakcji i deduplikacja wyników `grep`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Wymagania: **python3** (sprawdzono na 3.10.4), brak
zależności pip, polecenie `grep` w PATH (sprawdzono z ugrep 7.8.4; format `plik:numer:tekst` dla `-H -n`).
Skrypt kopiuje `fixture/` do katalogu tymczasowego, robi tam prawdziwe edycje, uruchamia prawdziwe testy
i `grep`, po czym sprząta.

## Fragment artykułu, którego dotyczy ten kod

> Narzędzie z #9 pamięta `last_seen` i przy ponownym odczycie zwraca stub albo diff. Kompakcja wycina z okna to,
> na co stub wskazuje. Wersja nieświadoma kompakcji (`ignore`) jest na sesji 2,11× tańsza (koszt ważony) niż brak
> dedupikacji, ale 4 z 14 wyników są nie do odtworzenia z okna. Poprawna wersja (`chain`: wpis ważny, gdy żyją
> wszystkie zdarzenia łańcucha: pełny odczyt + diffy) kosztuje 1,48× mniej niż brak dedupikacji i ma 0 błędów
> w 108 scenariuszach (kompakcja po każdym kroku × 6 długości ogona). Wariant `last` (sprawdza tylko ostatnie
> zdarzenie) zawodzi w 15 z 108.
>
> **Sesja skryptowana; kompakcja jest MODELOWANA (podsumowanie 510 tok. syntetyczne); żaden model nie był
> uruchamiany; mnożniki cache 0,10/1,25 i baza 8000 tok. to założenia z #9.** Zachowanie modelu i prawdziwego
> `/compact` — niezweryfikowane.

## Pliki

- [`ctxledger.py`](ctxledger.py) — sesja (prawdziwe edycje/testy/`grep`), modelowana kompakcja, polityki
  `none`/`ignore`/`epoch`/`last`/`chain` (+ warianty bez grep / tylko grep), mechaniczny test odtwarzalności
  (ok/dangling/wrong), przemiatanie pozycji kompakcji.
- [`test_ctxledger.py`](test_ctxledger.py) — 54 asercje, w tym testy negatywne (`ignore` i `last` MUSZĄ zawodzić).
- [`ctxdedup.py`](ctxdedup.py) — kopia z [#21](../../2026-10-14-ten-sam-plik-po-raz-piaty-dlaczego-wyrzuc-stare-odczyty-z/code/) (diff, `cost_of`, `tok`), importowana.
- [`fixture/`](fixture/) — `ctxsearch.py`, `test_ctxsearch.py` (pliki robocze sesji, kopie z #20/#21).

## Jak odpalić

Z katalogu `code/` (flaga `-B` nie zostawia `__pycache__/`):

```bash
python3 -B ctxledger.py run          # dwa scenariusze (ogon 0 i 6), wszystkie polityki
python3 -B ctxledger.py show chain 6 # zywe zdarzenia okna po sesji: polityka, ogon
python3 -B ctxledger.py show ignore 0
python3 -B ctxledger.py sweep        # 108 scenariuszy
python3 -B ctxledger.py verify       # exit 0 gdy bezpieczne polityki maja 0 bledow, a ignore/last > 0
python3 -B test_ctxledger.py         # ok. 1-2 min
```

## Prawdziwy, uruchomiony output

`run` (kompakcja przed turą 12 z 19; wycinek, kolumny: koszt ważony i odtwarzalność):

```
ogon po kompakcji: 0 zdarzen
| none | 361048 | 1.00x | 38122 | 79945 | 1.00x | 6/0/0 | 8/0/0 | 0 | 0 | 0 |
| ignore | 247041 | 1.46x | 11424 | 37842 | 2.11x | 4/2/0 | 6/2/0 | 2 | 2 | 117 |
| epoch | 313023 | 1.15x | 19715 | 53975 | 1.48x | 6/0/0 | 8/0/0 | 2 | 1 | 99 |
| last | 313023 | 1.15x | 19715 | 53975 | 1.48x | 6/0/0 | 8/0/0 | 2 | 1 | 99 |
| chain | 313023 | 1.15x | 19715 | 53975 | 1.48x | 6/0/0 | 8/0/0 | 2 | 1 | 99 |
| chain-bez-grep | 320189 | 1.13x | 21041 | 56216 | 1.42x | 6/0/0 | 8/0/0 | 2 | 1 | 0 |
| chain-tylko-grep | 353882 | 1.02x | 36796 | 77704 | 1.03x | 6/0/0 | 8/0/0 | 0 | 0 | 99 |

ogon po kompakcji: 6 zdarzen
| none | 428072 | 1.00x | 46500 | 96282 | 1.00x | 6/0/0 | 8/0/0 | 0 | 0 | 0 |
| ignore | 250305 | 1.71x | 11832 | 38637 | 2.49x | 4/2/0 | 6/2/0 | 2 | 2 | 117 |
| epoch | 316287 | 1.35x | 20123 | 54770 | 1.76x | 6/0/0 | 8/0/0 | 2 | 1 | 99 |
| last | 251005 | 1.71x | 11932 | 38822 | 2.48x | 4/2/0 | 8/0/0 | 2 | 2 | 113 |
| chain | 314565 | 1.36x | 19877 | 54315 | 1.77x | 6/0/0 | 8/0/0 | 2 | 1 | 113 |
```

(Kolejność kolumn: token-tury, vs none, zapis do cache, koszt ważony, vs none, odczyty ok/dangling/wrong,
grep ok/dangling/wrong, diffy, stuby, pominięte linie grep.)

`sweep`:

```
| none | 108 | 0 | 0 | 1512 | 1.00 |
| ignore | 108 | 91 | 354 | 1512 | 0.45 |
| epoch | 108 | 0 | 0 | 1512 | 0.58 |
| last | 108 | 15 | 20 | 1512 | 0.54 |
| chain | 108 | 0 | 0 | 1512 | 0.55 |
| chain-bez-grep | 108 | 0 | 0 | 1512 | 0.59 |
| chain-tylko-grep | 108 | 0 | 0 | 1512 | 0.97 |
```

`verify`: `OK` (exit 0). Test: `OK: 54 asercji, 0 niepowodzen`.

## Uczciwe ograniczenia

- Kompakcja modelowana, nie obserwowana: nie wiem, co przeżywa prawdziwy `/compact`, ani co zawiera podsumowanie.
- Żaden model nie był uruchamiany: „dangling/wrong” to test mechaniczny (czy wynik da się złożyć z tekstu okna),
  nie dowód, że model się pomyli.
- Jedna 19-krokowa sesja i dwa pliki; „0 błędów” nie jest dowodem ogólnym. Wyniki `grep` są małe (385 tok.),
  więc zysk z ich dedupikacji jest niewielki; `ls` i `grep -r` po dużym repo — nietestowane.
- Skąd zewnętrzne narzędzie dowiaduje się o kompakcji (haki `claude`?) — niezweryfikowane, żywej sesji nie uruchamiano.
- Mnożniki cache (0,10/1,25) i baza 8000 tok. — założenia z #9.
