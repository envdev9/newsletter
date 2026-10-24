# Kod do wydania z 8.10 — dzielenie zadania na okna kontekstu (kiedy ciąć, co zabrać w handoffie)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Wymagania: **python3** (sprawdzono na 3.10.4),
brak zależności. Nic nie jest zapisywane na dysk (poza testem, który używa katalogu tymczasowego).

## Fragment artykułu, którego dotyczy ten kod

> Zadanie syntetyczne: 24 jednostki pracy (543 784 tok.) w oknie 200 000 (2,77x okna), baza 10 000 tok.
> Cięcie to przeprowadzka: koszt = zimny start nowego okna + to, co zgubisz w handoffie. Model kosztów
> (koszt ważony cache, założenia 0,1x/1,25x) daje przy T = 90 000: `predictive+live` 1 466 975,
> `boundary+live` 1 595 253, `boundary+recent3` 1 915 699 (+31%), `boundary+none` 2 106 761 (+44%),
> model auto-kompakcji `never+recent3` 2 553 196 (+74%). Próg T ma szeroki dołek (30-90 tys. różnią
> się o ~14%), a polityka handoffu stromą ścianę, bo 34 z 64 zależności sięgają dalej niż 3 jednostki
> wstecz. Optymalne T rośnie z rozmiarem bazy (45 → 140 tys. przy bazie 5 → 60 tys.).
>
> **Model kosztów na danych syntetycznych; żaden model ani CLI nie były uruchamiane.** Mnożniki cache,
> jakość handoffu pisanego przez model i realna auto-kompakcja Claude Code — niezweryfikowane.

## Pliki

- [`ctxsplit.py`](ctxsplit.py) — generator zadania, symulacja (wyzwalacze `never`/`mid`/`boundary`/`predictive`
  x polityki `none`/`recent3`/`all`/`all_capped`/`live`), render i linter pliku handoff.
- [`test_ctxsplit.py`](test_ctxsplit.py) — 36 asercji (3 scenariusze policzone ręcznie, testy negatywne lintu).
- [`HANDOFF.example.md`](HANDOFF.example.md) — przykładowy handoff (wynik `handoff --after 12`, treść syntetyczna).

## Jak odpalić

Flaga `-B` nie zostawia `__pycache__/`.

```bash
cd code/
python3 -B ctxsplit.py plan
python3 -B ctxsplit.py run --T 90000
python3 -B ctxsplit.py sweep
python3 -B ctxsplit.py base
python3 -B ctxsplit.py handoff --after 12
python3 -B ctxsplit.py lint HANDOFF.example.md
python3 -B ctxsplit.py lint HANDOFF.example.md --root .   # exit 1: wskazniki w przykladzie nie istnieja (oczekiwane)
python3 -B test_ctxsplit.py
```

## Prawdziwy, uruchomiony output

`run --T 90000`:

```
odniesienie (jedno okno bez limitu): 40106334 token-tur, koszt wazony 4647485, max kontekst 553784
| strategia | okien | token-tury | koszt wazony cache | vs bez limitu (wazony) | rework tok | brakujace fakty | wymuszone ciecia | max kontekst | handoffy tok |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| never+recent3 (auto-kompakcja) | 4 | 17033461 | 2553196 | 0.55x | 148986 | 11 | 3 | 199998 | 2985 |
| mid+live | 9 | 8633996 | 1719658 | 0.37x | 85889 | 0 | 0 | 92402 | 11931 |
| boundary+none | 9 | 10620381 | 2106761 | 0.45x | 274671 | 32 | 0 | 133222 | 0 |
| boundary+recent3 | 8 | 10024052 | 1915699 | 0.41x | 155363 | 20 | 0 | 124480 | 7198 |
| boundary+all | 7 | 8847149 | 1635295 | 0.35x | 0 | 0 | 0 | 114864 | 18637 |
| boundary+all_capped | 7 | 9314861 | 1748510 | 0.38x | 74859 | 10 | 0 | 122527 | 10452 |
| boundary+live | 7 | 8684137 | 1595253 | 0.34x | 0 | 0 | 0 | 111580 | 8745 |
| predictive+live | 8 | 7241734 | 1466975 | 0.32x | 0 | 0 | 0 | 90983 | 10604 |
```

`base`:

```
| baza | T (wazony) | okien | koszt wazony | jedno okno bez limitu (wazony) | T (surowe token-tury) | okien |
|---:|---:|---:|---:|---:|---:|---:|
| 5000 | 45000 | 21 | 1197654 | 4570235 | 20000 | 24 |
| 10000 | 60000 | 15 | 1376367 | 4647485 | 20000 | 24 |
| 30000 | 110000 | 8 | 1950975 | 4956485 | 20000 | 24 |
| 60000 | 140000 | 8 | 2676975 | 5419985 | 20000 | 24 |
```

`lint HANDOFF.example.md`: `383 tok. (bajty/4), limit 1500` i `OK`. Test: `OK: 0 niepowodzen`.
Pełne tabele `plan` i `sweep` — w artykule.

## Uczciwe ograniczenia

- Model, nie pomiar: zadanie, zależności i rozmiary tur są syntetyczne i zadane regułą w kodzie.
- Koszt ważony zakłada odczyt z cache 0,1x i zapis 1,25x (z pamięci autora), brak wygasania cache,
  zimny prefiks w każdym nowym oknie; ignoruje koszt tokenów wyjściowych.
- `never+recent3` to MÓJ model auto-kompakcji, nie opis działania `/compact`.
- Koszt odtworzenia decyzji (40% tokenów jednostki) i powtórka całej pracy w toku przy cięciu w środku
  to założenia modelu. Kod nie ma zabezpieczenia przed spiralą cięć przy zbyt małym T.
- Polityka `live` zakłada, że plan deklaruje zależności z góry i że autor handoffu wybiera je bezbłędnie.
- Nie mierzy jakości odpowiedzi w długim kontekście. Linter to heurystyka pod ten jeden format.
