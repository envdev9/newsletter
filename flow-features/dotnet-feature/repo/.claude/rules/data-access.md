---
paths:
  - "src/**/*Repository.cs"
  - "src/**/Infrastructure/**/*.cs"
  - "db/**/*.sql"
---

# Dostęp do danych

<!-- Szablon. Ogólne zasady Dappera/Postgresa są w ~/.claude/rules/dotnet-data.md; tu tylko to, co specyficzne dla repo. -->

Wzorzec: `src/<...>/<X>Repository.cs`

- Repozytorium na agregat (`I<X>Repository` w Application, implementacja w Infrastructure).
- SQL w <stałych `const string` w repozytorium / plikach `.sql` jako embedded resource>.
- Nazwy w bazie: <snake_case>, mapowanie: <`MatchNamesWithUnderscores` / aliasy>.
- Połączenie z <`NpgsqlDataSource` z DI>.

## Aktualizacje: zawsze `UPDATE`

**Modyfikacja istniejących wierszy przez `UPDATE ... WHERE id = @Id`, nigdy delete + insert.**
Powód: delete + insert zmienia ID, psuje klucze obce i historię, odpala triggery `DELETE`.
Kolekcje podrzędne synchronizuj różnicowo (`UPDATE` zmienionych, `INSERT` nowych, `DELETE` usuniętych).
Część starego kodu może robić delete + insert: tego nie kopiuj.

```csharp
const string Sql = """
    UPDATE orders
    SET status = @Status, updated_at = @UpdatedAt, version = version + 1
    WHERE id = @Id AND version = @Version
    """;
var rows = await conn.ExecuteAsync(new CommandDefinition(Sql, order, cancellationToken: ct));
if (rows == 0) return Error.Conflict(); // nie istnieje albo zmieniony równolegle
```

Test integracyjny aktualizacji sprawdza, że ID wiersza się nie zmieniło.

## Migracje

- Katalog: `db/<...>`, nazwy `<00001-Opis.sql>`, typ bazy dla SqlDeployer: `<...>`.
- Komenda lokalnie: `<sqldeployer -c "..." -f db --dt <...> --dryrun>`.
