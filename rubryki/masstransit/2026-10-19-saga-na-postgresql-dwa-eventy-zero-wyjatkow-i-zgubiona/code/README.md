# Kod do wydania z 2026-10-19 — MassTransit: saga na PostgreSQL, wyścig dwóch eventów i cichy lost update

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK**, **Docker** (PostgreSQL 16). MassTransit + MassTransit.EntityFrameworkCore 8.5.10,
Npgsql.EntityFrameworkCore.PostgreSQL 10.0.0 (wersja 9.x nie zbuduje się razem z MassTransit.EntityFrameworkCore
8.5.10 — błąd NU1107, bo ten ciągnie EF Core 10). Transport: in-memory (trwały jest tylko stan sagi).

## Fragment artykułu

> Saga w EF Core z domyślnym trybem optymistycznym i `ISagaVersion` potrafi po cichu zgubić aktualizację:
> kolumna `Version` nigdy się nie zmienia (w naszym teście zawsze 0), więc `WHERE Version = 0` pasuje do obu
> równoległych UPDATE-ów. Dwa eventy, `eventsApplied=2` zamiast 3, zero wyjątków. Prawdziwy token (`xmin`)
> zamienia to w głośny `DbUpdateConcurrencyException`; tryb pesymistyczny daje `SELECT ... FOR UPDATE`, ale
> przy domyślnej izolacji (wnioskuję: wyższej niż ReadCommitted — po jej ustawieniu błąd znika) drugi event dostaje SQLSTATE 40001, a nie czeka.

## Struktura

```
code/
└── masstransit-pgsaga-demo/
    ├── MassTransitPgSagaDemo.csproj
    ├── Saga.cs      # OrderState (ISagaVersion), mapa EF (opcjonalnie xmin), OrderStateMachine
    └── Program.cs   # tryby: reset | submit | pay | race | show
```

## Uruchomienie (ścieżki względem `code/`)

```bash
# 1. PostgreSQL (jednorazowy kontener, port tylko na localhost)
docker run -d --name mt-pgsaga-demo -e POSTGRES_PASSWORD=demo -p 127.0.0.1:55432:5432 postgres:16-alpine

# 2. Build
dotnet build masstransit-pgsaga-demo
DLL=masstransit-pgsaga-demo/bin/Debug/net10.0/MassTransitPgSagaDemo.dll
# (inne polaczenie: zmienna MT_PG z connection stringiem Npgsql)

# A) restart procesu: dwa OSOBNE procesy, ta sama baza
dotnet $DLL submit 11111111-1111-1111-1111-111111111111
dotnet $DLL pay    11111111-1111-1111-1111-111111111111

# B) wyścig dwóch eventów: <optimistic|pessimistic> <retry|noretry> [xmin] [readcommitted] [sql]
dotnet $DLL race optimistic  noretry
dotnet $DLL race optimistic  retry
dotnet $DLL race pessimistic noretry sql
dotnet $DLL race pessimistic retry
dotnet $DLL race optimistic  noretry xmin
dotnet $DLL race optimistic  retry   xmin
dotnet $DLL race pessimistic noretry readcommitted

dotnet $DLL show
dotnet $DLL reset

# 3. Sprzątanie
docker rm -f mt-pgsaga-demo
```

## Co zostało zweryfikowane (realne uruchomienia, 2026-10-19)

| Scenariusz | Wynik w bazie (`eventsApplied`, `trail`) | Fault |
|---|---|---|
| A: `submit` → osobny proces `pay` | `state=Submitted paid=True eventsApplied=2 trail=Submitted;Paid;` | brak |
| `optimistic noretry` | `paid=True packed=True eventsApplied=2 trail=Submitted;Paid;` (lost update) | brak |
| `optimistic retry` | identycznie jak wyżej | brak |
| `pessimistic noretry` (domyślna izolacja) | `packed=False eventsApplied=2` | `InvalidOperationException` (SQLSTATE 40001) |
| `pessimistic retry` | `eventsApplied=3 trail=Submitted;Paid;Packed;` | jeden `R-RETRY`, brak Fault |
| `optimistic noretry xmin` | `packed=False eventsApplied=2` | `DbUpdateConcurrencyException` |
| `optimistic retry xmin` | `eventsApplied=3 trail=Submitted;Packed;Paid;` | jeden `R-RETRY` |
| `pessimistic noretry readcommitted` | `eventsApplied=3 trail=Submitted;Paid;Packed;` | brak |

Każdy scenariusz uruchomiony **raz** (wyścig jest niedeterministyczny co do tego, który event wygra — widać to w
kolejności `trail`). `dotnet build`: 0 warnings, 0 errors.

**Niezweryfikowane:** czas oczekiwania drugiego eventu na lock w `readcommitted` (nie mierzony), liczne powtórzenia /
statystyka wyścigu, wiele procesów jednocześnie (wyścig był w jednym procesie), `UseDelayedRedelivery`, RabbitMQ
jako transport sagi, `Optimistic` z `Version` inkrementowanym ręcznie.
