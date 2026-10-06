# Kod do wydania #13 — MassTransit: routing topic/direct na RabbitMQ

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej fragment artykułu + jak odpalić kod od zera.

Wymagania: **.NET 10 SDK**, **Docker** (obraz `rabbitmq:4.3-management`, ok. 150 MB).

## Fragment prasówki, którego dotyczy ten kod

> Od wydania #5 każdy nasz exchange na RabbitMQ był **fanout**: MassTransit publikuje typ
> wiadomości, a każda związana kolejka dostaje kopię. Dziś pierwszy raz sięgamy po **routing po
> kluczu**: exchange typu `topic` (wzorce `*` i `#`) oraz `direct` (dokładne dopasowanie).
> Zmierzone haczyki: konsument na domyślnej topologii nie dostaje nic z exchange'a topic
> (wiązanie z pustym kluczem), wiadomość bez pasującego wiązania znika po cichu
> (`publish_in=2`, `publish_out=1`), a zmiana typu istniejącego exchange'a kończy się
> `precondition_failed` widocznym tylko w logu brokera.

## Struktura projektu

```
code/
├── .gitignore                              # pomija bin/, obj/
└── masstransit-topic-routing-demo/
    ├── MassTransitTopicRoutingDemo.csproj  # MassTransit 8.5.10 + MassTransit.RabbitMQ 8.5.10
    ├── Contracts.cs                        # SensorReading (topic), Alert (direct), 5 konsumentów
    └── Program.cs                          # tryby: run / inspect / conflict
```

## Jak uruchomić od zera

### 1. Postaw RabbitMQ

```bash
docker run -d --name mt-topic-routing-demo -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=newsletter_dev \
  -e RABBITMQ_DEFAULT_PASS=newsletter_dev_local_only \
  rabbitmq:4.3-management
docker exec mt-topic-routing-demo rabbitmq-diagnostics -q ping
```

> ⚠️ `newsletter_dev` / `newsletter_dev_local_only` to dane **wyłącznie do demo** na lokalnym
> kontenerze. Nie używaj ich nigdzie indziej.

### 2. Zbuduj i uruchom (w tej kolejności)

```bash
dotnet build days/2026-10-06/masstransit/code/masstransit-topic-routing-demo
dotnet run --no-build --project days/2026-10-06/masstransit/code/masstransit-topic-routing-demo -- run
# odczekaj ok. 8 s (statystyki REST API mają opóźnienie), potem:
dotnet run --no-build --project days/2026-10-06/masstransit/code/masstransit-topic-routing-demo -- inspect
dotnet run --no-build --project days/2026-10-06/masstransit/code/masstransit-topic-routing-demo -- conflict
docker logs mt-topic-routing-demo --tail 8      # tu widać precondition_failed z trybu conflict
docker exec mt-topic-routing-demo rabbitmqctl list_exchanges name type
```

### 3. Posprzątaj (tylko własny kontener)

```bash
docker stop mt-topic-routing-demo
docker rm mt-topic-routing-demo
```

## Zweryfikowany output

Pełny output `run`, `inspect` i `conflict` jest w [`../ARTICLE.md`](../ARTICLE.md) (sekcje 2-6);
to prawdziwe uruchomienie na RabbitMQ `4.3-management`, .NET SDK 10.0.400,
`dotnet build`: 0 Warning(s), 0 Error(s). Skrót wyniku `run`:

```
  eu-all           2
  temp-anywhere    2
  audit            4
  naive-default    0
  alerts-critical  1
```

`inspect`: `SensorReading typ=topic publish_in=4 publish_out=8`, `Alert typ=direct publish_in=2
publish_out=1`. Kontener po demie zatrzymany i usunięty (`docker ps -a` pokazał potem tylko
cudze kontenery).

Niezweryfikowane: `mandatory`/publisher returns, odczyt klucza routingu w konsumencie,
exchange `headers`, klaster, TLS, `dotnet test` (brak testów w tym wydaniu).
