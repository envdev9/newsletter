# Kod do wydania #25 — dzierżawa z heartbeatem i tokenem ogrodzeniowym (zamrożony właściciel)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Katalog jest samodzielny (nie wymaga nadzorcy z #14–#24).
Wymagania: **python3** (testowane na 3.10.4), **Linux** (`fcntl.flock`, `SIGSTOP`), bez zależności.
Testy i demo tworzą katalogi `/tmp/prasowka-lease-*` i same je usuwają (test `TestZCleanup`).

**Rolę agenta gra skrypt** (`holder.py`); „praca" to `sleep`, „efekt" to wiersz w `work.log`. Realne:
procesy, `SIGSTOP`/`SIGCONT`/`SIGKILL`, `flock`, `os.replace`, wątek heartbeatu. Komenda `claude` nie była używana.

## Fragment prasówki, którego dotyczy ten kod

> `flock` trzyma bez końca, gdy właściciel jest zamrożony (`SIGSTOP`): B czeka 2,0 s i nie dostaje zamka, a dzierżawa
> z TTL 0,6 s przechodzi na B po 0,54 s (token 2). Heartbeat chroni żywego właściciela z długą pracą (B odbija się;
> bez heartbeatu B wchodzi w środek pracy). Cena: przejęcie po `SIGKILL` ≈ TTL (0,55 s) zamiast ≈ 0,08 s dla `flock`.
> Sama dzierżawa nie wystarcza: zamrożony między sprawdzeniem a zapisem właściciel po `SIGCONT` zapisuje przeterminowany
> stan — 3 zapisy bez sprawdzania, 1 przy check-then-act, 0 gdy **zasób** odrzuca niższy token (`FencedLog`).

## Pliki

| Plik | Rola |
|---|---|
| `lease.py` | `LeaseStore` (CAS pod krótkim flock, token rośnie przy każdym przejęciu), `Heartbeat`, `FencedLog` |
| `holder.py` | proces-pracownik; tryby `unfenced` / `checked` / `fenced`, opcja `--no-heartbeat` |
| `small.py` | pomocnicze: `acq` (jedna próba), `flockhold`/`flocktry` (baza porównawcza z `flock`) |
| `scen.py` | scenariusze na prawdziwych procesach (zamrożenie, długa praca, przejęcie po kill, wyścig) |
| `run_tests.py` | 14 testów `unittest` |
| `demo.py` | 5 sekcji pomiarów (źródło outputu w artykule) |

## Uruchomienie od zera

```bash
python3 -B run_tests.py          # ok. 17 s
python3 -B demo.py 10            # pomiary, 10 powtórzeń w sekcjach 4-5
```

(`-B` — bez `__pycache__`.)

## Realny output

Testy (dwa uruchomienia):

```
..............
----------------------------------------------------------------------
Ran 14 tests in 17.350s

OK
```

(drugie: `Ran 14 tests in 17.331s`, `OK`). `python3 -B demo.py 10`:

```
== 1. zamrozony (SIGSTOP) wlasciciel miedzy sprawdzeniem a zapisem; B przejmuje; A wznowiony (ttl 0.6 s)
  unfenced: tokeny A/B = 1/2; A: ['wrote:0', 'wrote:1', 'wrote:2']; zapisy przeterminowane = 3; ...
  checked : tokeny A/B = 1/2; A: ['wrote:0', 'stop:lease-lost-before-1']; zapisy przeterminowane = 1; ...
  fenced  : tokeny A/B = 1/2; A: ['REJECTED:0:token 1 < 2']; zapisy przeterminowane = 0; ...
== 2. zamrozony ZYWY wlasciciel: flock vs dzierzawa
  flock  : got=False po 2.002 s oczekiwania (timeout 2 s)
  dzierz.: B busy=False token=2 czekal 0.542 s
== 3. zywy wlasciciel, dluga praca 2.0 s przy ttl 0.6 s; probe B po 1.5 s
  heartbeat=True : B busy=True; A odnowien=9, A hb_lost=False, A events=['wrote:0']
  heartbeat=False: B busy=False; A odnowien=None, A hb_lost=False, A events=['wrote:0']
== 4. czas od SIGKILL do przejecia (10 prob, ttl 0.6 s)
  flock: min 0.083 s, mediana 0.084 s, max 0.087 s
  lease: min 0.549 s, mediana 0.553 s, max 0.559 s
== 5. wyscig 4 procesow o wolna dzierzawe (20 rund)
  zwyciezcow na runde: [1]; tokeny zwyciezcow: [(1,)]
```

(w sekcji 1 pominięto pełne listy `log:`; są w artykule.)

## Niezweryfikowane

Żywa sesja `claude`/`claude -p`, `permissionMode`, hooki headless; prawdziwy LLM; zegar `monotonic` między maszynami i po restarcie
hosta, skoki zegara; NFS/Windows/macOS; dzierżawa w bazie/etcd; narzut `FencedLog` przy wielu pisarzach; głodzenie wątku heartbeatu
przy przeciążeniu; wyścig o dzierżawę wygasającą w trakcie; integracja z nadzorcą WAL z #14–#24.
