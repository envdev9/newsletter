# Projekt

Backend .NET (ASP.NET Core, .NET Aspire), PostgreSQL przez Dapper/Npgsql, migracje SqlDeployer, CI w TeamCity, wdrożenie na Kubernetes (Helm).

## Komendy

- Build: `dotnet build`
- Testy: `dotnet test`
- Testy integracyjne wymagają zmiennej `ConnectionStrings__TestDb` (dedykowana baza testowa; nazwa musi zawierać `test`).

## Gdzie co leży

- `.claude/rules/conventions.md`: podjęte decyzje i konwencje. `antipatterns.md`: czego nie robić (z powodami). `sql.md`: zasady skryptów SQL (ładuje się przy plikach `.sql`).
- `docs/domain/`: opis biznesowy, słownik (`glossary.md`), reguły (`rules.md`). Czytaj przy zadaniach dotykających domeny; nazywaj byty zgodnie ze słownikiem.
- `docs/architecture/`: układ projektów. `adr/`: uzasadnienia decyzji. Nowa decyzja to nowy ADR według `adr/0000-template.md`.
- `docs/superpowers/specs/`: specy funkcji z brainstormingu.

## Workflow

Nową funkcję backendową zaczynaj od `/feature-backend <opis>` (agent `dotnet-developer`, review i security równolegle, commit po potwierdzeniu).

## Do uzupełnienia w projekcie

- Katalog ze skryptami SqlDeployer i komenda uruchomienia dla Postgresa:
- Nazwa zasobu bazy w AppHost (zakładamy `db`):
