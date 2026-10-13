# Kod do wydania z 2026-10-13 — MassTransit: Courier, redelivery po restarcie workera, idempotencja, graceful shutdown

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK**, **Docker** (RabbitMQ). MassTransit + MassTransit.RabbitMQ 8.5.10.

## Fragment artykułu

> Ten sam `TrackingNumber`, dwa różne procesy, dwa skutki — a na końcu `RoutingSlipCompleted`.
> Courier gwarantuje at-least-once, więc po śmierci workera w trakcie kroku drugi worker dostaje
> ten krok z `Redelivered=True` i wykonuje skutek ponownie. Obrona: klucz idempotentności
> `TrackingNumber:Aktywność`. Graceful shutdown (`StopApplication`) czeka na krok w toku i nie
> daje duplikatu — slip zostaje zaparkowany w kolejce następnego kroku.

## Struktura

```
code/
├── .gitignore
└── masstransit-courier-redelivery-demo/
    ├── MassTransitCourierRedeliveryDemo.csproj
    ├── Contracts.cs   # 4 aktywności, księga skutków (plik), konsument zdarzeń
    └── Program.cs     # tryby: worker | start | inspect | peek
```

Tryby: `worker <plik-księgi> [slowMs] [idempotent] [stopafter=<ms>]`, `start <orderId>`,
`inspect` (REST API), `peek <kolejka>` (podgląd bez konsumowania).

## Uruchomienie

Ścieżki względem `code/`. Księga (`ledger.log`) jest zwykłym plikiem — używaj świeżej na scenariusz.

```bash
docker run -d --name mt-redelivery-demo -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=newsletter_dev -e RABBITMQ_DEFAULT_PASS=newsletter_dev_local_only \
  rabbitmq:4.3-management

dotnet build masstransit-courier-redelivery-demo
DLL=masstransit-courier-redelivery-demo/bin/Debug/net10.0/MassTransitCourierRedeliveryDemo.dll

# A) redelivery: worker 1 ze spowolnionym krokiem 2 (120 s)
dotnet $DLL worker ledger-a.log 120000        # terminal 1
dotnet $DLL start ORD-A                       # terminal 2
# gdy w ledger-a.log jest EFFECT AuthorizePayment: zabij worker 1 (kill -9 <pid> lub Ctrl+C w terminalu 1)
docker exec mt-redelivery-demo rabbitmqctl list_queues name messages_ready messages_unacknowledged consumers
dotnet $DLL peek authorize-payment_execute
dotnet $DLL worker ledger-a.log 0             # worker 2 -> redelivered=True i drugi EFFECT

# B) idempotencja: jak A, ale worker 2 z flagą:  worker ledger-b.log 0 idempotent   -> SKIP

# C) graceful shutdown: host sam się zatrzymuje po 10 s, krok 2 trwa 10 s
dotnet $DLL worker ledger-c.log 10000 stopafter=10000   # i po ~4 s: dotnet $DLL start ORD-C
# krok kończy się PO ApplicationStopping, brak duplikatu; kolejny worker dokończy slip z create-shipment_execute

docker rm -f mt-redelivery-demo
```

## Co zostało zweryfikowane, a co nie

Zweryfikowane realnie (`dotnet build`: 0 Warning(s), 0 Error(s); RabbitMQ 4.3-management):
redelivery (`redelivered=True`, drugi `EFFECT`), tryb `idempotent` (`SKIP`), treść slipa w kolejce
(`peek`), graceful shutdown przez `StopApplication()` (krok dokończony, bez duplikatu).

**Niezweryfikowane:** `kill`/`kill -9` były zablokowane uprawnieniami sesji — procesy zatrzymywano
narzędziem zatrzymywania zadań (SIGTERM + szybkie zakończenie); zachowanie po przekroczeniu
`ShutdownTimeout`; współbieżne workery i atomowość klucza idempotentności. Kontener usunięty
(`docker rm -f`, potwierdzone `docker ps -a`).
