# Kod do wydania z 2026-10-20 — MassTransit: UseDelayedRedelivery na RabbitMQ bez wtyczki, Interval retry i ShutdownTimeout

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK**, **Docker** (`rabbitmq:4.3-management`). MassTransit + MassTransit.RabbitMQ 8.5.10.

## Fragment artykułu

> `UseDelayedRedelivery` na RabbitMQ wymaga wtyczki opóźnionych wiadomości, której nie ma w oficjalnym obrazie
> `rabbitmq:4.3-management`. Bez niej host startuje i pierwsze próby wyglądają normalnie, ale kolejne próby
> przychodzą po ~21 s zamiast po 3 s, zdrowa wiadomość za pechową stoi (przy `PrefetchCount=1`), a zamknięcie hosta
> trwa 30,0 s (domyślny `HostOptions.ShutdownTimeout`; po ustawieniu na 5 s - 5,0 s). Prawdziwy powód widać tylko w
> logu brokera: `unknown exchange type 'x-delayed-message'`. Alternatywa `Interval` retry działa (3,0 s), ale blokuje slot.

## Struktura

```
code/
└── masstransit-delayed-demo/
    ├── MassTransitDelayedDemo.csproj
    └── Program.cs   # tryby: run <immediate|interval|delayed|delayed-plugin> [sekundy] [shutdownTimeoutSek] | inspect | clean
```

## Uruchomienie (ścieżki względem `code/`)

```bash
# 1. RabbitMQ (porty tylko na localhost; guest/guest dziala tylko lokalnie)
docker run -d --name mt-delayed-demo -p 127.0.0.1:56721:5672 -p 127.0.0.1:56722:15672 rabbitmq:4.3-management

# 2. Build
dotnet build masstransit-delayed-demo
DLL=masstransit-delayed-demo/bin/Debug/net10.0/MassTransitDelayedDemo.dll

# 3. Scenariusze (miedzy nimi: clean)
dotnet $DLL clean
dotnet $DLL run immediate
dotnet $DLL clean
dotnet $DLL run interval 3
dotnet $DLL clean
dotnet $DLL run delayed 3        # ~60 s: TIMEOUT + 30 s StopAsync
dotnet $DLL clean
dotnet $DLL run delayed 3 5      # 4. argument = HostOptions.ShutdownTimeout (s)
dotnet $DLL inspect              # kolejki i exchange'e z REST API

# W logu brokera widac przyczyne:
docker logs mt-delayed-demo

# 4. Sprzatanie
docker rm -f mt-delayed-demo
```

## Co zostało zweryfikowane (realne uruchomienia, 2026-10-20)

| Wariant | Wynik |
|---|---|
| `immediate` | próby #1/#2 w tej samej ms, job-2 po 0,3 s, `StopAsync` 0,1 s |
| `interval 3` | próby po 1,3 / 4,3 / 7,3 s; job-2 dopiero po 7,4 s (czekał ~6 s) |
| `delayed 3` (bez pluginu), 2 przebiegi | próby #3/#4 po 22,5 s (22,6 s), job-2 niezrealizowany w 31 s, `StopAsync` 30,0 s |
| `delayed 3 5` | `StopAsync` 5,0 s |
| log brokera | `precondition_failed: unknown exchange type 'x-delayed-message'` |

`dotnet build`: 0 warnings, 0 errors. Kontener `mt-delayed-demo` usunięty (`docker ps -a` bez niego).

**Niezweryfikowane:** `UseDelayedRedelivery` z działającą wtyczką (wariant `delayed-plugin` kompiluje się, nie był
uruchomiony; pobranie wtyczki odrzucone przez uprawnienia), przyczyna ~21 s (hipoteza: timeout nieudanej wysyłki do
exchange'a `x-delayed-message`), zachowanie `job-2` przy poprawnym delayed redelivery, `StopAsync` w wariancie
`interval`, statystyka (każdy wariant raz, `delayed` dwa razy).
