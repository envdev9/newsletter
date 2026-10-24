# Kod do wydania #12 — MassTransit: `_error`/`_skipped` na prawdziwym RabbitMQ

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej fragment artykułu + jak odpalić kod od zera.

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`), **Docker** (działający silnik + wolne ok.
150 MB na obraz `rabbitmq:4.3-management`, jeśli nie masz go już w cache).

## Fragment prasówki, którego dotyczy ten kod

> W wydaniu #2 (in-memory) ustaliliśmy teorię: `UseMessageRetry` próbuje ponownie w tym samym
> procesie, a gdy to nie pomoże, wiadomość trafia do `Fault<T>` i kolejki `<endpoint>_error`;
> `_skipped` to zupełnie inny przypadek - wiadomość, której **nikt na endpointcie nie umie
> skonsumować**. Transport in-memory nie ma jednak trwałości - te kolejki znikały wraz z procesem.
> Dziś, po czterech wydaniach na prawdziwym RabbitMQ, domykamy tę teorię **dowodem**: stawiamy
> broker, odpalamy proces, który świadomie pada z błędem, **zabijamy go**, i w **zupełnie nowym,
> niezależnym procesie** sprawdzamy, co broker naprawdę zapamiętał - łącznie z treścią wiadomości
> i nagłówkami `MT-*`. Po drodze obalamy jedno błędne przypuszczenie, które zrobiliśmy przy pisaniu
> tego kodu: `Ignore<T>` NIE idzie do `_skipped` - idzie PROSTO do `_error`, bez retry.

## Struktura projektu

```
code/
├── docker-compose.yml                     # RabbitMQ 4.3 + plugin management (porty 5672, 15672)
├── .gitignore                             # pomija bin/, obj/
└── masstransit-retry-error-demo/
    ├── MassTransitRetryErrorDemo.csproj      # MassTransit 8.5.10 + MassTransit.RabbitMQ 8.5.10
    ├── Contracts.cs                          # 3 konsumentów + 3 ConsumerDefinition z UseMessageRetry
    │                                         # FlakyConsumer       - 2 porażki, 3. próba OK (Interval)
    │                                         # AlwaysFailingConsumer - błąd trwały -> _error
    │                                         # SkippableConsumer   - Ignore<T> -> _error, BEZ retry
    └── Program.cs                             # 5 trybów: topology / inspect / run <flaky|fail|skip|orphan> / peek <kolejka>
```

## Jak uruchomić od zera

### 1. Postaw RabbitMQ

```bash
docker run -d --name mt-retry-error-demo -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=newsletter_dev \
  -e RABBITMQ_DEFAULT_PASS=newsletter_dev_local_only \
  rabbitmq:4.3-management
# poczekaj ok. 15 s na start, potem sprawdź:
docker exec mt-retry-error-demo rabbitmq-diagnostics -q ping
# UI managementu: http://localhost:15672 (login: newsletter_dev / newsletter_dev_local_only)
```

Jeśli masz działający `docker compose`/`docker-compose` (w środowisku, w którym budowałem to demo,
żaden z nich nie był dostępny - `docker: unknown command: docker compose` - więc plik niżej **nie
został uruchomiony przez compose**, tylko przez równoważny `docker run` powyżej):

```bash
docker compose -f days/2026-10-05/masstransit/code/docker-compose.yml up -d
```

> ⚠️ Login `newsletter_dev` / `newsletter_dev_local_only` to dane **wyłącznie deweloperskie**, takie
> same jak w poprzednich wydaniach - nie `guest/guest`, nie żaden sekret produkcyjny.

### 2. Zbuduj i uruchom kolejne tryby (w tej kolejności)

```bash
cd days/2026-10-05/masstransit/code/masstransit-retry-error-demo
dotnet build

dotnet run --no-build -- topology       # deklaruje 3 kolejki GŁÓWNE (bez _error/_skipped - te są leniwe)
dotnet run --no-build -- inspect        # potwierdza: tylko 3 kolejki, żadnych _error/_skipped jeszcze

dotnet run --no-build -- run flaky      # 2 porażki, 3. próba OK - retry w tym samym procesie
dotnet run --no-build -- run fail       # błąd trwały -> po 3 próbach trafia do 'always-failing_error'
dotnet run --no-build -- run skip       # Ignore<T> -> BEZ retry, od razu do 'skippable_error'
dotnet run --no-build -- run orphan     # wysyła typ bez konsumenta na kolejkę 'flaky' -> 'flaky_skipped'

dotnet run --no-build -- inspect        # NOWY proces - 3 kolejki błędów/skip mają messages_ready=1,
                                         # consumers=0, mimo że żaden z powyższych procesów już nie żyje

dotnet run --no-build -- peek flaky_skipped          # treść + nagłówki (MT-Reason=dead-letter)
dotnet run --no-build -- peek always-failing_error   # treść + nagłówki (MT-Reason=fault, RetryCount=2)
dotnet run --no-build -- peek skippable_error        # treść + nagłówki (MT-Reason=fault, BEZ RetryCount)
```

### 3. Posprzątaj

```bash
docker stop mt-retry-error-demo && docker rm mt-retry-error-demo
# (lub `docker compose -f days/2026-10-05/masstransit/code/docker-compose.yml down -v`,
# jeśli stawiałeś przez compose)
```

## Zweryfikowany output (prawdziwe uruchomienie, ten sam broker przez cały czas, chronologicznie)

```
$ dotnet run --no-build -- topology
=== TOPOLOGY: startuję hosta - MassTransit deklaruje kolejki GŁÓWNE na RabbitMQ (_error/_skipped powstają leniwie) ===
[     0 ms] bus wystartował, topologia (3 konsumentów) zadeklarowana na brokerze
[   510 ms] host zatrzymany - kolejki NA BROKERZE zostają, bo są trwałe (durable)

$ dotnet run --no-build -- inspect
=== INSPECT: co broker naprawdę ma w kolejkach _error/_skipped - BEZ ŻADNEGO podłączonego konsumenta ===
--- kolejki (główne + _error/_skipped) ---
  kolejka 'always-failing'  durable=True  messages_ready=0  unacked=0  consumers=0
  kolejka 'flaky'  durable=True  messages_ready=0  unacked=0  consumers=0
  kolejka 'skippable'  durable=True  messages_ready=0  unacked=0  consumers=0
--- exchange'y związane z błędami/retry (Fault, bez wbudowanych amq.*) ---
                                                           # (puste - jeszcze nic nie zawiodło)

$ dotnet run --no-build -- run flaky
=== RUN FLAKY: 48815418 zawiedzie 2 razy, uda się przy 3. próbie (UseMessageRetry.Interval) ===
[     0 ms] [Flaky]          próba 1/3 dla 48815418 - wyjątek PRZEJŚCIOWY, retry za chwilę
[   324 ms] [Flaky]          próba 2/3 dla 48815418 - wyjątek PRZEJŚCIOWY, retry za chwilę
[   641 ms] [Flaky]          próba 3/3 dla 48815418 - SUKCES, retry nie jest już potrzebny
[  2056 ms] host ZATRZYMANY (proces się kończy) - żaden konsument już nie jest podłączony do brokera

$ dotnet run --no-build -- run fail
=== RUN FAIL: 1fd64b81 zawiedzie TRWALE - po 2 retry MassTransit przenosi wiadomość do kolejki _error ===
[     0 ms] [AlwaysFailing]  próba 1 dla 1fd64b81 - błąd TRWAŁY, nigdy się nie uda
[   226 ms] [AlwaysFailing]  próba 2 dla 1fd64b81 - błąd TRWAŁY, nigdy się nie uda
[   434 ms] [AlwaysFailing]  próba 3 dla 1fd64b81 - błąd TRWAŁY, nigdy się nie uda
[  2063 ms] host ZATRZYMANY (proces się kończy) - żaden konsument już nie jest podłączony do brokera

$ dotnet run --no-build -- run skip
=== RUN SKIP: afe9ef54 to znane-złe dane (Ignore<KnownBadDataException>) - BEZ retry, ale wciąż do _error ===
[     0 ms] [Skippable]      afe9ef54 - dane znane jako złe, retry nie ma sensu
[  1064 ms] host ZATRZYMANY (proces się kończy) - żaden konsument już nie jest podłączony do brokera

$ dotnet run --no-build -- run orphan
=== RUN ORPHAN: f1a73619 - wysyłam NobodyConsumesThis WPROST na kolejkę 'flaky', która go nie konsumuje -> prawdziwa kolejka _skipped na RabbitMQ ===
[     0 ms] host ZATRZYMANY (proces się kończy) - żaden konsument już nie jest podłączony do brokera

$ dotnet run --no-build -- inspect        # NOWY proces, zero konsumentów podłączonych do czegokolwiek
=== INSPECT: co broker naprawdę ma w kolejkach _error/_skipped - BEZ ŻADNEGO podłączonego konsumenta ===
--- kolejki (główne + _error/_skipped) ---
  kolejka 'always-failing'  durable=True  messages_ready=0  unacked=0  consumers=0
  kolejka 'always-failing_error'  durable=True  messages_ready=1  unacked=0  consumers=0
  kolejka 'flaky'  durable=True  messages_ready=0  unacked=0  consumers=0
  kolejka 'flaky_skipped'  durable=True  messages_ready=1  unacked=0  consumers=0
  kolejka 'skippable'  durable=True  messages_ready=0  unacked=0  consumers=0
  kolejka 'skippable_error'  durable=True  messages_ready=1  unacked=0  consumers=0
--- exchange'y związane z błędami/retry (Fault, bez wbudowanych amq.*) ---
  exchange 'MassTransit:Fault'  typ=fanout  durable=True
  exchange 'MassTransit:Fault--MassTransitRetryErrorDemo:KnownBadData--'  typ=fanout  durable=True
  exchange 'MassTransit:Fault--MassTransitRetryErrorDemo:PermanentFailure--'  typ=fanout  durable=True

$ docker exec mt-retry-error-demo rabbitmqctl list_queues name durable messages consumers
name                    durable  messages  consumers
flaky_skipped           true     1         0
skippable               true     0         0
always-failing_error    true     1         0
skippable_error         true     1         0
always-failing          true     0         0
flaky                   true     0         0
                                                           # identyczne liczby jak w REST API

$ dotnet run --no-build -- peek flaky_skipped
=== PEEK: zaglądam do kolejki 'flaky_skipped' przez REST API (requeue=true, nic nie usuwam) ===
  wiadomość #1 (payload, pierwsze 200 znaków): { "messageId": "...", ... }
    header MT-Host-MassTransitVersion = 8.5.10.0
    header MT-Reason = dead-letter                         # BRAK jakiegokolwiek MT-Fault-*

$ dotnet run --no-build -- peek always-failing_error
=== PEEK: zaglądam do kolejki 'always-failing_error' przez REST API (requeue=true, nic nie usuwam) ===
    header MT-Fault-ConsumerType = MassTransitRetryErrorDemo.AlwaysFailingConsumer
    header MT-Fault-ExceptionType = MassTransitRetryErrorDemo.OrderRejectedException
    header MT-Fault-Message = Zamówienie 1fd64b81 trwale odrzucone
    header MT-Fault-MessageType = MassTransitRetryErrorDemo.PermanentFailure
    header MT-Fault-RetryCount = 2                          # 2 PONOWIENIA faktycznie się odbyły
    header MT-Reason = fault

$ dotnet run --no-build -- peek skippable_error
=== PEEK: zaglądam do kolejki 'skippable_error' przez REST API (requeue=true, nic nie usuwam) ===
    header MT-Fault-ConsumerType = MassTransitRetryErrorDemo.SkippableConsumer
    header MT-Fault-ExceptionType = MassTransitRetryErrorDemo.KnownBadDataException
    header MT-Fault-Message = Dane afe9ef54 są znane jako złe
    header MT-Fault-MessageType = MassTransitRetryErrorDemo.KnownBadData
    header MT-Reason = fault                                # BRAK MT-Fault-RetryCount - retry nigdy
                                                             # nie wystartował (Ignore<T>), nie "zużył się"

$ dotnet run --no-build -- inspect        # kontrolne - po peek z requeue=true liczby się NIE zmieniły
  kolejka 'always-failing_error'  durable=True  messages_ready=1  unacked=0  consumers=0
  kolejka 'flaky_skipped'  durable=True  messages_ready=1  unacked=0  consumers=0
  kolejka 'skippable_error'  durable=True  messages_ready=1  unacked=0  consumers=0
```

Lokalnie: .NET SDK **10.0.400**, MassTransit **8.5.10** + MassTransit.RabbitMQ **8.5.10**, RabbitMQ
`4.3-management` w Dockerze. `dotnet build` - **0 Warning(s), 0 Error(s)** (po dodaniu trzeciego
parametru `IRegistrationContext` do `ConfigureConsumer` - bez niego kompiluje się też, ale z
warningiem CS0672, bo dwuparametrowa sygnatura jest `[Obsolete]` w tej wersji MassTransit).

### Uwagi / sprostowanie w trakcie pisania tego kodu

- **`Ignore<TException>()` NIE wysyła do `_skipped`.** Idzie do `_error`, tak jak każdy inny fault -
  różnica jest tylko w tym, że retry nigdy nie wystartował (stąd brak nagłówka
  `MT-Fault-RetryCount`, nie "RetryCount=0"). `_skipped` to wyłącznie przypadek "żaden `IConsumer<T>`
  na endpointcie nie obsługuje tego typu wiadomości" (nagłówek `MT-Reason=dead-letter`, zero
  nagłówków `MT-Fault-*`, bo nigdy nie wystąpił żaden wyjątek).
- Kolejki `_error`/`_skipped` **nie są tworzone z góry** przy starcie hosta - `inspect` zaraz po
  `topology` pokazuje tylko 3 kolejki główne. Powstają leniwie, w momencie pierwszego użycia.
- `POST /api/queues/%2f/<kolejka>/get` z `ackmode: "ack_requeue_true"` pozwala przeczytać treść i
  nagłówki wiadomości bez jej usuwania - potwierdzone przez `inspect` przed/po (`messages_ready`
  się nie zmienia).
- `rabbitmqctl list_queues name durable messages consumers` w kontenerze zgadza się 1:1 z REST API
  management plugin.
- Niezweryfikowane: `UseDelayedRedelivery` na prawdziwym RabbitMQ, interakcja z
  `ConcurrentMessageLimit`/Courierem, trwałe repozytoria sag, topic/direct exchange, klaster,
  TLS/AMQPS, zachowanie `_error`/`_skipped` pod dużym wolumenem wiadomości.
- `.gitignore` w `code/` pomija `bin/` i `obj/`.
