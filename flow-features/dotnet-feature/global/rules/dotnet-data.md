---
paths:
  - "**/*.sql"
  - "**/*Repository*.cs"
  - "**/*Repositories/**/*.cs"
  - "**/Data/**/*.cs"
  - "**/Persistence/**/*.cs"
  - "**/Migrations/**"
  - "**/*IntegrationTests*/**/*.cs"
---

# Zasady .NET: dane (Dapper, PostgreSQL, SqlDeployer)

Uzupełnienie `~/.claude/rules/dotnet.md`. Czytaj, gdy zadanie dotyczy bazy, zapytań, migracji lub testów integracyjnych.

## Dapper i PostgreSQL (Npgsql)

- Dostęp do danych przez Dapper na `NpgsqlDataSource` / `IDbConnection` z DI. Połączenia krótko żyjące: `await using var conn = await dataSource.OpenConnectionAsync(ct)`. Nie trzymaj połączenia w polu singletona.
- Zapytania zawsze parametryzowane (`new { Id = id }` lub `DynamicParameters`), nigdy konkatenacja ani interpolacja wartości do SQL. Dynamiczne fragmenty (ORDER BY, nazwy kolumn) tylko z białej listy w kodzie.
- Metody asynchroniczne Dappera (`QueryAsync`, `QuerySingleOrDefaultAsync`, `ExecuteAsync`) z `CommandDefinition(sql, params, transaction, cancellationToken: ct)`, żeby przekazać `CancellationToken`.
- Wybieraj tylko potrzebne kolumny (bez `SELECT *`), mapuj do rekordów/DTO. Dla `snake_case` w bazie ustaw `DefaultTypeMap.MatchNamesWithUnderscores = true` albo aliasuj kolumny, zgodnie z tym, co robi repo.
- Filtruj, sortuj i paginuj w SQL (`LIMIT`/`OFFSET` lub keyset), nie w pamięci. Unikaj N+1: jedno zapytanie z JOIN i `splitOn` (multi-mapping) albo `WHERE id = ANY(@ids)`.
- Zapytania trzymaj blisko repozytorium/klasy dostępu do danych, w stałych lub plikach SQL, nie rozsiane po serwisach. Logika biznesowa poza warstwą SQL.
- **Modyfikacja istniejących wierszy przez `UPDATE` w miejscu, nie przez delete + insert.** Delete + insert zmienia ID, psuje klucze obce, historię/audyt i odpala triggery `DELETE`. Kolekcje podrzędne synchronizuj różnicowo: `UPDATE` zmienionych, `INSERT` nowych, `DELETE` tylko faktycznie usuniętych. Wyjątek tylko na wyraźne polecenie.
- Operacje wielokrokowe w jawnej transakcji (`BeginTransactionAsync`) przekazywanej do każdego wywołania. Przy współbieżnej edycji użyj optymistycznej blokady (kolumna `version` lub `xmin`) i sprawdzaj liczbę zmienionych wierszy.
- Zmiany schematu tylko przez SqlDeployer (sekcja niżej). Nie wprowadzaj innego narzędzia (EF Migrations, DbUp, FluentMigrator). Nie edytuj skryptów już zastosowanych; nowa zmiana to nowy skrypt.
- Indeksy dla kolumn w filtrach i joinach. Ograniczenia (`NOT NULL`, `UNIQUE`, klucze obce) w schemacie, nie tylko w kodzie. Sprawdź plan dla nietrywialnych zapytań (`EXPLAIN`).
- Typy Postgresa: `timestamptz` dla czasu (UTC w kodzie), `uuid`, `numeric` dla pieniędzy, nigdy `float`. Pamiętaj o mapowaniu enumów i `jsonb` w Npgsql.

## Migracje: SqlDeployer

Migracje bazy robimy narzędziem SqlDeployer (dotnet tool, NuGet `SqlDeployer`, repo `MichalAgata/SqlDeployer`): zwykłe skrypty SQL, bez kodu i bez EF Migrations. Obsługuje m.in. PostgreSQL.

- Skrypty są w katalogach o stałej kolejności wykonania, a wewnątrz katalogu uruchamiane alfabetycznie. Nazywaj je z numerem na początku (`00001-Opis.sql`) i trzymaj się struktury katalogów, którą repo już ma. Zanim dodasz skrypt, obejrzyj istniejące i dopasuj nazwę, katalog i numer.
- Nazwa pliku może zawierać znaczniki: `.EVERYTIME.` (uruchamiany przy każdej migracji) i `.ENV.<NAZWA>.` (tylko gdy podano `--env=<NAZWA>`). Używaj ich tylko, gdy repo już to robi.
- Narzędzie jest domyślnie ustawione na SQL Server, więc dla Postgresa musi dostać typ bazy (`--databasetype`/`--dt`). Dokładną wartość dla Postgresa sprawdź w dokumentacji wersji używanej w repo albo w istniejących skryptach uruchamiających.
- Przydatne opcje: `-c` (connection string), `-f` (katalog ze skryptami), `--dryrun` (pokazuje, co by się wykonało), `-t` (w transakcji), `-ni` (bez pytań, wymagane w CI/Jobie), `--baseline` (oznacza skrypty jako wykonane bez uruchamiania, np. dla istniejącej bazy). Zacznij od `--dryrun`.
- Tabele migracji trafiają do schematu `sqldep` (opcja `--schema`). Nie modyfikuj ich ręcznie.
- Rollback nie jest udokumentowany jako ręczny proces, więc projektuj zmiany wstecznie kompatybilnie (najpierw dodaj, później usuń) i nie licz na cofnięcie.
- Schemat w testach integracyjnych stawiaj tym samym SqlDeployerem i tymi samymi skryptami co produkcja. Dla izolowanego schematu testowego sprawdź, jak narzędzie obsługuje schemat docelowy (connection string z `Search Path` oraz opcja `--schema`) i zgłoś, jeśli nie da się tego pogodzić.
- Uruchamianie na Kubernetesie: osobny Job (lub init container) z obrazem zawierającym SqlDeployer i skrypty, z `-ni`, przed rolloutem serwisów.

## Testy integracyjne na bazie

- Zapytania Dappera i endpointy: testy integracyjne na prawdziwej bazie Postgres, nie na SQLite ani mockach połączenia, bo nie wykryją błędów SQL i mapowania. Bez Testcontainers: testy łączą się z istniejącą, dedykowaną bazą testową.
- Connection string do bazy testowej pochodzi ze zmiennej środowiskowej (np. `ConnectionStrings__TestDb`) lub z `dotnet user-secrets`; nigdy z kodu ani z repo. Gdy go brak, test ma się wywalić z czytelnym komunikatem, a nie być pomijany po cichu.
- Bezpieczeństwo: fixture przed startem sprawdza, że nazwa bazy lub schematu pasuje do wzorca testowego (np. zawiera `test`) i odmawia pracy na innej bazie. Testy nigdy nie dotykają bazy produkcyjnej ani deweloperskiej z prawdziwymi danymi.
- Izolacja przebiegu: każdy przebieg testów (fixture na kolekcję, `IAsyncLifetime` + `ICollectionFixture`) tworzy własny, unikalny schemat (lub bazę) z losowym sufiksem, stawia w nim schemat i po zakończeniu go usuwa. Równoległe przebiegi (kilku deweloperów, buildy TeamCity) nie kolidują.
- Schemat stawiaj tym samym narzędziem migracji co produkcja, uruchamianym na starcie fixture'a, a nie osobnym skryptem testowym.
- Izolacja danych między testami: czyść tabele (np. Respawn) albo używaj unikalnych danych na test. Testy nie zależą od kolejności.
- Do `WebApplicationFactory` wstrzykuj connection string bazy testowej zamiast produkcyjnego. Jeśli repo ma już inny setup testów integracyjnych, dopasuj się do niego i zgłoś to.
- Przy aktualizacjach sprawdzaj w teście, że ID wiersza się nie zmieniło (łapie delete + insert zamiast `UPDATE`).
