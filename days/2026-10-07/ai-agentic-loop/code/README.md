# Kod do wydania #14 — nadzorca pętli agentowej (budżet, zapętlenie, retry, wznawianie)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **python3** (testowane na 3.10.4), bez zależności zewnętrznych. Testy tworzą
tymczasowe katalogi w `/tmp` (`prasowka-loop-*`) i same je usuwają.

**Rolę modelu gra funkcja Pythona** `policy(historia)` — nie LLM i nie Claude Code. Realny jest
nadzorca. Komenda `claude` nie była uruchamiana (odrzucona przez uprawnienia).

## Fragment prasówki, którego dotyczy ten kod

> Pętla agentowa potrzebuje warunków wyjścia poza modelem: budżetu (kroki, koszt, czas),
> trzech detektorów zapętlenia (ta sama akcja, cykl, ten sam błąd mimo różnych akcji),
> retry z backoffem tylko dla błędów przejściowych oraz dziennika write-ahead z kluczem
> idempotencji. Crash między efektem a zapisem wyniku rozwiązuje się powtórką z tym samym
> kluczem; narzędzie bez klucza kończy bieg jako `NEEDS_HUMAN`, bo nadzorca nie zgaduje.

## Pliki

| Plik | Rola |
|---|---|
| `agentloop.py` | `Supervisor`, `Budget`, `Journal`, detektory, backoff, klucz idempotencji |
| `world.py` | narzędzia z licznikami efektów ubocznych + 'modele' (policy) do scenariuszy |
| `run_tests.py` | 25 testów `unittest` |
| `demo.py` | wypisuje przebieg 7 scenariuszy (źródło outputu w artykule) |

## Uruchomienie

```bash
python3 -B run_tests.py
python3 -B demo.py
```

(`-B` — bez zapisu `__pycache__`.) Exit code `0` gdy wszystkie testy przeszły.

## Realny output (testy)

```
Ran 25 tests in 0.306s

OK
```

Output `demo.py` jest wklejony w artykule; losowość (jitter) ma stałe ziarno, więc opóźnienia
`[0.324, 0.302, 2.604]` powtarzają się, a klucze idempotencji (hash) zależą tylko od
`run_id`, kroku i akcji.
