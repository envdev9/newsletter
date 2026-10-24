# Kod do wydania #15 — `ef-core-review` v2: LIKE '%x%', Contains na listach i plan prosto z aplikacji

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Skaner `scan_ef.py` z #14 dostał trzy rozszerzenia, a każde ma pomiar na prawdziwym SQL Server 2022
> i EF Core 10.0.12. (1) `LIKE-LEADING-WILDCARD`: `Email.Contains(term)` na indeksowanej kolumnie
> `varchar(100)` w tabeli 50 000 wierszy to **371 odczytów logicznych** (plan: Clustered Index Scan),
> a `Email == x` to **5**, `StartsWith` — **25**. (2) `CONTAINS-LIST` / `CONTAINS-CONSTANT`: dla list
> o 300 różnych rozmiarach EF 10 domyślnie zostawia **23 plany w cache** (parametr na element,
> dopełniany do "wiaderek"), tryb `Parameter` (OPENJSON) — **1**, tryb `Constant` — **301**;
> lista 5000 id: 82 ms / 29 ms / 955 ms. (3) Skaner rozpoznaje kontekst EF także po zadeklarowanym
> typie (`Repo repo` + `DbSet<Order> Orders`), a nie tylko po nazwie zmiennej. Plany do `scan_plan.py`
> generuje teraz sama aplikacja: `PlanCaptureInterceptor` (EF `DbCommandInterceptor`).

## Struktura

```
code/
├── claude-skills/ef-core-review/    # -> .claude/skills/ef-core-review/
│   ├── SKILL.md                     # instrukcja skilla v2
│   ├── scan_ef.py                   # skaner kodu v2 (10 reguł, stdlib)
│   └── scan_plan.py                 # skaner planu z #13 (bez zmian w logice)
├── claude-hooks/                    # -> .claude/hooks/
│   ├── ef-post-edit.py              # PostToolUse: WARN -> exit 2, INFO -> additionalContext (bez zmian)
│   └── settings.snippet.json
├── ef-plan-demo/                    # projekt .NET 10 + EF Core 10.0.12 (SqlServer)
│   ├── ShopContext.cs               # Customer + Email varchar(100) z indeksem
│   ├── Queries.cs                   # zapytania mierzone (Equals/StartsWith/Contains/EndsWith, ByIds, EF.Constant)
│   ├── PlanCaptureInterceptor.cs    # DbCommandInterceptor: plan zapytania EF -> plik .xml
│   └── Program.cs                   # sekcja 1 (bez bazy), 2-4 (prawdziwy SQL Server)
├── regression/ef-v1/                # kod demo z #14 — tylko do skanowania w testach (nie jest kompilowany)
├── samples/                         # PRAWDZIWE plany zapisane przez interceptor (SQL Server 2022)
│   └── like_eq.xml  like_startswith.xml  like_contains.xml  like_endswith.xml
└── run_tests.py                     # 65 sprawdzeń
```

## Jak uruchomić testy (bez .NET i bez SQL Server)

Z katalogu `code/`, wymagany tylko Python 3:

```bash
python3 run_tests.py
python3 claude-skills/ef-core-review/scan_ef.py ef-plan-demo
python3 claude-skills/ef-core-review/scan_plan.py samples/like_contains.xml
```

## Jak uruchomić demo .NET

Sekcja 1 (ile parametrów generuje `Contains`) wymaga tylko SDK .NET 10 i nuget.org — bez bazy:

```bash
dotnet run --project ef-plan-demo/EfPlanDemo.csproj
```

Sekcje 2-4 (plan cache, lista 5000 id, LIKE z planami) — własny, jednorazowy kontener SQL Server,
port tylko na loopbacku:

```bash
docker run -e ACCEPT_EULA=Y -e MSSQL_SA_PASSWORD='Twoje_haslo_123x' -e MSSQL_MEMORY_LIMIT_MB=2048 -p 127.0.0.1:14381:1433 --name prasowka-ai-mssql-1008 -d mcr.microsoft.com/mssql/server:2022-latest
dotnet run --project ef-plan-demo/EfPlanDemo.csproj -- --sqlserver "Server=127.0.0.1,14381;User Id=sa;Password=Twoje_haslo_123x;TrustServerCertificate=true;Encrypt=false" --plan-dir /sciezka/do/katalogu
docker rm -f prasowka-ai-mssql-1008
```

Program sam tworzy bazę `PrasowkaAiPlan1008` (50 000 wierszy) i na końcu ją usuwa. Poczekaj kilkanaście
sekund po `docker run`, aż SQL Server wstanie. Plany trafiają do `--plan-dir` jako `like_*.xml`
(kopie z mojego uruchomienia są w `samples/`).

## Użycie w prawdziwym repo

```bash
mkdir -p .claude/skills .claude/hooks
cp -r claude-skills/ef-core-review .claude/skills/
cp claude-hooks/ef-post-edit.py .claude/hooks/
# scalic claude-hooks/settings.snippet.json z .claude/settings.json
```

`PlanCaptureInterceptor` dodajesz w środowisku dev: `options.AddInterceptors(new PlanCaptureInterceptor(cs, "plans"))`,
a przed zapytaniem ustawiasz `interceptor.NextLabel = "nazwa"`. Wymaga uprawnienia `VIEW SERVER STATE`.

## Weryfikacja — co uruchomiono naprawdę

SDK .NET 10.0.400, EF Core 10.0.12, SQL Server 2022 (Docker, Linux, własny kontener, usunięty po teście),
Python 3.10 (stdlib). Build: 0 warnings, 0 errors.

```
$ dotnet run --project ef-plan-demo/EfPlanDemo.csproj -- --sqlserver "<cs>" --plan-dir samples
== Sekcja 1: ids.Contains(c.Id) - ile parametrow generuje EF Core 10 (bez polaczenia z baza) ==
tryb domyslny               rozmiar listy -> liczba DECLARE: 1->1 2->2 5->5 6->10 9->10 17->20 100->100 500->500 1000->1000 2000->2000 2100->1 2200->1
tryb Parameter (OPENJSON)   rozmiar listy -> liczba DECLARE: 1->1 2->1 5->1 6->1 9->1 17->1 100->1 500->1 1000->1 2000->1 2100->1 2200->1
tryb Constant               rozmiar listy -> liczba DECLARE: 1->0 2->0 5->0 6->0 9->0 17->0 100->0 500->0 1000->0 2000->0 2100->0 2200->0
-- tryb Parameter (OPENJSON), 3 elementy:
DECLARE @ids nvarchar(4000) = N'[10,20,30]';
...WHERE [c].[Id] IN (SELECT [i].[value] FROM OPENJSON(@ids) WITH ([value] int '$') AS [i])

== Sekcja 2: plan cache - listy o rozmiarach 1..300, po jednym zapytaniu na rozmiar ==
domyslny                   wpisow w plan cache:   23   czas 300 zapytan: 2526 ms
Parameter (OPENJSON)       wpisow w plan cache:    1   czas 300 zapytan: 1060 ms
Constant                   wpisow w plan cache:  301   czas 300 zapytan: 5262 ms
EF.Constant(ids) w kodzie  wpisow w plan cache:  301   czas 300 zapytan: 4498 ms

== Sekcja 3: duza lista (5000 id) w roznych trybach ==
domyslny               SQL: 1 DECLARE, 24112 znakow; wynik=5000, 82 ms
Parameter (OPENJSON)   SQL: 1 DECLARE, 24092 znakow; wynik=5000, 29 ms
Constant               SQL: 0 DECLARE, 28976 znakow; wynik=5000, 955 ms

== Sekcja 4: LIKE '%x%' vs LIKE 'x%' na varchar(100) z indeksem, 50 000 wierszy (plan z interceptora) ==
zapytanie     wierszy  logical reads   WHERE w SQL
eq                  1              5   WHERE [c].[Email] = @email
startswith         11             25   WHERE [c].[Email] LIKE @prefix_startswith ESCAPE '\'
contains            1            371   WHERE [c].[Email] LIKE @term_contains ESCAPE '\'
endswith           50            371   WHERE [c].[Email] LIKE @suffix_endswith ESCAPE '\'
-- plany zapisane (4): like_eq.xml, like_startswith.xml, like_contains.xml, like_endswith.xml
-- baza PrasowkaAiPlan1008 usunieta
```

Plany zapisane przez interceptor, przepuszczone przez `scan_plan.py` (opisy skrócone):

```
like_eq.xml         | INFO | KEY-LOOKUP | NodeId=3 Clustered Index Seek na [Customers].[PK__...] (~1 wierszy) ...
like_startswith.xml | INFO | KEY-LOOKUP | NodeId=6 Clustered Index Seek na [Customers].[PK__...] (~1 wierszy) ...
like_contains.xml   | WARN | SCAN       | NodeId=0 Clustered Index Scan na [Customers].[PK__...] (tabela ~50000 wierszy, odczyt ~4500) ...
like_endswith.xml   | WARN | SCAN       | NodeId=0 Clustered Index Scan na [Customers].[PK__...] (tabela ~50000 wierszy, odczyt ~4500) ...
```

Skaner kodu na `ef-plan-demo` (exit 1; opisy skrócone) i hook na `Queries.cs` (exit 2):

```
Queries.cs:19 | WARN | LIKE-LEADING-WILDCARD | `c.Email.Contains(...)` -> LIKE '%...' na INDEKSOWANEJ kolumnie `Email` ...
Queries.cs:23 | WARN | LIKE-LEADING-WILDCARD | `c.Email.EndsWith(...)` -> LIKE '%...' ...
Queries.cs:27 | INFO | CONTAINS-LIST         | `ids.Contains(c.Id)` -> IN (...): EF 10 wysyla jeden parametr na element ...
Queries.cs:31 | WARN | CONTAINS-CONSTANT     | `EF.Constant(...)` wstawia wartosci jako literaly do tekstu SQL ...
Program.cs:41 | WARN | CONTAINS-CONSTANT     | ParameterTranslationMode.Constant: kolekcje (Contains) wchodza do SQL jako literaly ...
```

`python3 run_tests.py` → `WYNIK: 65/65 sprawdzen zgodnych` (5 regresja z #14, 4 kod ef-plan-demo, 19 fixtur
z #14, 21 fixtur v2, 5 planów + spójność kod↔plan, 11 hooka).
Pierwsza wersja dała 62/65: dwa błędy to wina harnessu testowego (skanowałem zły plik z pary), jeden to
realny błąd skanera — opisany w artykule.

### Czego NIE zweryfikowano

- **Żywa sesja Claude Code.** Hook sprawdzono przez pipe/plik JSON na stdin, nie przez prawdziwe zdarzenie
  `PostToolUse`; skill nie był auto-aktywowany. `claude` CLI nie był uruchamiany.
- **Czasy** (2.5 s / 1.1 s / 5.3 s, 82 / 29 / 955 ms) to jednorazowe, pojedyncze uruchomienia na jednej
  maszynie (na wcześniejszych przebiegach tego samego kodu: 2.4-2.9 s, 1.0-1.2 s, 5.2-5.4 s — ten sam rząd
  wielkości). Wiarygodna jest kolejność i rząd wielkości, nie dokładne liczby. Liczby odczytów logicznych
  i wpisów w cache są deterministyczne.
- **Dlaczego 301, nie 300 wpisów** w trybie `Constant`: nie badałem, co jest tym dodatkowym wpisem.
- Odczyty zależą od planu wybranego dla konkretnej wartości parametru. W roboczym przebiegu, w którym fraza była
  literałem w SQL (a nie parametrem), ten sam `Contains` dał 222 odczyty (Index Scan na `IX_Customers_Email`),
  a `EndsWith` 320 — czyli "371" nie jest stałą natury, tylko wynikiem planu dla parametru na tych danych.
- Plany z interceptora to plany **kompilacyjne z cache** (bez `ActualRows`), dla jednego zapytania i tabeli
  50 000 wierszy. `SET SHOWPLAN_XML ON` + `sp_executesql` nie zwrócił planu wewnętrznego zapytania (tylko wiersz
  `EXECUTE PROC`), dlatego interceptor czyta `sys.dm_exec_query_plan`.
- Skaner dopasowuje po typie **tylko** reguły v2 i kontekst `DbSet` (`Repo repo`); `STRING-UNICODE` nadal działa
  po nazwie właściwości. `IEntityTypeConfiguration` w innym katalogu niż skanowany nie jest czytany. Typ
  zmiennej to tekstowa deklaracja `Typ nazwa` — dziedziczenie, aliasy `using`, `var`, wstrzykiwanie przez
  konstruktor z primary constructor (`class R(ShopCtx store)`) nie są rozpoznawane.
- Tylko SQL Server; PostgreSQL/SQLite tłumaczą `Contains` na listach inaczej i nie były mierzone.
- Pułapka procesowa: zmienne środowiskowe w poleceniu były w tym środowisku odrzucane, dlatego connection
  string przekazuję argumentem `--sqlserver` (zmienna `EFPLAN_SQLSERVER` też działa, ale jej nie testowałem).
