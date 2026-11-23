# <Nazwa projektu>

<!--
Szablon z flow-feautres/dotnet-feature/repo. Uzupełnij miejsca <...> i usuń sekcje, które nie dotyczą.
Ten plik Claude Code wczytuje automatycznie w każdej sesji w tym repo. Trzymaj go krótko:
szczegóły „jak pisać X” są w .claude/rules/ (ładują się przy pracy na pasujących plikach).
-->

Ogólne zasady .NET: @~/.claude/rules/dotnet.md

## Co to jest

<1–3 zdania: co robi aplikacja, dla kogo.>

## Stack

- .NET <wersja>, <ASP.NET Core Web API / Minimal API / konsola / worker>
- Baza: <PostgreSQL + Dapper / brak>, migracje: <SqlDeployer, katalog `db/`>
- Testy: <xUnit>, <jednostkowe w `tests/X.UnitTests`, integracyjne w `tests/X.IntegrationTests`>
- Hosting: <Docker + Kubernetes (Helm) / Aspire / lokalnie>
- CI: <TeamCity / brak>

## Struktura

```
src/
  <Projekt>.Api/            # controllery/endpointy, DI, konfiguracja
  <Projekt>.Application/    # serwisy, logika biznesowa
  <Projekt>.Domain/         # encje, reguły domenowe
  <Projekt>.Infrastructure/ # repozytoria (Dapper), integracje
tests/
  <Projekt>.UnitTests/
  <Projekt>.IntegrationTests/
db/                         # skrypty SqlDeployer
```

Kierunek zależności: Api → Application → Domain; Infrastructure implementuje interfejsy z Application.

## Komendy

```bash
dotnet build
dotnet test                                   # jednostkowe
ConnectionStrings__TestDb="<...>" dotnet test # z integracyjnymi
dotnet run --project src/<Projekt>.Api
```

## Pliki wzorcowe

Nowy kod pisz tak jak te pliki:

| Co | Wzorzec |
|---|---|
| Controller / endpoint | `src/<...>/Controllers/<X>Controller.cs` |
| Serwis | `src/<...>/<X>Service.cs` |
| Repozytorium | `src/<...>/<X>Repository.cs` |
| Test jednostkowy | `tests/<...>/<X>ServiceTests.cs` |
| Test integracyjny | `tests/<...>/<X>RepositoryTests.cs` |

## Stan kodu

<!-- Usuń, jeśli kod jest spójny. -->
Część starego kodu nie trzyma się zasad z `.claude/rules/`. Nie kopiuj wzorców ze starych plików; wzorem są tylko pliki z tabeli wyżej.
Starego kodu nie refaktoryzuj przy okazji, chyba że zadanie tego dotyczy.

## Zakazy specyficzne dla projektu

- <np. nie dodawaj EF Core>
- <np. nie zmieniaj kontraktów w `Contracts/` bez wersjonowania>
