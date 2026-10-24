# Kod do wydania #16 — `ef-core-review` v3: PostgreSQL (Npgsql), plany `EXPLAIN` i bramka budżetowa w CI

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Skill `ef-core-review` z #15 znał tylko SQL Server. Na PostgreSQL 16.14 (Npgsql EF Core 10.0.0, 200 000 wierszy)
> zmierzyłem: (1) `ids.Contains(...)` — Npgsql domyślnie wysyła **jedną tablicę** (`= ANY(@p)`): 1 wpis w
> `pg_stat_statements` dla 300 rozmiarów listy (tryb `Constant`: 300). (2) `StartsWith` na zwykłym btree w kolacji
> `en_US.utf8` to Seq Scan (**1696** buforów), z `varchar_pattern_ops` — **4**. (3) `Contains` leczy dopiero GIN
> z `gin_trgm_ops`: **17** buforów zamiast 1696 (za to dla `eq` ten indeks jest gorszy: 461 vs 4). Interceptor
> `PgPlanCaptureInterceptor` zapisuje `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` każdego zapytania, a `scan_pg_plan.py`
> (SEQ-SCAN, HASH-SPILL, SORT-SPILL, TEMP-IO, ESTIMATE-SKEW, BUDGET) ma kod wyjścia nadający się na bramkę w CI.
> Skaner kodu rozpoznaje dialekt (`UseNpgsql`), zna `ILike` i ma INFO `PG-STARTSWITH-OPCLASS`.

## Struktura

```
code/
├── claude-skills/ef-core-review/    # -> .claude/skills/ef-core-review/
│   ├── SKILL.md                     # instrukcja skilla v3
│   ├── scan_ef.py                   # skaner kodu v3 (dialekt Npgsql, ILike, PG-STARTSWITH-OPCLASS)
│   ├── scan_plan.py                 # skaner planow SQL Server XML z #13 (bez zmian, skopiowany dla samodzielnosci)
│   └── scan_pg_plan.py              # NOWY: skaner planow PostgreSQL (EXPLAIN FORMAT JSON) + budzet
├── claude-hooks/                    # -> .claude/hooks/   (bez zmian wzgledem #15)
│   ├── ef-post-edit.py
│   └── settings.snippet.json
├── pg-plan-demo/                    # projekt .NET 10 + EF Core 10.0.12 + Npgsql 10.0.0
│   ├── ShopContext.cs               # Customer + Email varchar(100) z indeksem btree, tryb kolekcji opcjonalny
│   ├── Queries.cs                   # eq / StartsWith / Contains / EndsWith / ByIds / self-join / sort
│   ├── PgPlanCaptureInterceptor.cs  # DbCommandInterceptor: EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) -> plik .json
│   └── Program.cs                   # sekcje 1-3 (wymaga PostgreSQL)
├── samples/                         # 16 PRAWDZIWYCH planow z PostgreSQL 16.14, zapisanych przez interceptor
├── budgets.json                     # przykladowy budzet buforow
└── run_tests.py                     # 40 sprawdzen
```

## Jak uruchomić testy (bez .NET i bez PostgreSQL)

Z katalogu `code/`, wymagany tylko Python 3:

```bash
python3 run_tests.py
python3 claude-skills/ef-core-review/scan_ef.py pg-plan-demo
python3 claude-skills/ef-core-review/scan_pg_plan.py samples
python3 claude-skills/ef-core-review/scan_pg_plan.py --budget budgets.json samples/btree_contains.json samples/gin_trgm_contains.json
```

## Jak uruchomić demo .NET

Wymaga SDK .NET 10 i Dockera. `pg_stat_statements` musi być załadowane przy starcie serwera, a `pg_trgm` jest
w obrazie `postgres:16` (contrib). Własny, jednorazowy kontener, port tylko na loopbacku:

```bash
docker run -e POSTGRES_PASSWORD=Twoje_haslo_123x -p 127.0.0.1:15432:5432 --name prasowka-ai-pg-1009 -d postgres:16 -c shared_preload_libraries=pg_stat_statements -c pg_stat_statements.track=all
dotnet run --project pg-plan-demo/PgPlanDemo.csproj -- --pg "Host=127.0.0.1;Port=15432;Username=postgres;Password=Twoje_haslo_123x;Database=postgres" --plan-dir /sciezka/do/katalogu
docker rm -f prasowka-ai-pg-1009
```

Program tworzy bazę `prasowka_ai_1009` (200 000 wierszy), po zakończeniu ją usuwa. Poczekaj kilka sekund po
`docker run`, aż PostgreSQL wstanie. Plany trafiają do `--plan-dir` jako `<indeks>_<zapytanie>.json`
(kopie z mojego uruchomienia są w `samples/`).

## Użycie w prawdziwym repo

```bash
mkdir -p .claude/skills .claude/hooks
cp -r claude-skills/ef-core-review .claude/skills/
cp claude-hooks/ef-post-edit.py .claude/hooks/
# scalic claude-hooks/settings.snippet.json z .claude/settings.json
```

Bramka w CI: w teście integracyjnym ustaw `interceptor.NextLabel = "nazwa_testu"` przed zapytaniem (interceptor przyjmuje
tylko `SELECT` — EXPLAIN ANALYZE wykonuje polecenie), a w kroku pipeline uruchom
`python3 .claude/skills/ef-core-review/scan_pg_plan.py --budget budgets.json plans/` (exit 1 = naruszenie).
Interceptor wykonuje zapytanie drugi raz na osobnym połączeniu — tylko dev/testy.

## Weryfikacja — co uruchomiono naprawdę

SDK .NET 10.0.400, EF Core 10.0.12, Npgsql EF 10.0.0, PostgreSQL 16.14 (Docker, własny kontener, usunięty po teście),
Python 3.10 (stdlib). Build: 0 warnings, 0 errors.

```
PostgreSQL: 16.14 (Debian 16.14-1.pgdg13+1), collation bazy: en_US.utf8, wierszy: 200000
domyslny (nie ustawiony) wpisow w pg_stat_statements:   1   wywolan: 300   czas 300 zapytan: 1010 ms
Parameter                wpisow w pg_stat_statements:   1   wywolan: 300   czas 300 zapytan: 781 ms
Constant                 wpisow w pg_stat_statements: 300   wywolan: 300   czas 300 zapytan: 1181 ms
lista 5000 id:   45 ms / 54 ms / 82 ms (szum - bez wniosku)

indeks             zapytanie    wierszy   bufory       ms
btree              eq                 1        4     0.21
btree              startswith         1     1696    34.76
btree              contains           1     1696    67.07
btree              endswith       50000     1696   147.18
btree_pattern_ops  startswith         1        4     0.03
btree_pattern_ops  contains           1     1696    67.43
gin_trgm           eq                 1      461    14.74
gin_trgm           startswith         1      255     8.75
gin_trgm           contains           1       17     0.16
gin_trgm           endswith       50000     2050    69.22

work_mem domyslny  join: Hash: 4 partii    342.1 ms | sort: external merge 9496kB   1028.5 ms
work_mem 64kB      join: Hash: 256 partii  403.9 ms | sort: external merge 6920kB    794.6 ms
```

(Skrócone: pełny wydruk zawiera też SQL i warunki `Filter`/`Index Cond` każdego planu. Poprzedni przebieg tego samego
kodu dał te same bufory i plany, a czasy w ms o tym samym rzędzie wielkości, z różnicami do ok. 50%.)

`python3 run_tests.py` → `WYNIK: 40/40 sprawdzen zgodnych` (13 dialekt skanera, 3 kod demo, 18 planów, 4 bramka, 2 hook).
Pierwsze uruchomienie dało 38/40: dwa błędy to wina oczekiwań testu (model SQL Server bez `varchar` poprawnie daje
`STRING-UNICODE`). Realne błędy znalezione skanerem na własnym demo opisuje artykuł (komunikaty SQL Server w projekcie Npgsql).

### Czego NIE zweryfikowano

- **Żywa sesja Claude Code.** CLI jest w środowisku, ale próba uruchomienia `claude` została odrzucona przez uprawnienia
  sesji, więc go nie uruchamiałem. Hook sprawdzono JSON-em na stdin (2 przypadki), nie zdarzeniem `PostToolUse`;
  skill nie był auto-aktywowany.
- **Czasy** (ms) to pojedyncze uruchomienia z narzutem `EXPLAIN ANALYZE`; wiarygodne są bufory i liczba wpisów w statystykach.
  Wyniki dla `work_mem` (hash/sort) są niewyjaśnione — niższy `work_mem` nie dał dłuższego sortowania.
- **Spill typu Hash w SQL Server** — niezrobiony (brak SQL Servera w tej sesji); sekcja 3 to odpowiednik PostgreSQL.
- `ESTIMATE-SKEW` testowane tylko planem złożonym ręcznie; progi reguł (10 000 wierszy, 90%, 10×) są arbitralne.
- Tylko `en_US.utf8`, jedna tabela, jeden kształt danych; koszt zapisu i rozmiar indeksu GIN niemierzone; `ILIKE`/`citext` niemierzone.
- Dialekt skanera jest wykrywany tekstowo dla całego zestawu plików; `PG-STARTSWITH-OPCLASS` nie czyta migracji `.sql` ani kolacji bazy.
- Bramka CI sprawdzona tylko kodem wyjścia skanera w `run_tests.py`, nie w prawdziwym pipeline.
