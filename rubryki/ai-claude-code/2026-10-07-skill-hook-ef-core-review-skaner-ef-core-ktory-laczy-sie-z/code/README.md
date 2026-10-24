# Kod do wydania #14 — `ef-core-review`: skaner EF Core + hook, połączone z planem wykonania

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Skill `ef-core-review` łączy skaner planów z #13 z kodem .NET: deterministyczny skaner
> `scan_ef.py` (7 reguł: N+1, `SaveChanges` w pętli, `ToList()` przed `Where`, dwa `Include`
> bez `AsSplitQuery`, funkcja na kolumnie, brak `AsNoTracking`, indeksowany `string` bez
> `IsUnicode(false)`) oraz hook `PostToolUse`, który odpala go po każdej edycji `.cs`.
> Zmierzone na EF Core 10.0.12 i prawdziwym SQL Server 2022: ten sam `Where(c => c.Email == email)`
> daje `nvarchar(100)` albo `varchar(100)` zależnie od jednej linii konfiguracji modelu —
> **222 vs 5 odczytów logicznych**, a `scan_plan.py` potwierdza przyczynę (`IMPLICIT-CONVERT`
> + Index Scan) w planie, który wygenerował sam EF.

## Struktura

```
code/
├── claude-skills/ef-core-review/    # -> .claude/skills/ef-core-review/
│   ├── SKILL.md                     # instrukcja skilla (skaner -> ocena -> format odpowiedzi)
│   ├── scan_ef.py                   # skaner kodu EF Core (stdlib, ~400 linii)
│   └── scan_plan.py                 # skaner planu z #13, bez zmian
├── claude-hooks/                    # -> .claude/hooks/
│   ├── ef-post-edit.py              # PostToolUse: WARN -> exit 2, INFO -> additionalContext
│   └── settings.snippet.json        # fragment do .claude/settings.json
├── ef-demo/                         # projekt .NET 10 + EF Core 10.0.12
│   ├── Entities.cs                  # Customer / Order / Tag
│   ├── BadShopContext.cs            # Email: zwykly string (-> nvarchar)
│   ├── GoodShopContext.cs           # Email: IsUnicode(false) (-> varchar)
│   ├── BadQueries.cs                # 7 antywzorcow, po jednym na metode
│   ├── GoodQueries.cs               # poprawione odpowiedniki
│   └── Program.cs                   # sekcja 1 (SQL bez bazy), 2 (SQLite), 3 (prawdziwy SQL Server)
├── samples/                         # PRAWDZIWE plany z SQL Server 2022 wygenerowane przez EF Core
│   ├── ef_bad.xml                   # parametr nvarchar na kolumnie varchar
│   └── ef_good.xml                  # parametr varchar
└── run_tests.py                     # 36 sprawdzen: kod demo, fixtury, plany, hook
```

## Jak uruchomić testy (bez .NET i bez SQL Server)

Z katalogu `code/`, wymagany tylko Python 3:

```bash
python3 run_tests.py
python3 claude-skills/ef-core-review/scan_ef.py ef-demo
python3 claude-skills/ef-core-review/scan_plan.py samples/ef_bad.xml
```

## Jak uruchomić demo .NET

Sekcje 1 i 2 wymagają tylko SDK .NET 10 i dostępu do nuget.org (SQL Server niepotrzebny):

```bash
dotnet run --project ef-demo/EfDemo.csproj
```

Sekcja 3 (opcjonalna) — własny, jednorazowy kontener SQL Server, port tylko na loopbacku:

```bash
docker run -e ACCEPT_EULA=Y -e MSSQL_SA_PASSWORD='Twoje_haslo_123x' -e MSSQL_MEMORY_LIMIT_MB=2048 -p 127.0.0.1:14371:1433 --name prasowka-ai-mssql-1007 -d mcr.microsoft.com/mssql/server:2022-latest
dotnet run --project ef-demo/EfDemo.csproj -- --sqlserver "Server=127.0.0.1,14371;User Id=sa;Password=Twoje_haslo_123x;TrustServerCertificate=true;Encrypt=false" --plan-dir /sciezka/do/katalogu
docker rm -f prasowka-ai-mssql-1007
```

Program sam tworzy bazę `PrasowkaAiEf1007` (varchar + indeks, 50 000 wierszy), a na końcu ją
usuwa. Plany trafiają do `--plan-dir` jako `ef_bad.xml` / `ef_good.xml` (kopie są w `samples/`).
Poczekaj chwilę po `docker run`, aż SQL Server wstanie, zanim uruchomisz demo.

## Użycie w prawdziwym repo

```bash
mkdir -p .claude/skills .claude/hooks
cp -r claude-skills/ef-core-review .claude/skills/
cp claude-hooks/ef-post-edit.py .claude/hooks/
# scalic claude-hooks/settings.snippet.json z .claude/settings.json
```

Wyciszenie reguły w kodzie: `// ef-review: ignore N-PLUS-1` w linii instrukcji lub linię wyżej.

## Weryfikacja — co uruchomiono naprawdę

SDK .NET 10.0.400, EF Core 10.0.12, SQL Server 2022 (Docker, Linux), Python 3.10 (stdlib).
Build projektu: 0 warnings, 0 errors.

```
$ dotnet run --project ef-demo/EfDemo.csproj
== Sekcja 1: SQL z EF Core (provider SqlServer, bez polaczenia) ==
-- BadShopContext (Email: zwykly string):
DECLARE @email nvarchar(100) = N'user42@example.com';
...
-- GoodShopContext (Email: IsUnicode(false)):
DECLARE @email varchar(100) = 'user42@example.com';
...
-- funkcja na kolumnie (ToLower) w Where:
DECLARE @ToLower nvarchar(100) = N'user42@example.com';
...WHERE LOWER([c].[Email]) = @ToLower

== Sekcja 2: pomiary na SQLite in-memory (20 klientow, 200 zamowien, 160 tagow) ==
scenariusz                            polecen  sledzonych
N+1 (zle)                                  21           0
N+1 (dobrze: Select + Count)                1           0
ToList() przed Where (zle)                  1           0
Count w SQL (dobrze)                        1           0
Include x2 bez split (zle)                  1           0
Include x2 + AsSplitQuery (dobrze)          3           0
odczyt bez AsNoTracking (zle)               1         200
odczyt z AsNoTracking (dobrze)              1           0
zapytanie z Include x2 zwraca 1600 wierszy; split query: 20 + 200 + 160 = 380
```

Sekcja 3 (z `--sqlserver`), prawdziwy SQL Server 2022:

```
== Sekcja 3: prawdziwy SQL Server (kolumna varchar(100) + indeks, 50 000 wierszy) ==
-- bad: wynik=1 wiersz, parametr: @email NVarChar(100)
-- good: wynik=1 wiersz, parametr: @email VarChar(100)
-- bad: logical reads (dm_exec_query_stats) = 222 przy 1 wykonaniu, plan zapisany: ...
-- good: logical reads (dm_exec_query_stats) = 5 przy 1 wykonaniu, plan zapisany: ...
-- SaveChanges w petli (20 Tag): 20 polecen do SQL Server
-- jeden SaveChanges (20 Tag):   1 polecen do SQL Server
-- baza PrasowkaAiEf1007 usunieta
```

Plan zapytania wygenerowanego przez EF (`scan_plan.py samples/ef_bad.xml`, opisy skrócone):

```
WARN | SCAN             | NodeId=2 Index Scan na [Customers].[IX_Customers_Email] (tabela ~50000 wierszy, odczyt ~1) ...
INFO | KEY-LOOKUP       | NodeId=4 Clustered Index Seek na [Customers].[PK__Customer__...] (~1 wierszy) ...
WARN | IMPLICIT-CONVERT | Seek Plan: CONVERT_IMPLICIT(nvarchar(100),[c].[Email],0)=[@email] - niezgodnosc typow ...
```

`python3 run_tests.py` → `WYNIK: 36/36 sprawdzen zgodnych` (5 kod demo, 20 fixtur inline,
2 plany, 9 hooka). Pierwsza wersja skanera miała 32/36 — cztery realne błędy (masking stringów,
`foreach` bez klamer, konfiguracja `varchar` w innym pliku, deduplikacja indeksu złożonego),
opisane w artykule.

### Czego NIE zweryfikowano

- **Żywa sesja Claude Code.** Hook sprawdzono przez pipe JSON na stdin (9 przypadków), nie przez
  prawdziwe zdarzenie `PostToolUse`. Kształt `additionalContext` w JSON-ie hooka pochodzi z
  dokumentacji, nie z obserwacji w żywej sesji; auto-aktywacja skilla też nie była testowana.
- Plany są **kompilacyjne, z `sys.dm_exec_query_plan`** (bez `ActualRows`); jedno zapytanie, jedna
  tabela 50 000 wierszy — współczynnik 222 vs 5 zależy od danych.
- `FUNC-ON-COLUMN`, `TOLIST-BEFORE-FILTER`, `INCLUDE-NO-SPLIT`, `NO-ASNOTRACKING` zmierzono jako
  liczbę poleceń / encji w SQLite lub tekst SQL, **nie** planem na SQL Server.
- Pomiary N+1 i `Include` na SQLite in-memory: liczba poleceń nie zależy od providera, ale
  SQLite nie batchuje wstawień (dlatego `SaveChanges` zmierzono na SQL Server).
- Skaner jest tekstowy: kontekst EF rozpoznaje po nazwie zmiennej (`db`, `ctx`, `context`,
  `*Context`, `*Db`; `repo.Orders.ToList().Where(...)` nie jest wykrywane — luka w teście),
  typy `string` i konfigurację `varchar` dopasowuje po nazwie właściwości, nie po typie encji.
  Nie obsługuje `IEntityTypeConfiguration` rozproszonych po innych katalogach niż skanowany.
- `DataReaderDisposing.ReadCount` odrzucono jako miarę wierszy: liczy końcowy `Read()` i dla
  split query zwracał 0 dla zapytań zależnych.
- Pułapki procesowe: w tym środowisku zmienne środowiskowe w poleceniu były odrzucane,
  dlatego demo przyjmuje `--sqlserver` / `--plan-dir` jako argumenty (zmienne
  `EFDEMO_SQLSERVER` / `EFDEMO_PLAN_DIR` też działają).
