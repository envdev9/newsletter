# Kod do wydania #19 — dwóch pisarzy na jednym dzienniku: `flock`, martwy zamek, wyścigi

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). `agentloop.py` to niezmieniona kopia nadzorcy z wydania #18
(katalog jest samodzielny). Wymagania: **python3** (testowane na 3.10.4), **Linux** (`fcntl.flock`, `/proc`),
bez zależności. Testy i demo tworzą katalogi `/tmp/prasowka-lock-*` i same je usuwają (test `TestZCleanup`
sprawdza, że nic nie zostaje).

**Rolę modelu gra funkcja Pythona** (`policy`); „efekt uboczny" to wiersz dopisany do `effects.log`.
Realne: procesy (`subprocess`, `SIGKILL`), `flock`, `O_EXCL`, `os.replace`. Komenda `claude` nie była używana.

## Fragment prasówki, którego dotyczy ten kod

> Dwóch nadzorców na jednym dzienniku bez blokady: efekty się podwajają (średnio 23,4 z 12), klucz idempotencji
> nie ratuje (check-then-write nieatomowe, średnio 17,0 z 12), a `fold` pokazuje zawsze 12 kroków — dziennik
> nie zdradza duplikatów. `FlockLock` na osobnym pliku `.lock` daje dokładnie 12 efektów w 20/20 biegów, także
> gdy właściciel dostaje `SIGKILL` (jądro zwalnia blokadę); plik-zamek `O_EXCL` po kill -9 blokuje na stałe, a
> jego naprawa „sprawdź PID i usuń" ma wyścig: 5/100 prób kończy się dwoma właścicielami i zgubioną
> aktualizacją. Haczyki `flock`: zamek na samym dzienniku ginie po `os.replace` z `compact`; `unlink` pliku
> `.lock` tworzy dwóch właścicieli; dziecko po `fork()` trzyma zamek po śmierci rodzica; wspólny
> `journal.jsonl.tmp` wywraca niezablokowane procesy (`FileNotFoundError`, 20/40 procesów).

## Pliki

| Plik | Rola |
|---|---|
| `joblock.py` | `FlockLock`, `ExclLock` (z opcjonalnym wykrywaniem martwego właściciela), `pid_alive` (pid + czas startu z `/proc`) |
| `worker.py` | proces-pisarz: nadzorca nad wspólnym dziennikiem, tryby `none`, `flock`, `flock-nb`, `excl`, `excl-stale` |
| `contender.py` | zawodnik o zamek: sekcja krytyczna z licznikiem i przedziałem czasu (wykrywanie nakładania) |
| `harness.py` | uruchamianie wielu procesów, SIGKILL w losowym momencie, liczenie efektów |
| `agentloop.py` | nadzorca z #14–#18 (kopia) |
| `run_tests.py` | 20 testów `unittest` na prawdziwych procesach |
| `demo.py` | 9 sekcji pomiarów (źródło outputu w artykule) |

## Uruchomienie od zera

```bash
python3 -B run_tests.py          # ok. 50 s
python3 -B demo.py 20            # pomiary, 20 powtórzeń na sekcję (kilka minut)
python3 -B demo.py 5 3,5         # tylko sekcje 3 i 5, 5 powtórzeń
```

(`-B` — bez `__pycache__`.) Ręcznie jeden pisarz: `python3 -B worker.py --dir /tmp/moj-katalog --mode flock-nb`
(katalog musi istnieć); drugi taki sam proces w drugim terminalu dostanie kod 75.

## Realny output (testy)

```
Ran 20 tests in 50.676s

OK
```

Drugie uruchomienie: `Ran 20 tests in 50.882s`, `OK`. Wyścigi są losowe — częstości z `demo.py` zmieniają się
między uruchomieniami (np. wyścig przejęcia w naturalnym oknie: 0/25 przy 5 powtórzeniach, 5/100 przy 20).
Testy statystyczne asercją „≥ 1 trafienie" (wyścig przejęcia: 40 prób, 3 zawodników, okno 10 ms; `FileNotFoundError`
przy kompaktowaniu: 8 biegów).

## Niezweryfikowane

Żywa sesja `claude`/`claude -p`, `permissionMode`, hooki headless; prawdziwy LLM; NFS, Windows, macOS, kontenery
z odrębnymi przestrzeniami PID (reuse PID-u tylko symulowany); więcej niż 3 pisarzy; głodzenie przy `flock`;
dzierżawa/heartbeat i zawieszony właściciel (`SIGSTOP`); odziedziczenie zamka przez procesy potomne w innych
językach (np. .NET).
