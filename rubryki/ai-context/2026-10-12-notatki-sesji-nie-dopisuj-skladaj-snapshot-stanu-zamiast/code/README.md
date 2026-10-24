# Kod do wydania z 12.10 — snapshot stanu zamiast dopisywania (fold) + weryfikator snapshotu

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Wymagania: **python3** (sprawdzono na 3.10.4),
brak zależności. Nic nie jest zapisywane na dysk (skrypty tylko czytają i drukują).

## Fragment artykułu, którego dotyczy ten kod

> Strumień 300 zdarzeń (SYNTETYCZNY, typy `SET/DEL/ADD/RM/INC`) daje stan końcowy 42 elementów.
> Log w całości: 6037 tok., snapshot: 565 tok. (10,7x). Naiwny czytelnik (pierwsza wzmianka, bez `RM`)
> odtwarza z logu 59% faktów (60 elementów „widmo”), ze snapshotu 100%. Ucinanie od najstarszych
> (cap 1500 tok.) daje 52% stanu poprawnego czytelnika — gubi konwencje z początku. Snapshot + ogon:
> im dłuższy ogon, tym gorszy naiwny czytelnik (100 zdarzeń: 79,5%). Fold jest asocjacyjny (200
> podziałów) i wymaga sortowania zdarzeń (52 elementy rozjazdu bez niego). `verify` wykrywa 6/6
> wstrzykniętych błędów snapshotu.
>
> **Dane syntetyczne; żaden model ani CLI nie były uruchamiane.** Zachowanie modelu składającego
> snapshot i czytającego go — niezweryfikowane.

## Pliki

- [`ctxfold.py`](ctxfold.py) — generator zdarzeń, `fold`, render/parse snapshotu, polityki
  (`append_all`, `append_cap`, `fold`, `fold_every`), dwa modele czytelnika, `verify`.
- [`test_ctxfold.py`](test_ctxfold.py) — 31 asercji (asocjacyjność, round trip, czytelnicy, wszystkie
  klasy błędów `verify`, kolejność).
- [`SNAPSHOT.bad.example.md`](SNAPSHOT.bad.example.md) — snapshot z 6 wstrzykniętymi błędami (symulacja).

## Jak odpalić

Flaga `-B` nie zostawia `__pycache__/`. Polecenia z katalogu `code/`:

```bash
python3 -B ctxfold.py stats
python3 -B ctxfold.py sizes
python3 -B ctxfold.py compare --t 300
python3 -B ctxfold.py compare --t 290
python3 -B ctxfold.py tail
python3 -B ctxfold.py order
python3 -B ctxfold.py snapshot --t 300 [--why]
python3 -B ctxfold.py log --key decision/orders
python3 -B ctxfold.py verify SNAPSHOT.bad.example.md     # exit 1, 6 problemow (oczekiwane)
python3 -B test_ctxfold.py
```

## Prawdziwy, uruchomiony output

`stats`:

```
zdarzen: 300, operacje: {'add': 61, 'del': 15, 'inc': 44, 'rm': 40, 'set': 140}
klucze zmiennych: 35, nadpisanych >=2x: 17, nadpisan lacznie: 105
stan koncowy: 20 zmiennych, 21 elem. zbiorow, 1 liczniki
log w calosci: 6037 tok., snapshot: 565 tok.
```

`compare --t 300`:

```
| polityka | tok. | prawda: elem. | czyt. poprawny: ok | spurious | czyt. naiwny: ok | spurious |
|---|---|---|---|---|---|---|
| append_all | 6037 | 42 | 42 (100%) | 0 | 25 (59%) | 60 |
| append_cap(1500) | 1524 | 42 | 22 (52%) | 1 | 12 (28%) | 18 |
| append_cap(500) | 504 | 42 | 12 (28%) | 1 | 9 (21%) | 5 |
| fold | 565 | 42 | 42 (100%) | 0 | 42 (100%) | 0 |
| fold+dlaczego | 932 | 42 | 42 (100%) | 0 | 42 (100%) | 0 |
| fold_every(25) | 565 | 42 | 42 (100%) | 0 | 42 (100%) | 0 |
```

`tail` (średnia po t = 10..300):

```
| polityka | sr. tok. | max tok. | naiwny: sr. dokladnosc | poprawny: sr. dokladnosc |
|---|---|---|---|---|
| fold (co zdarzenie) | 392 | 568 | 100.0% | 100.0% |
| fold_every(5) | 434 | 680 | 97.6% | 100.0% |
| fold_every(10) | 481 | 748 | 95.3% | 100.0% |
| fold_every(25) | 606 | 1049 | 91.1% | 100.0% |
| fold_every(50) | 841 | 1521 | 86.2% | 100.0% |
| fold_every(100) | 1296 | 2400 | 79.5% | 100.0% |
| append_all | 3161 | 6037 | 70.7% | 100.0% |
```

`order`: `... roznica wzgledem prawdy bez sortowania: 52 elem., po sortowaniu po t: 0`.
`verify SNAPSHOT.bad.example.md`: 6 linii `BLAD:` (BRAK, PRZESTARZALA, BLEDNA, NADMIAR x2, LICZNIK), exit 1.
Test: `OK: 31 asercji, 0 niepowodzen`.

## Uczciwe ograniczenia

- Strumień syntetyczny: rozkład nadpisań (np. `decision/orders` 16x) i rozmiary wartości zadane regułą.
- „Czytelnik naiwny” to MÓJ model (pierwsza wzmianka, bez `RM`/`DEL`), nie obserwacja zachowania modelu.
- Snapshot jest ograniczony tylko żywym stanem; zbiory add-only (`pitfall`) rosną i wymagają przycinania.
- Fold wymaga typowanych zdarzeń i porządku; z prozy go nie wyprowadzisz. Wstrzyknięte błędy w
  `SNAPSHOT.bad.example.md` to symulacja, nie rozkład błędów prawdziwego modelu.
- Brak weryfikacji w dokumentacji i na żywym `claude` (`/compact`, wznowienie sesji).
