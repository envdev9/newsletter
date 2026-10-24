# Kod do wydania #10 — `sql-plan-review` na prawdziwym SQL Serverze

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Baza demo `PrasowkaAiPlanReview` z tabelą `Orders` (50 000 wierszy). Pięć realnych planów
> nagranych przez `SET STATISTICS XML ON` na SQL Server 2022 (Docker): plan `TRIVIAL` bez
> sugestii indeksu vs. ten sam predykat + `ORDER BY` → plan `FULL` z `MissingIndexGroup`;
> Key Lookup przez indeks bez `INCLUDE`; i klasyczna pułapka ADO.NET/EF Core — string
> parametr wysyłany jako `NVARCHAR`, kolumna `VARCHAR` → `PlanAffectingConvert`, indeks
> zignorowany, `Index Scan` zamiast `Index Seek` (114 vs 2 logical reads, 57×). Skaner
> `scan_plan.py` ze skilla `sql-plan-review` (wydanie #4) sprawdzony na tych realnych
> planach: **5/5 zgodnych, zero zmian w kodzie skanera potrzebnych** — nazwy atrybutów XML
> zapisane tam "z pamięci" okazały się trafne.

## Struktura

```
code/
├── claude-skills/sql-plan-review/   # -> .claude/skills/sql-plan-review/ (kopia z #4, bez zmian logiki)
│   ├── SKILL.md
│   ├── scan_sql.py                  # regexowy skaner T-SQL (niezmieniony, nie testowany dzisiaj ponownie)
│   └── scan_plan.py                 # skaner Showplan XML — dzisiaj zweryfikowany na realnych planach
├── sql/                              # odtworzenie demo-bazy i nagranie planow od zera
│   ├── 00-create-database.sql
│   ├── 01-schema-and-data.sql        # tabela Orders, 50 000 wierszy
│   ├── 02-missing-index-trivial.sql  # plan TRIVIAL — brak sugestii indeksu
│   ├── 03-missing-index-full.sql     # + ORDER BY -> plan FULL — sugestia sie pojawia
│   ├── 04-key-lookup.sql             # indeks bez INCLUDE -> Key Lookup
│   ├── 05-implicit-convert.sql       # NVARCHAR vs VARCHAR parametr na kolumnie VARCHAR
│   └── 06-implicit-convert-iostats.sql  # ten sam parametr, ale ze SET STATISTICS IO
├── samples/                           # REALNE plany XML nagrane z live SQL Server (nie fixtury)
│   ├── missing_index_trivial.xml
│   ├── missing_index_full.xml
│   ├── keylookup.xml
│   ├── implicit_convert_bad.xml
│   └── implicit_convert_good.xml
└── run_tests.py                       # scan_plan.py na kazdej probce vs oczekiwany zestaw regul
```

Wymagania do odtworzenia `samples/*.xml` od zera: Docker + obraz
`mcr.microsoft.com/mssql/server:2022-latest`. **Do samego uruchomienia `run_tests.py` SQL
Server NIE jest potrzebny** — próbki `.xml` już są w repo, to realne nagrane plany.

## Jak odtworzyć bazę i plany od zera

Jeśli nie masz jeszcze kontenera z SQL Serverem:

```bash
docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=Your_password123!" \
    -p 1433:1433 --name sql-plan-review-demo \
    -d mcr.microsoft.com/mssql/server:2022-latest
```

(W tej sesji użyto kontenera, który już działał w środowisku z innej rubryki — polecenia
niżej są ogólne, podstaw własną nazwę kontenera/hasło.)

Każdy krok: skopiuj skrypt do kontenera, odpal `sqlcmd`. Dla planów XML kluczowe jest `-y 0`
(bez tego `sqlcmd` **obcina** długie kolumny tekstowe na 256 znaków — plan XML wychodzi
uszkodzony w połowie):

```bash
docker cp sql/00-create-database.sql <kontener>:/tmp/00.sql
docker exec <kontener> /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Your_password123!' -C -i /tmp/00.sql

docker cp sql/01-schema-and-data.sql <kontener>:/tmp/01.sql
docker exec <kontener> /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Your_password123!' -C -i /tmp/01.sql

docker cp sql/03-missing-index-full.sql <kontener>:/tmp/03.sql
docker exec <kontener> /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Your_password123!' -C -i /tmp/03.sql -o /tmp/out03.txt -y 0

# plan XML siedzi w jednej linii wyniku, zaczyna sie od "<ShowPlanXML"
docker exec <kontener> sh -c "grep -o '<ShowPlanXML.*' /tmp/out03.txt > /tmp/plan.xml"
docker cp <kontener>:/tmp/plan.xml samples/missing_index_full.xml
```

Analogicznie dla `02`, `04`, `05` (plik `05` ma DWA zapytania w jednym batchu — dwie linie z
`ShowPlanXML` w wyniku, trzeba wyciągnąć obie osobno, patrz niżej "Pułapki"). Na koniec
posprzątaj:

```bash
docker exec <kontener> /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Your_password123!' -C \
    -Q "ALTER DATABASE PrasowkaAiPlanReview SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE PrasowkaAiPlanReview;"
```

## Jak uruchomić testy (nie wymaga SQL Servera)

Z katalogu `code/`:

```bash
python3 run_tests.py
python3 claude-skills/sql-plan-review/scan_plan.py samples/implicit_convert_bad.xml
```

Użycie skilla w prawdziwym repo:

```bash
mkdir -p .claude/skills
cp -r claude-skills/sql-plan-review .claude/skills/
```

## Weryfikacja — co uruchomiono naprawdę

Docker 29.1.3, SQL Server 2022 (RTM-CU27, KB5104824, Developer Edition, Linux/Ubuntu 22.04),
Python 3.10.4 (tylko stdlib):

```
$ python3 run_tests.py
OK    missing_index_trivial.xml    oczekiwano: SCAN                                     otrzymano: SCAN
OK    missing_index_full.xml       oczekiwano: MISSING-INDEX, SCAN                      otrzymano: MISSING-INDEX, SCAN
OK    keylookup.xml                oczekiwano: ESTIMATE-SKEW, KEY-LOOKUP                otrzymano: ESTIMATE-SKEW, KEY-LOOKUP
OK    implicit_convert_bad.xml     oczekiwano: IMPLICIT-CONVERT, SCAN                   otrzymano: IMPLICIT-CONVERT, SCAN
OK    implicit_convert_good.xml    oczekiwano: -                                        otrzymano: -

WYNIK: 5/5 przypadkow zgodnych (realne plany z SQL Server 2022, Docker)
```

Realne `STATISTICS IO` (plik `sql/06-implicit-convert-iostats.sql`), ten sam predykat
(`OrderStatus = 'Cancelled'`, 100/50 000 wierszy), dwa typy parametru:

```
--- NVARCHAR param (niezgodnosc typu) ---
Table 'Orders'. Scan count 1, logical reads 114, ...
--- VARCHAR param (typ zgodny z kolumna) ---
Table 'Orders'. Scan count 1, logical reads 2, ...
```

Realny fragment `MissingIndexGroup` z `samples/missing_index_full.xml` (dokładnie te atrybuty,
które `scan_plan.py` sprawdza od wydania #4):

```xml
<MissingIndexes><MissingIndexGroup Impact="95.9436"><MissingIndex Database="[PrasowkaAiPlanReview]"
Schema="[dbo]" Table="[Orders]"><ColumnGroup Usage="EQUALITY"><Column Name="[CustomerId]"
ColumnId="2"></Column></ColumnGroup></MissingIndex></MissingIndexGroup></MissingIndexes>
```

### Czego NIE zweryfikowano

- Reguły `SPILL`, `NO-JOIN-PREDICATE`, `NO-STATISTICS`, `MEMORY-GRANT` — w tej sesji nie
  udało się w rozsądnym czasie wywołać tych warunków na kontrolowanej próbce (50 000
  wierszy, jedna tabela). Wymagałyby większej skali danych albo ograniczenia pamięci
  serwera; zostają niezweryfikowane, tak jak zaznaczono w #4.
- Zachowanie na innych wersjach/edycjach SQL Server (sprawdzono tylko 2022 RTM-CU27
  Developer Edition na Linuksie w kontenerze).
- `scan_sql.py` (skaner tekstowy T-SQL) — skopiowany bez zmian z #4, nie był przedmiotem
  dzisiejszej weryfikacji (ta dotyczyła wyłącznie planów XML).
- Auto-aktywacja skilla po `description`/`allowed-tools` w żywej sesji Claude Code — jak w
  poprzednich wydaniach, nieweryfikowalne bez takiej sesji.
- Próg `Impact >= 50` (WARN vs INFO) sprawdzony tylko dla jednej realnej wartości (`95.9`) —
  nie wiadomo, jak się zachowuje blisko granicy.
- Pułapka procesowa (nie w kodzie): uruchomienie `.sh` jako całości jest w tym środowisku
  odrzucane przez uprawnienia (jak w poprzednich wydaniach) — wszystkie komendy `docker
  cp`/`docker exec` wykonano pojedynczo, ręcznie, nie przez skrypt.
- Pułapka znaleziona przy nagrywaniu: `sqlcmd` domyślnie **obcina** długie kolumny tekstowe
  (plan XML) na 256 znaków — bez `-y 0` plik wychodzi obcięty w połowie tagu i nie parsuje
  się jako XML. Druga pułapka: plik `05-implicit-convert.sql` ma dwa `EXEC sp_executesql` w
  jednym uruchomieniu `sqlcmd -i`, więc wynik ma DWIE linie zaczynające się od
  `<ShowPlanXML` — trzeba je rozdzielić numerem linii (`grep -n`), inaczej `grep -o` z `-i`
  nad całym plikiem miesza oba plany w jeden ciąg.
