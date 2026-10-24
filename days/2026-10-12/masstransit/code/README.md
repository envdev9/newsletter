# Kod do wydania z 2026-10-12 — MassTransit: Courier na RabbitMQ, awaria procesu w trakcie slipa

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK**, **Docker** (RabbitMQ). MassTransit 8.5.10.

## Fragment artykułu

> Routing slip nie żyje w twoim procesie, tylko w brokerze: cały slip (itinerary, log kroków,
> zmienne) to treść jednej wiadomości w kolejkach `*_execute`. Gdy proces ginie po skutku
> ubocznym, a przed potwierdzeniem kroku, wiadomość wraca do kolejki (`ready=1`, `consumers=0`),
> a żadne zdarzenie `Faulted` nie jest publikowane. Gwarancja to at-least-once.

## Struktura

```
code/
├── .gitignore
└── masstransit-courier-restart-demo/
    ├── MassTransitCourierRestartDemo.csproj
    ├── Contracts.cs   # 4 aktywności, księga skutków (plik), konsument zdarzeń
    └── Program.cs     # tryby: worker | start | inspect
```

## Uruchomienie

```bash
docker run -d --name mt-courier-restart-demo -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=newsletter_dev -e RABBITMQ_DEFAULT_PASS=newsletter_dev_local_only \
  rabbitmq:4.3-management

dotnet build masstransit-courier-restart-demo
DLL=masstransit-courier-restart-demo/bin/Debug/net10.0/MassTransitCourierRestartDemo.dll

# terminal 1: worker z awarią po kroku 2 (4 s opóźnienia, potem FailFast)
dotnet $DLL worker /tmp/ledger.log 4000 crash
# terminal 2: wyślij slip (proces kończy się od razu)
dotnet $DLL start ORD-B
# po awarii:
docker exec mt-courier-restart-demo rabbitmqctl list_queues name messages_ready messages_unacknowledged consumers
# terminal 1: nowy worker bez awarii (opcjonalnie dopisz: idempotent)
dotnet $DLL worker /tmp/ledger.log 0

docker rm -f mt-courier-restart-demo
```

## Co zostało zweryfikowane, a co nie

Zweryfikowane realnie (`dotnet build`: 0 Warning(s), 0 Error(s); RabbitMQ 4.3-management):

- ścieżka szczęśliwa 4 kroków na brokerze (worker + `start` w osobnych procesach),
- awaria `FailFast` po skutku w kroku 2: exit code 134, `authorize-payment_execute`
  `messages_ready=1`, `consumers=0` (`rabbitmqctl`).

**Niezweryfikowane (uruchomienie odrzucone przez uprawnienia sesji):** drugi worker odbierający
slip po awarii (`redelivered=True`, podwójny skutek), tryb `idempotent`, graceful shutdown
(SIGTERM). Kod tych trybów kompiluje się, ale nie został wykonany. Kontener został usunięty
(`docker rm -f`, potwierdzone `docker ps -a`).
