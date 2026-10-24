# Kod do wydania z 2026-10-21 — MassTransit: atomowy klucz idempotentności przy 2 workerach

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK**, **Docker** (`rabbitmq:4.3-management`). MassTransit + MassTransit.RabbitMQ 8.5.10,
Microsoft.Data.Sqlite 10.0.0 (restore zgłasza ostrzeżenie NU1903 dla `SQLitePCLRaw.lib.e_sqlite3` - tylko demo).

## Fragment artykułu

> „Sprawdź i zapisz” przy dwóch workerach księguje podwójnie: dwa duplikaty tej samej płatności trafiły do
> różnych procesów, a ich efekty zakończyły się w odstępie 141 ms (krócej niż 300 ms efektu), więc oba zrobiły
> `SELECT`, zanim któryś zapisał klucz (5 płatności -> 10 efektów). Klucz główny wstawiony *po* efekcie nic nie chroni. Poprawka: sprawdzenie i
> zajęcie klucza jako jedna operacja (`INSERT OR IGNORE`, sprawdź liczbę wierszy) **przed** efektem (5 płatności -> 5 efektów).
> Cena: awaria po zajęciu klucza zgubi efekt (nie testowane).

## Struktura

```
code/
├── .gitignore
└── idempotency-demo/
    ├── IdempotencyDemo.csproj
    └── Program.cs   # tryby: reset | worker <naive|atomic> <nazwa> <sekundy> | publish <n> | report
```

Stan wspólny: `mt-idem-demo.db` w katalogu tymczasowym systemu (`Path.GetTempPath()`).

## Uruchomienie (ścieżki względem `code/`)

```bash
# 1. RabbitMQ (porty tylko na localhost)
docker run -d --name mt-idem-demo -p 127.0.0.1:56731:5672 -p 127.0.0.1:56732:15672 rabbitmq:4.3-management

# 2. Build
dotnet build idempotency-demo
# DLL: idempotency-demo/bin/Debug/net10.0/IdempotencyDemo.dll

# 3. Scenariusz naive - dwa workery w DWÓCH terminalach (kazdy na 25 s)
dotnet idempotency-demo/bin/Debug/net10.0/IdempotencyDemo.dll reset
dotnet idempotency-demo/bin/Debug/net10.0/IdempotencyDemo.dll worker naive A 25     # terminal 1
dotnet idempotency-demo/bin/Debug/net10.0/IdempotencyDemo.dll worker naive B 25     # terminal 2
dotnet idempotency-demo/bin/Debug/net10.0/IdempotencyDemo.dll publish 5             # terminal 3, gdy oba wystartuja
dotnet idempotency-demo/bin/Debug/net10.0/IdempotencyDemo.dll report

# 4. Scenariusz atomic - to samo, ale po `reset` uruchom workery ze strategia atomic
dotnet idempotency-demo/bin/Debug/net10.0/IdempotencyDemo.dll reset
dotnet idempotency-demo/bin/Debug/net10.0/IdempotencyDemo.dll worker atomic A 20
dotnet idempotency-demo/bin/Debug/net10.0/IdempotencyDemo.dll worker atomic B 20
dotnet idempotency-demo/bin/Debug/net10.0/IdempotencyDemo.dll publish 5
dotnet idempotency-demo/bin/Debug/net10.0/IdempotencyDemo.dll report

# 5. Sprzatanie
docker rm -f mt-idem-demo
```

## Co zostało zweryfikowane (realne uruchomienia, 2026-10-21; każdy scenariusz raz)

| Strategia | Wynik `report` |
|---|---|
| `naive` | 5 płatności, `efektow=2 (A,B)` dla każdej, razem 10, duplikatów 5; zero `SKIP` |
| `atomic` | 5 płatności, `efektow=1`, razem 5, duplikatów 0; 5 × `SKIP (klucz zajety)` |

`dotnet build`: 0 błędów, 2 ostrzeżenia NU1903 (SQLite). Zrzut konsoli workerów i `report` jest w artykule.

**Niezweryfikowane:** awaria po zajęciu klucza (efekt zgubiony - tylko rozumowanie), stan `started`/`done`,
więcej niż 2 workery, serwerowa baza (PostgreSQL/SQL Server), statystyka (każdy scenariusz raz), `dotnet test`.
Wtyczka `delayed-message` (plan z #27) nie została pobrana - pobieranie zablokowane przez uprawnienia.
