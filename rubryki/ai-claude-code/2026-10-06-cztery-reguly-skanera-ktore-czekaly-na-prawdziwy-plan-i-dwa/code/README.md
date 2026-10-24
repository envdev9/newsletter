# Kod do wydania #13 — `sql-plan-review`: SPILL, MEMORY-GRANT, NO-STATISTICS i NO-JOIN-PREDICATE na realnych planach

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Cztery reguły skanera `scan_plan.py`, które od wydania #4 czekały na realny plan —
> `SPILL`, `MEMORY-GRANT`, `NO-STATISTICS`, `NO-JOIN-PREDICATE` — odpalone na planach
> nagranych z SQL Server 2022 (Docker, własny kontener, własna baza). Wszystkie cztery
> zadziałały bez zmian w logice wykrywania, ale realne plany ujawniły dwa błędy skanera
> (podwójne raportowanie spillu, fałszywy `ESTIMATE-SKEW` na operatorach z wieloma
> wykonaniami — także w teście z #10) oraz dwie "ślepe plamki" silnika: plan `TRIVIAL` nie
> niesie ostrzeżenia `ColumnsWithNoStatistics`, a `COUNT(*)` z cross joina nie niesie
> `NoJoinPredicate`.

## Struktura

```
code/
├── claude-skills/sql-plan-review/   # -> .claude/skills/sql-plan-review/
│   ├── SKILL.md                     # bez zmian (kopia z #10)
│   ├── scan_sql.py                  # bez zmian (kopia z #10)
│   └── scan_plan.py                 # POPRAWIONY w #13: dedup SPILL, ESTIMATE-SKEW na wykonanie
├── sql/                             # odtworzenie bazy i planow od zera
│   ├── 00-create-database.sql       # baza PrasowkaAiSpill1006, AUTO_CREATE_STATISTICS OFF
│   ├── 01-spill.sql                 # zmienna tabelowa + hint compat 140 -> sort wylewa sie do tempdb
│   ├── 02-memory-grant.sql          # varchar(4000) z krotkimi wartosciami -> przewymiarowany grant
│   ├── 03-no-statistics.sql         # WHERE Category = 7 w joinie: BEZ ostrzezenia (slepa plamka)
│   ├── 04-no-join-predicate.sql     # FROM a, b bez warunku, MAX(a.x + b.x)
│   └── 05-no-statistics-variants.sql# GROUP BY / ORDER BY / klucz joina: ostrzezenie jest
├── samples/                         # REALNE plany XML z zywego SQL Servera (14 plikow)
├── extract_plan.py                  # wyciaga n-ty <ShowPlanXML> z wyjscia sqlcmd -y 0
└── run_tests.py                     # 15 sprawdzen: scan_plan.py na samples/*.xml
```

Do uruchomienia `run_tests.py` SQL Server **nie jest potrzebny** — próbki są w repo.

## Jak uruchomić testy

Z katalogu `code/`:

```bash
python3 run_tests.py
python3 claude-skills/sql-plan-review/scan_plan.py samples/spill.xml
```

Użycie skilla w prawdziwym repo:

```bash
mkdir -p .claude/skills
cp -r claude-skills/sql-plan-review .claude/skills/
```

## Jak odtworzyć plany od zera (własny, jednorazowy kontener)

Kontener bez publikowania portów, unikalna nazwa — nie dotyka niczego innego:

```bash
docker run -e ACCEPT_EULA=Y -e MSSQL_SA_PASSWORD='Twoje_haslo_123x' -e MSSQL_MEMORY_LIMIT_MB=2048 \
    --name prasowka-ai-mssql-1006 -d mcr.microsoft.com/mssql/server:2022-latest
docker cp sql prasowka-ai-mssql-1006:/tmp/sql
docker exec prasowka-ai-mssql-1006 /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Twoje_haslo_123x' -C -b -i /tmp/sql/00-create-database.sql
docker exec prasowka-ai-mssql-1006 /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Twoje_haslo_123x' -C -b -y 0 -i /tmp/sql/01-spill.sql -o /tmp/out01.txt
docker cp prasowka-ai-mssql-1006:/tmp/out01.txt out01.txt
python3 extract_plan.py out01.txt samples/spill.xml
```

Analogicznie `02`, `04`, `05` (dla `05` trzy plany: `extract_plan.py out05.txt plik.xml 1|2|3`).
Kolejność po prostu 00, 01, 02, 03, 04, 05: `02` tworzy `dbo.Wide` (używa jej `03`), `03` tworzy
`dbo.Plain`, `04` tworzy `dbo.Tiny` — obie potrzebne w `05`.
Sprzątanie:

```bash
docker exec prasowka-ai-mssql-1006 /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Twoje_haslo_123x' -C -Q "ALTER DATABASE PrasowkaAiSpill1006 SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE PrasowkaAiSpill1006"
docker rm -f prasowka-ai-mssql-1006
```

## Weryfikacja — co uruchomiono naprawdę

SQL Server 2022 RTM-CU27 (16.0.4295.3) Developer, Linux, Docker; Python 3.10 (stdlib):

```
$ python3 run_tests.py
OK    missing_index_trivial.xml      oczekiwano: SCAN                                       otrzymano: SCAN
OK    missing_index_full.xml         oczekiwano: MISSING-INDEX, SCAN                        otrzymano: MISSING-INDEX, SCAN
OK    keylookup.xml                  oczekiwano: KEY-LOOKUP                                 otrzymano: KEY-LOOKUP
OK    implicit_convert_bad.xml       oczekiwano: IMPLICIT-CONVERT, SCAN                     otrzymano: IMPLICIT-CONVERT, SCAN
OK    implicit_convert_good.xml      oczekiwano: -                                          otrzymano: -
OK    spill.xml                      oczekiwano: ESTIMATE-SKEW, SCAN, SPILL                 otrzymano: ESTIMATE-SKEW, SCAN, SPILL
OK    memory_grant.xml               oczekiwano: MEMORY-GRANT, SCAN                         otrzymano: MEMORY-GRANT, SCAN
OK    no_join_predicate.xml          oczekiwano: NO-JOIN-PREDICATE, SCAN                    otrzymano: NO-JOIN-PREDICATE, SCAN
OK    no_statistics_groupby.xml      oczekiwano: NO-STATISTICS, SCAN                        otrzymano: NO-STATISTICS, SCAN
OK    no_statistics_orderby.xml      oczekiwano: MISSING-INDEX, NO-STATISTICS, SCAN         otrzymano: MISSING-INDEX, NO-STATISTICS, SCAN
OK    no_statistics_joinkey.xml      oczekiwano: NO-STATISTICS, SCAN                        otrzymano: NO-STATISTICS, SCAN
OK    no_statistics_trivial.xml      oczekiwano: SCAN                                       otrzymano: SCAN
OK    no_statistics.xml              oczekiwano: MISSING-INDEX, SCAN                        otrzymano: MISSING-INDEX, SCAN
OK    spill.xml                      liczba SPILL              oczekiwano: 1  otrzymano: 1
OK    no_join_predicate.xml          liczba NO-JOIN-PREDICATE  oczekiwano: 1  otrzymano: 1

WYNIK: 15/15 sprawdzen zgodnych (realne plany z SQL Server 2022, Docker)
```

Uwaga metodologiczna: oczekiwane zestawy reguł ustalono po obejrzeniu realnych planów i
wyników skanera (to test regresji/dokumentacja zachowania, nie test napisany "w ciemno").

Realny fragment planu spillu (`samples/spill.xml`):

```xml
<Warnings><SpillToTempDb SpillLevel="2" SpilledThreadCount="1"></SpillToTempDb><SortSpillDetails
GrantedMemoryKb="1024" UsedMemoryKb="1024" WritesToTempDb="7841" ReadsFromTempDb="7841"></SortSpillDetails></Warnings>
```

### Czego NIE zweryfikowano

- Spill typu **Hash** (`HashSpillDetails`) — skaner go obsługuje, ale realnego planu z hash
  spillem nie nagrano; tylko Sort spill.
- Nazwy atrybutów `SpillLevel`, `WritesToTempDb` potwierdzone dla Sort; dla Hash — z pamięci.
- Dlaczego dokładnie `WHERE Category = 7` w joinie nie niesie `ColumnsWithNoStatistics`,
  a `GROUP BY`/`ORDER BY`/klucz joina niosą — zmierzone, ale mechanizmu wewnętrznego
  optymalizatora nie sprawdzono (hipoteza: ostrzeżenie dotyczy statystyk potrzebnych do
  estymacji, a dla równości optymalizator ma heurystykę 316 = sqrt(100000)).
- Progi (`g/u >= 10`, `g >= 10 000 KB`, `SKEW_FACTOR = 10`) arbitralne, sprawdzone na
  jednym przypadku każdy.
- Inne wersje/edycje SQL Server, auto-aktywacja skilla w żywej sesji Claude Code.
- Pułapki procesowe: `cp -r`, `mv` i łączenie poleceń w jednym wywołaniu powłoki były w
  tym środowisku odrzucane — wszystko robione pojedynczymi poleceniami.
