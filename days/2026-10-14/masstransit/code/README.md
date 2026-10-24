# Kod do wydania z 2026-10-14 — MassTransit: trwała saga w EF Core (SQLite)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK**. MassTransit + MassTransit.EntityFrameworkCore 8.5.10,
Microsoft.EntityFrameworkCore.Sqlite 9.0.10. Bez Dockera (SQLite w pliku, transport in-memory).

## Fragment artykułu

> Repozytorium EF Core zapisuje stan sagi jako wiersz w tabeli, więc nowy proces może podjąć
> sagę tam, gdzie poprzedni skończył. Zmierzony haczyk: typy wiadomości w globalnej przestrzeni
> nazw są odrzucane (`Messages types must have a valid namespace`). Pozostałe scenariusze
> (restart, wyścig, pesymistyczna współbieżność) - NIEZWERYFIKOWANE, patrz artykuł.

## Struktura

```
code/
└── masstransit-efsaga-demo/
    ├── MassTransitEfSagaDemo.csproj
    ├── Saga.cs      # OrderState (ISagaVersion), mapa EF, OrderDbContext, OrderStateMachine
    └── Program.cs   # tryby: submit | pay | race | show
```

## Uruchomienie (ścieżki względem `code/`)

```bash
dotnet build masstransit-efsaga-demo
# DLL: masstransit-efsaga-demo/bin/Debug/net10.0/MassTransitEfSagaDemo.dll

# A) restart procesu: dwa OSOBNE procesy, ta sama baza
dotnet masstransit-efsaga-demo/bin/Debug/net10.0/MassTransitEfSagaDemo.dll submit saga.db 11111111-1111-1111-1111-111111111111
dotnet masstransit-efsaga-demo/bin/Debug/net10.0/MassTransitEfSagaDemo.dll pay    saga.db 11111111-1111-1111-1111-111111111111

# B) wyścig dwóch eventów na jednej sadze
dotnet masstransit-efsaga-demo/bin/Debug/net10.0/MassTransitEfSagaDemo.dll race saga.db optimistic noretry
dotnet masstransit-efsaga-demo/bin/Debug/net10.0/MassTransitEfSagaDemo.dll race saga.db optimistic retry
dotnet masstransit-efsaga-demo/bin/Debug/net10.0/MassTransitEfSagaDemo.dll race saga.db pessimistic noretry
```

## Co zostało zweryfikowane, a co nie

Zweryfikowane: `dotnet build` (0 errors; ostrzeżenie NU1903 o transitive SQLitePCLRaw) oraz
jeden start, który ujawnił błąd przestrzeni nazw (naprawiony). **Niezweryfikowane:** wszystkie
scenariusze A i B powyżej - uruchomienia były zablokowane uprawnieniami sesji, więc nie ma
żadnego outputu do zacytowania.
