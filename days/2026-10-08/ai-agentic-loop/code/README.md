# Kod do wydania #15 — cykl życia dziennika pętli agentowej (zamknięcie biegu, czas, naprawa ogona, `resolve`)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Rozwija nadzorcę z wydania #14.

Wymagania: **python3** (testowane na 3.10.4), bez zależności zewnętrznych. Testy i demo tworzą
tymczasowe katalogi w `/tmp` (`prasowka-loop2-*`) i same je usuwają (usunięcia nie potwierdzono
listingiem `/tmp` — polecenie zostało odrzucone przez uprawnienia).

**Rolę modelu gra funkcja Pythona** `policy(historia)` — nie LLM i nie Claude Code. Realny jest
nadzorca. Komenda `claude` nie była uruchamiana (`claude --version` odrzucone przez uprawnienia).

## Fragment prasówki, którego dotyczy ten kod

> Dziennik write-ahead z #14 nie miał końca ani zegara. Dopisujemy: (1) rekord `end` o znaczeniu —
> `DONE`/`LOOP`/`NO_PROGRESS`/`NEEDS_HUMAN` są stanami końcowymi (wznowienie odtwarza wynik i nie pyta
> modelu), `BUDGET_*` wznawialne; (2) czas wirtualny `vt` w każdym rekordzie, żeby budżet czasu kumulował się
> między procesami; (3) naprawę urwanego ostatniego wiersza (w #14 kolejny zapis sklejał się z resztką
> i cały dalszy ogon był nieczytelny); (4) `resolve` — jedyna droga wyjścia z `NEEDS_HUMAN`, zapisana
> w tym samym dzienniku; (5) dedup zwracający ORYGINALNY wynik.

## Pliki

| Plik | Rola |
|---|---|
| `agentloop.py` | `Supervisor`, `Journal` (naprawa ogona), `fold` (jedyna semantyka rekordów), `resolve` |
| `world.py` | narzędzia z licznikami efektów + 'modele' (policy), w tym `policy_tripwire` |
| `run_tests.py` | 24 testy `unittest` (m.in. kontrole: bez `end`, bez przywrócenia zegara, `repair=False`) |
| `demo.py` | przebieg scenariuszy (źródło outputu w artykule) |

## Uruchomienie

```bash
python3 -B run_tests.py
python3 -B demo.py
```

(`-B` — bez zapisu `__pycache__`.) Exit code `0` gdy wszystkie testy przeszły.

## Realny output (testy)

```
Ran 24 tests in 0.333s

OK
```

Output `demo.py` jest wklejony w artykule. Losowość (jitter) ma stałe ziarno (`seed=3`), więc
liczby czasu powtarzają się; klucze idempotencji zależą tylko od `run_id`, kroku i akcji.
