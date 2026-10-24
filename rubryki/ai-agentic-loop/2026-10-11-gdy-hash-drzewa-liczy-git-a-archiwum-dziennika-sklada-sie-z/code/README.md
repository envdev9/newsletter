# Kod do wydania #18 — hash drzewa z `git write-tree` i oś zdarzeń z archiwów dziennika

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Rozwija nadzorcę z wydań #14, #15 i #17
(`rubryki/ai-agentic-loop/2026-10-10-postep-mierzy-sie-w-kodzie-nie-w-tekscie-bledu-i-pamiec/code`) — `agentloop.py` i `world.py` są skopiowane (jedyna zmiana:
punkt `crash_hook` `compact_archived`), katalog jest samodzielny.

Wymagania: **python3** (testowane na 3.10.4) i **git** (testowane na 2.34.1) w `PATH`, bez zależności
Pythona. Testy i demo tworzą tymczasowe katalogi w `/tmp` (`prasowka-loop4-*`) i same je usuwają
(usunięcia nie potwierdzono listingiem `/tmp` — polecenie zostało odrzucone przez uprawnienia).

**Rolę modelu gra funkcja Pythona** `policy(historia)` — nie LLM i nie Claude Code. Realne są: nadzorca,
`git` (osobny `GIT_DIR`, prawdziwe `add -A` + `write-tree`) i pliki na dysku. „Testy" to funkcja
sprawdzająca, czy w `Foo.cs` jest słowo `fixed`, nie `dotnet test`. Komenda `claude` nie była uruchamiana
(`claude --version` odrzucone przez uprawnienia).

## Fragment prasówki, którego dotyczy ten kod

> `GitTreeObserver` liczy hash drzewa przez `git add -A` do osobnego, tymczasowego `GIT_DIR` i `git
> write-tree` (nie dotyka repo użytkownika). Daje to definicję „zmiany" z `.gitignore` i trybów plików
> (`chmod +x` zmienia hash), ale: plik śledzony wcześniej niż wpisany do `.gitignore` dalej się liczy przy
> trwałym indeksie, a zagnieżdżone repo to ślepy punkt (gitlink). Pomiar: przy 5000 plikach 421 ms
> (własny hash) vs 45–54 ms (git, trwały indeks po rozgrzaniu), przy 200 plikach własny hash jest szybszy.
> Drugi element: `timeline.merge` składa segmenty `journal.jsonl.archive-NNNNN` + żywy plik w jedną oś
> zdarzeń (bez snapshotów, z deduplikacją po kluczu zdarzenia), a `verify` porównuje `fold(oś)` z
> `fold(żywy plik)`. Oś jest rekord po rekordzie równa dziennikowi bez kompaktowania; brak segmentu to
> `TimelineGap`. Znalezisko: crash między `os.link` a `os.replace` sprawia, że archiwum i żywy dziennik to
> ten sam inode — archiwum rośnie po wznowieniu, a naiwne sklejenie daje 79 zdarzeń zamiast 61.

## Pliki

| Plik | Rola |
|---|---|
| `gittree.py` | `GitTreeObserver` — hash drzewa przez `git add -A` + `git write-tree` w osobnym `GIT_DIR` |
| `timeline.py` | `merge`, `verify`, `write_full`, `explain_step`, `TimelineGap`, `TimelineMismatch` |
| `agentloop.py` | nadzorca, dziennik, `fold`, `compact` (z #17 + punkt `compact_archived`) |
| `world.py` | prawdziwy katalog repo + narzędzia + „modele" (policy) |
| `run_tests.py` | 22 testy `unittest` (git, osie, luki, crash między link a replace) |
| `demo.py` | scenariusze 1–7 (źródło outputu w artykule) |

## Uruchomienie

```bash
python3 -B run_tests.py
python3 -B demo.py
```

(`-B` — bez zapisu `__pycache__`.) Exit code `0` gdy wszystkie testy przeszły. Demo trwa kilkanaście
sekund (benchmark na 5000 plikach).

## Realny output (testy)

```
Ran 22 tests in 2.280s

OK
```

Output `demo.py` jest wklejony w artykule. Liczby czasowe (sekcja 4 demo) zależą od maszyny i zmieniają
się między uruchomieniami (np. „nic się nie zmieniło", 200 plików: 44,1 ms vs 18,2 ms) — to rząd
wielkości, nie benchmark. Hashe i liczby rekordów są deterministyczne.

## Niezweryfikowane

Żywa sesja `claude`/`claude -p`, `permissionMode` w frontmatterze agenta i hooki headless (brak dostępu do
CLI), zachowanie prawdziwego LLM, Windows/CRLF, systemy plików sieciowe, `core.fsmonitor`, równoległe
pisarze, strumieniowe składanie osi dla bardzo długich biegów.
