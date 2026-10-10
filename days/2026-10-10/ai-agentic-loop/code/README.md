# Kod do wydania #17 — detektor postępu na hashu drzewa repo i snapshoty stanu dziennika

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Rozwija nadzorcę z wydań #14 i #15
(`days/2026-10-08/ai-agentic-loop/code`) — pliki są skopiowane i zmienione, katalog jest samodzielny.

Wymagania: **python3** (testowane na 3.10.4), bez zależności zewnętrznych. Testy i demo tworzą
tymczasowe katalogi w `/tmp` (`prasowka-loop3-*`) i same je usuwają (usunięcia nie potwierdzono
listingiem `/tmp` — polecenie zostało odrzucone przez uprawnienia).

**Rolę modelu gra funkcja Pythona** `policy(historia)` — nie LLM i nie Claude Code. Realny jest
nadzorca i prawdziwy katalog na dysku, którego hash liczymy. „Testy" to funkcja sprawdzająca, czy w
`Foo.cs` jest słowo `fixed`, nie `dotnet test`. Komenda `claude` nie była uruchamiana
(`claude --version` odrzucone przez uprawnienia).

## Fragment prasówki, którego dotyczy ten kod

> Detektory z #14 patrzą na tekst (odcisk akcji, sygnatura błędu) i są ślepe, gdy model dopisuje do
> argumentów licznik albo runner dopisuje do błędu identyfikator uruchomienia. Dodajemy detektor
> oparty o **hash treści drzewa repo**: zliczamy porażki *weryfikacji* (`verifies=True`) na tym samym
> hashu; trzecia porażka na identycznym drzewie to `TREE_STALL`. Liczy się treść, nie `mtime`, bez
> `obj/`/`bin/`/`.git`. Czytanie plików nie jest weryfikacją, więc „8 odczytów i naprawa" nie jest
> alarmem (naiwne „drzewo bez zmian przez 4 kroki" by go zabiło).
> Drugi element: dziennik write-ahead jest kompaktowany do rekordu `snapshot` (podsumowanie:
> `total`, `cost`, ostatnie odciski/sygnatury, `tree_fail` + ogon `keep` kroków + wiszący `intent`
> + ostatni `end`). Zapis przez `.tmp` + `os.replace` jest bezpieczny na crash; `fold` pozostaje
> jedynym miejscem znającym semantykę rekordów. Ceny: model widzi tylko ogon historii, a ślad
> audytowy trzeba zachować osobno (`archive=True`, twarde dowiązanie).

## Pliki

| Plik | Rola |
|---|---|
| `agentloop.py` | `Supervisor`, `Journal`, `fold` (+ `snapshot`), `compact`, `tree_hash`, `detect_tree_stall`, `resolve` |
| `world.py` | prawdziwy katalog repo + narzędzia z licznikami efektów + „modele" (policy) |
| `run_tests.py` | 41 testów `unittest` (hash drzewa, `TREE_STALL`, snapshoty, crash w kompaktowaniu, regresje) |
| `demo.py` | scenariusze 1–9 (źródło outputu w artykule) |

## Uruchomienie

```bash
python3 -B run_tests.py
python3 -B demo.py
```

(`-B` — bez zapisu `__pycache__`.) Exit code `0` gdy wszystkie testy przeszły.

## Realny output (testy)

```
Ran 41 tests in 3.092s

OK
```

Output `demo.py` jest wklejony w artykule. Backoff (jitter) ma stałe ziarno; hashe drzewa i klucze
zależą tylko od treści, więc liczby się powtarzają.

## Niezweryfikowane

Żywa sesja `claude`/`claude -p`, `permissionMode` w frontmatterze agenta i hooki headless (brak
dostępu do CLI), zachowanie prawdziwego LLM, wydajność hashowania dużych repo, flaky testy,
równoległość kompaktowania, Windows.
