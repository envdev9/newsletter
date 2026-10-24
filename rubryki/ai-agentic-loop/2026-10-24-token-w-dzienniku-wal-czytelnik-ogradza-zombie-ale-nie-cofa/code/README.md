# Kod do wydania #29 — token ogrodzeniowy w dzienniku WAL (fencing po stronie czytelnika)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Katalog jest samodzielny (nie wymaga nadzorcy z #14–#25).
Wymagania: **python3** (testowane na 3.10.4), **Linux** (`fcntl.flock`, `SIGSTOP`), bez zależności.
Testy i demo tworzą katalogi `/tmp/prasowka-fence-*` i same je usuwają (test sprawdza, że nic nie zostało).

**Rolę agenta gra skrypt** (`actor.py`); „praca" to `sleep`, „skutek" to wiersz w `effects.log`. Realne: procesy,
`SIGSTOP`/`SIGCONT`/`SIGKILL`, `flock` (dzierżawa), `O_APPEND`, `os.replace`. Komenda `claude` nie była używana.

## Fragment prasówki, którego dotyczy ten kod

> Dziennik WAL to zwykły `O_APPEND` — zasób nie odmówi zapisu, więc token sprawdza czytelnik: `fold` odrzuca rekord z tokenem niższym niż
> najwyższy widziany wcześniej. Zombie po `SIGCONT` (kroki 2–5 + `done`): fold z tokenem odrzucił 5 rekordów i pokazał wynik B, naiwny przypisał
> bieg A. Ale skutki zewnętrzne kroków 2–5 wykonały się dwa razy — fencing czytelnika nie cofa świata. Tryb `intent` (rekord, potem odczyt,
> potem skutek) daje 0 duplikatów przy zamrożeniu przed zapisem; w oknie między sprawdzeniem a skutkiem skutek przychodzi późno (po krokach 3–5),
> a przy `SIGKILL` w oknie ginie (`brakujące: [2]`, dziennik mówi „zrobione"). Snapshot musi nieść `hw`, inaczej zombie wraca.

## Pliki

| Plik | Rola |
|---|---|
| `wal.py` | `Journal` (`O_APPEND`, jeden `write()`), `fold(fence=…)`, `compact(carry_hw=…)` |
| `lease.py` | dzierżawa + heartbeat z #25 (skopiowana bez zmian) |
| `actor.py` | proces-agent; tryby `blind` / `intent`; barierka z tokenem po przejęciu |
| `scen.py` | scenariusze na procesach (SIGSTOP → przejęcie B → SIGCONT/SIGKILL) |
| `run_tests.py` | 13 testów `unittest` |
| `demo.py` | 5 sekcji (źródło outputu w artykule) |

## Uruchomienie od zera

```bash
python3 -B run_tests.py     # ok. 10 s
python3 -B demo.py          # pomiary
```

## Realny output

Testy (uruchomione 3 razy, w tym dwa równolegle; identycznie):

```
.............
----------------------------------------------------------------------
Ran 13 tests in 9.636s

OK
```

`python3 -B demo.py`:

```
== 1. blind, A zamrozony PRZED krokiem 2 (SIGSTOP), B przejmuje, A wznowiony
  fold z tokenem  : {"steps": {"0": "A/t1", "1": "A/t1", "2": "B/t2", "3": "B/t2", "4": "B/t2", "5": "B/t2"}, "done_by": "B", "hw": 2, "dropped": 5}
  fold naiwny     : {"steps": {"0": "A/t1", "1": "A/t1", "2": "A/t1", "3": "A/t1", "4": "A/t1", "5": "A/t1"}, "done_by": "A", "hw": 2, "dropped": 0}
  skutki na krok  : {0: 1, 1: 1, 2: 2, 3: 2, 4: 2, 5: 2} | duplikaty: [2, 3, 4, 5] | brakujace: []
  kolejnosc skutkow: ['A/t1:0', 'A/t1:1', 'B/t2:2', 'B/t2:3', 'B/t2:4', 'B/t2:5', 'A/t1:2', 'A/t1:3', 'A/t1:4', 'A/t1:5']
== 2. intent, ta sama zamrozenie przed krokiem 2
  skutki na krok  : {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1} | duplikaty: [] | brakujace: []
== 3. intent, A zamrozony w OKNIE miedzy sprawdzeniem a skutkiem (pause 0.4 s), potem SIGCONT
  skutki na krok  : {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1} | duplikaty: [] | brakujace: []
  kolejnosc skutkow: ['A/t1:0', 'A/t1:1', 'B/t2:3', 'B/t2:4', 'B/t2:5', 'A/t1:2']
== 4. intent, A zamrozony w oknie i zabity (SIGKILL)
  skutki na krok  : {0: 1, 1: 1, 3: 1, 4: 1, 5: 1} | duplikaty: [] | brakujace: [2]
== 5. offline: snapshot musi niesc high-water mark; stary fd po compact
  carry_hw=True : krok1 zapisal B/t2, hw=2, odrzucone=['A1s1-zombie']
  carry_hw=False: krok1 zapisal A/t1, hw=1, odrzucone=[]
  zapis przez stary fd po compact: rekordow w dzienniku = 1 (1 = snapshot; zapis zombie trafil do osieroconego i-node'a)
```

(Pominięto linie `fold…` sekcji 2–4; pełne są w artykule/po uruchomieniu.)

## Niezweryfikowane

Żywa sesja `claude`/`claude -p`, `permissionMode`, hooki headless; prawdziwy LLM; NFS/Windows/macOS; więcej niż dwóch pisarzy; zegar `monotonic`
między maszynami; integracja z nadzorcą z #14–#24; wrażliwość scenariuszy procesowych na wolną maszynę (czasy `sleep`/TTL).
