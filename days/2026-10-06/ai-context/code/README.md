# Kod do wydania z 6.10 — kompresja wyników narzędzi i budżet kontekstu

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Wymagania: **python3** (sprawdzono na 3.10.4),
brak zależności.

## Fragment artykułu, którego dotyczy ten kod

> Każda kompresja jest stratna, a strata jest niewidoczna dla modelu. Dlatego oceniaj ją dwiema
> liczbami naraz: zyskiem w tokenach i przeżywalnością faktów ("igieł"). Na syntetycznym logu
> (~53 tys. tok., 4 igły w środku) `head` daje 88x i 0/4, `head+tail` 1/4, "tylko błędy" 3/4
> (gubi fakt bez słowa `error`), `dedup` i `smart` 4/4. Przy budżecie 250 tok. `smart` gubi igłę,
> bo ostrzeżenia powtórzone ~100 razy wygrywają w funkcji oceny z faktem unikalnym - funkcja oceny
> jest polityką kontekstu. Dla JSON: najpierw wiersze (filtr), potem kolumny (projekcja):
> 44 102 → 80 tok.; `head` psuje składnię.
>
> **Dane są syntetyczne, żaden model nie był uruchamiany**; mierzona jest obecność faktów w tekście,
> nie zachowanie modelu. Literatura o "lost in the middle" — z pamięci, źródło nie zostało pobrane
> (WebFetch odrzucony).

## Pliki

- [`toolcompress.py`](toolcompress.py) — generatory danych syntetycznych, strategie kompresji
  (head, head+tail, dedup, tylko błędy, smart, spill; JSON: head, projekcja, filtr+projekcja),
  metryka przeżywalności igieł, plecak budżetu i kolejność "brzegi". Tokeny = bajty/4.
- [`test_toolcompress.py`](test_toolcompress.py) — 21 asercji.

## Jak odpalić

Flaga `-B` nie zostawia `__pycache__/`. `spill` zapisuje plik `toolcompress_spill_demo.log`
w katalogu tymczasowym systemu (usuń po próbie).

```bash
cd code/
python3 -B toolcompress.py demo
python3 -B toolcompress.py demo --budget 250
python3 -B toolcompress.py pack
python3 -B test_toolcompress.py
```

Na własnym logu: `python3 -B toolcompress.py filter --budget 600 < twoj.log`
(uwaga: waga ważności i wzorce błędów w `SEV` są dobrane pod logi `dotnet`).

## Prawdziwy, uruchomiony output

Pełne tabele (`demo`, `demo --budget 250`, `pack`) są w artykule; test:

```
OK: 0 niepowodzen
```

(21 linii `OK`, w tym: head gubi igły 0/4, tylko-błędy 3/4, dedup/smart 4/4, filtr JSON 3/3 przy zysku >50x.)

## Uczciwe ograniczenia

- Dane syntetyczne; zysk ~100x wynika z ekstremalnej powtarzalności logu, w realnych logach będzie mniejszy.
- Metryka mierzy obecność tekstu igły, nie to, czy model ją zauważy i użyje.
- Plecak nie zna wykluczeń (bierze surowy i skompresowany log naraz); wartości `value` są subiektywne.
- `order_edges` to hipoteza oparta na pamięci o literaturze; wpływ na model niemierzony.
- Nie sprawdzano integracji z hookami Claude Code ani żywej sesji.
