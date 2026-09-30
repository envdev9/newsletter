# Kod do wydania #7 — MassTransit: RoutingSlip/Courier (rozproszona transakcja z kompensacją)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej fragment artykułu + jak odpalić kod od zera.

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`), **Docker** (działający silnik + wolne ok.
150 MB na obraz `rabbitmq:4.3-management`, jeśli nie masz go już w cache).

## Fragment prasówki, którego dotyczy ten kod

> Wyobraź sobie proces zamówienia: **zarezerwuj towar → obciąż kartę**. To dwa niezależne kroki,
> mogą nawet siedzieć w dwóch różnych mikroserwisach, każdy ze swoją kolejką. Jeśli krok 2
> (płatność) zawiedzie, krok 1 (rezerwacja) musi zostać **cofnięty** - inaczej towar zostaje
> zablokowany na zawsze dla zamówienia, które nigdy nie zostało opłacone. RoutingSlip odwraca ten
> problem: **budujesz plan podróży (itinerary)** - listę aktywności do wykonania po kolei - i
> wysyłasz go w świat. Framework sam pilnuje kolejności, sam wykonuje kompensację wstecz przy
> błędzie i sam publikuje jedno z dwóch zdarzeń na koniec: `RoutingSlipCompleted` albo
> `RoutingSlipFaulted`.

## Struktura projektu

```
code/
├── docker-compose.yml                  # RabbitMQ 4.3 + plugin management (porty 5672, 15672)
├── .gitignore                          # pomija bin/, obj/
└── masstransit-routingslip-demo/
    ├── MassTransitRoutingSlipDemo.csproj  # MassTransit 8.5.10 + MassTransit.RabbitMQ 8.5.10
    ├── Contracts.cs                       # ReserveInventoryActivity (z kompensacją),
    │                                      # ChargePaymentActivity (bez kompensacji),
    │                                      # RoutingSlipEventsConsumer, Log
    └── Program.cs                         # 3 tryby: topology / inspect / run <ok|fail>
```

## Jak uruchomić od zera

### 1. Postaw RabbitMQ

```bash
docker run -d --name mt-routingslip-demo -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=newsletter_dev \
  -e RABBITMQ_DEFAULT_PASS=newsletter_dev_local_only \
  rabbitmq:4.3-management
# poczekaj ok. 15 s na start, potem sprawdź:
docker exec mt-routingslip-demo rabbitmq-diagnostics -q ping
# UI managementu: http://localhost:15672 (login: newsletter_dev / newsletter_dev_local_only)
```

Jeśli masz działający `docker compose`/`docker-compose` (w środowisku, w którym budowałem to demo,
żaden z nich nie był dostępny - `docker compose` zwracał `unknown command` - więc plik niżej **nie
został uruchomiony przez compose**, tylko przez równoważny `docker run` powyżej):

```bash
docker compose -f days/2026-09-30/masstransit/code/docker-compose.yml up -d
```

> ⚠️ Login `newsletter_dev` / `newsletter_dev_local_only` to dane **wyłącznie deweloperskie**, takie
> same jak w wydaniu #5 - nie `guest/guest`, nie żaden sekret produkcyjny.

### 2. Zbuduj i uruchom kolejne tryby (w tej kolejności)

```bash
export PATH="$HOME/.dotnet:$PATH"        # jeśli SDK jest w ~/.dotnet
cd days/2026-09-30/masstransit/code/masstransit-routingslip-demo
dotnet build

dotnet run --no-build -- topology     # deklaruje kolejki execute/compensate + konsumenta zdarzeń
dotnet run --no-build -- inspect      # pokazuje topologię (bez ruchu jeszcze)
dotnet run --no-build -- run ok       # kwota 250 zł (limit 1000 zł) - obie aktywności OK, RoutingSlipCompleted
dotnet run --no-build -- run fail     # kwota 1500 zł - ChargePayment rzuca wyjątek, ReserveInventory
                                       # zostaje SKOMPENSOWANE, RoutingSlipFaulted
dotnet run --no-build -- inspect      # (po ok. 6 s, patrz "Uwagi") kolejki znów puste, consumers=0
```

### 3. Posprzątaj

```bash
docker stop mt-routingslip-demo && docker rm mt-routingslip-demo
# (lub `docker compose -f days/2026-09-30/masstransit/code/docker-compose.yml down -v`,
# jeśli stawiałeś przez compose)
```

## Zweryfikowany output (prawdziwe uruchomienie, ten sam broker przez cały czas)

```
$ dotnet run --no-build -- topology
=== TOPOLOGY: startuję hosta z aktywnościami Couriera - MassTransit deklaruje kolejki execute/compensate na RabbitMQ ===
[     0 ms] bus wystartował, topologia (2 aktywności + konsument zdarzeń) zadeklarowana na brokerze
[   685 ms] host zatrzymany (proces zaraz się kończy) - kolejki na brokerze ZOSTAJĄ, bo są trwałe

$ dotnet run --no-build -- run ok
=== RUN OK: routing slip zamówienia, kwota płatności = 250.00 zł (limit karty = 1000 zł) ===
[     0 ms] adres execute ReserveInventory = queue:reserve-inventory_execute
[     7 ms] adres execute ChargePayment    = queue:charge-payment_execute
[     7 ms] adres konsumenta zdarzeń       = queue:routing-slip-events
[    73 ms] wysyłam routing slip 021452dc-5ee7-4495-b90a-38d13e36a384 dla zamówienia a4e247b4 (itinerary: ReserveInventory -> ChargePayment)
[   911 ms] [ReserveInventory]  EXECUTE   rezerwuję 2x ABC-1 dla zamówienia a4e247b4
[  1038 ms] [ChargePayment]     EXECUTE   próbuję obciążyć 250.00 zł za zamówienie a4e247b4
[  1038 ms] [ChargePayment]     EXECUTE   płatność zaakceptowana
[  1102 ms] [EVENTS] RoutingSlipCompleted 021452dc-5ee7-4495-b90a-38d13e36a384 po 1030 ms - WSZYSTKIE aktywności ukończone, nic nie kompensowano
[  3915 ms] koniec okna obserwacji

$ dotnet run --no-build -- run fail
=== RUN FAIL: routing slip zamówienia, kwota płatności = 1500.00 zł (limit karty = 1000 zł) ===
[     0 ms] adres execute ReserveInventory = queue:reserve-inventory_execute
[     0 ms] adres execute ChargePayment    = queue:charge-payment_execute
[     0 ms] adres konsumenta zdarzeń       = queue:routing-slip-events
[    67 ms] wysyłam routing slip 2e25737d-0b71-4a06-ab5d-de06e6f6e31f dla zamówienia bf8f6b90 (itinerary: ReserveInventory -> ChargePayment)
[   955 ms] [ReserveInventory]  EXECUTE   rezerwuję 2x ABC-1 dla zamówienia bf8f6b90
[  1071 ms] [ChargePayment]     EXECUTE   próbuję obciążyć 1500.00 zł za zamówienie bf8f6b90
[  1071 ms] [ChargePayment]     EXECUTE   karta ODRZUCONA (kwota 1500.00 zł > limit 1000 zł)
[  1304 ms] [ReserveInventory]  COMPENSATE  zwalniam rezerwację 2x ABC-1 dla zamówienia bf8f6b90 - dalszy krok routing slipa zawiódł
[  1357 ms] [EVENTS] RoutingSlipFaulted 2e25737d-0b71-4a06-ab5d-de06e6f6e31f po 1299 ms - transakcja NIE powiodła się, kompensacja poprzednich aktywności już wykonana
[  1358 ms] [EVENTS]   aktywność 'ChargePayment' rzuciła: System.InvalidOperationException: Karta odrzucona dla kwoty 1500.00 zł
[  3957 ms] koniec okna obserwacji

$ dotnet run --no-build -- inspect
=== INSPECT: co MassTransit naprawdę utworzył na brokerze (REST API management plugin) ===
--- exchange'y (bez wbudowanych amq.*) ---
  exchange 'MassTransit.Courier.Contracts:RoutingSlipCompleted'  typ=fanout  durable=True
  exchange 'MassTransit.Courier.Contracts:RoutingSlipFaulted'  typ=fanout  durable=True
  exchange 'MassTransit:Fault'  typ=fanout  durable=True
  exchange 'MassTransit:Fault--MassTransit.Courier.Contracts:RoutingSlip--'  typ=fanout  durable=True
  exchange 'charge-payment_execute'  typ=fanout  durable=True
  exchange 'reserve-inventory_compensate'  typ=fanout  durable=True
  exchange 'reserve-inventory_execute'  typ=fanout  durable=True
  exchange 'routing-slip-events'  typ=fanout  durable=True
--- kolejki ---                                                            # ZARAZ po run fail - PUŁAPKA
  kolejka 'reserve-inventory_execute'  durable=True  messages_ready=0  unacked=0  consumers=1   # nieaktualne!

$ sleep 6 && dotnet run --no-build -- inspect   # po odczekaniu - dopiero teraz widać prawdę
--- kolejki ---
  kolejka 'charge-payment_execute'  durable=True  messages_ready=0  unacked=0  consumers=0
  kolejka 'reserve-inventory_compensate'  durable=True  messages_ready=0  unacked=0  consumers=0
  kolejka 'reserve-inventory_execute'  durable=True  messages_ready=0  unacked=0  consumers=0
  kolejka 'routing-slip-events'  durable=True  messages_ready=0  unacked=0  consumers=0
--- bindingi (exchange -> kolejka), bez amq.* ---
  'MassTransit.Courier.Contracts:RoutingSlipCompleted' --[routing_key='']--> exchange 'routing-slip-events'
  'MassTransit.Courier.Contracts:RoutingSlipFaulted' --[routing_key='']--> exchange 'routing-slip-events'
  'MassTransit:Fault--MassTransit.Courier.Contracts:RoutingSlip--' --[routing_key='']--> exchange 'MassTransit:Fault'
  'charge-payment_execute' --[routing_key='']--> queue 'charge-payment_execute'
  'reserve-inventory_compensate' --[routing_key='']--> queue 'reserve-inventory_compensate'
  'reserve-inventory_execute' --[routing_key='']--> queue 'reserve-inventory_execute'
  'routing-slip-events' --[routing_key='']--> queue 'routing-slip-events'
```

Sprawdzone także niezależnie przez `docker exec mt-routingslip-demo rabbitmqctl list_queues name
durable messages consumers` i `rabbitmqctl list_exchanges name type durable` - te same nazwy, te
same liczby. Lokalnie: .NET SDK 10.0.400, MassTransit 8.5.10 + MassTransit.RabbitMQ 8.5.10, RabbitMQ
`4.3-management` w Dockerze.

### Uwagi

- **COMPENSATE zawsze leci przed `RoutingSlipFaulted`** (w logu: 1304 ms vs 1357 ms) - MassTransit
  gwarantuje, że system wróci do spójnego stanu, zanim ktokolwiek na zewnątrz dowie się o porażce.
- `reserve-inventory_execute`/`charge-payment_execute` **nie mają** osobnego "exchange'a wiadomości"
  (jak `OrderSubmitted` w wydaniu #5) - `RoutingSlip` trafia tam wyłącznie przez adresowany `Send`,
  nie `Publish`. Za to `RoutingSlipCompleted`/`RoutingSlipFaulted` mają pełny łańcuch exchange
  wiadomości → exchange kolejki → kolejka, bo `RoutingSlipEventsConsumer` to zwykły `IConsumer<T>`.
  Niespodzianka: `MassTransit:Fault--...RoutingSlip--` (transportowy `Fault<T>` z wydania #2) też
  został zadeklarowany automatycznie - nic tam nie trafiło (kurierowy `RoutingSlipFaulted` to osobny
  mechanizm), ale sama topologia istnieje.
- Opóźnienie statystyk REST API z wydania #5 (`messages_ready`) dotyczy też licznika `consumers` -
  `inspect` zaraz po `run fail` pokazał `consumers=1` na kolejce, z którą żaden proces już się nie
  łączył; dopiero po ok. 6 s pokazał `consumers=0`.
- `TActivity` musi implementować dokładnie interfejs `IActivity<TArguments, TLog>` (nie wystarczy
  osobno `IExecuteActivity<TArguments>` + `ICompensateActivity<TLog>` na tej samej klasie) - inaczej
  `AddActivity<TActivity, TArguments, TLog>()` nie skompiluje się (błąd CS0311, sprawdzone realnie).
- Niezweryfikowane: kompensacja, która sama zawodzi (`context.Failed(ex)`), itinerary z 3+
  aktywnościami, `ReviseItinerary`, trwałe repozytoria sag (RoutingSlip jest bezstanowy - plan leci
  w samej wiadomości, to osobny temat), interakcja z `UseMessageRetry` z wydania #2,
  `ConcurrentMessageLimit` z wydania #4 na aktywnościach, topic/direct exchange, klaster, TLS/AMQPS.
- `.gitignore` w `code/` pomija `bin/` i `obj/`.
