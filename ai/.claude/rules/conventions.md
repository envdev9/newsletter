# Konwencje projektu

Decyzje już podjęte w tym projekcie. Uzasadnienia: `docs/architecture/adr/`.

- Dostęp do danych: Dapper na `NpgsqlDataSource` (ADR-0001). Bez EF Core.
- Migracje: SqlDeployer, zwykłe skrypty SQL (ADR-0002). Zasady skryptów: `.claude/rules/sql.md`.
- Testy integracyjne: dedykowana baza testowa Postgres, nie Testcontainers (ADR-0003). Connection string z `ConnectionStrings__TestDb`.
- Orkiestracja i konfiguracja: .NET Aspire. Serwis zna tylko klucz `ConnectionStrings:db` (ADR-0004).
- Wdrożenie: kontener pod Kubernetesem, wiele replik, konfiguracja z env. CI: TeamCity.
- Nowe konwencje (nazewnictwo, struktura projektów, styl testów) dopisuj tutaj, gdy zapadnie decyzja.
