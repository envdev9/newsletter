# Kod do wydania #5 — MassTransit: prawdziwy RabbitMQ zamiast in-memory

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej fragment artykułu + jak odpalić kod od zera.

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`), **Docker** (działający silnik + wolne
ok. 150 MB na obraz `rabbitmq:4.3-management`, jeśli nie masz go już w cache).

## Fragment prasówki, którego dotyczy ten kod

> Do tej pory wszystkie cztery wydania tej rubryki używały transportu `UsingInMemory` — wygodnego
> do nauki, ale fundamentalnie innego niż produkcja: kolejka in-memory to zwykła kolekcja w RAM-ie
> tego samego procesu. Zamieniamy `cfg.UsingInMemory(...)` na `cfg.UsingRabbitMq(...)` i pokazujemy
> dwie rzeczy, których in-memory pokazać nie mogło: **prawdziwą topologię** na brokerze (exchange
> wiadomości → exchange kolejki → kolejka, wszystko utworzone automatycznie przez
> `ConfigureEndpoints`) oraz **trwałość niezależną od procesu klienta** — wiadomości opublikowane,
> gdy żaden konsument nie istniał, czekają na durable kolejce i zostają odebrane przez zupełnie
> nowy proces uruchomiony później.

## Struktura projektu

```
code/
├── docker-compose.yml               # RabbitMQ 4.3 + plugin management (porty 5672, 15672)
├── .gitignore                       # pomija bin/, obj/
└── masstransit-rabbitmq-demo/
    ├── MassTransitRabbitMqDemo.csproj  # MassTransit 8.5.10 + MassTransit.RabbitMQ 8.5.10
    ├── Contracts.cs                    # OrderSubmitted, OrderConsumer, Log
    └── Program.cs                      # 4 tryby: topology / publish / consume / inspect
```

Jeden projekt, cztery tryby uruchomienia (`dotnet run -- <tryb>`) — bo żeby uczciwie pokazać
trwałość na brokerze, potrzeba **osobnych procesów**, nie jednego `dotnet run` jak w poprzednich
wydaniach na in-memory.

## Jak uruchomić od zera

### 1. Postaw RabbitMQ

Najpewniejsza opcja - zwykły `docker run` (dokładnie to polecenie zweryfikowałem realnym
uruchomieniem w tej sesji; ani `docker compose`, ani samodzielny `docker-compose` nie były dostępne
w środowisku, w którym budowałem to demo, więc plik niżej NIE był odpalony przez compose - patrz
uwaga pod spodem):

```bash
docker run -d --name mt-rabbit-demo -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=newsletter_dev \
  -e RABBITMQ_DEFAULT_PASS=newsletter_dev_local_only \
  rabbitmq:4.3-management
# poczekaj ok. 15 s na start, potem sprawdź:
docker exec mt-rabbit-demo rabbitmq-diagnostics -q ping
# UI managementu: http://localhost:15672 (login: newsletter_dev / newsletter_dev_local_only)
```

Jeśli masz działający `docker compose`/`docker-compose`, ten sam efekt powinien dać (te same
parametry, ten sam obraz):

```bash
docker compose -f days/2026-09-28/masstransit/code/docker-compose.yml up -d
```

> ⚠️ **Niezweryfikowane**: `docker-compose.yml` obok tego README **nie zostało uruchomione przez
> narzędzie compose** - w tej sesji `docker compose` zwracał `unknown command`, a standalone
> `docker-compose` był zablokowany przez politykę sandboksa. Plik zawiera dokładnie te same
> parametry co przetestowany `docker run` powyżej, więc *powinien* działać identycznie, ale nie
> mam na to realnego outputu - użyj `docker run`, jeśli chcesz mieć pewność zweryfikowaną w tym
> wydaniu.

> ⚠️ Login `newsletter_dev` / `newsletter_dev_local_only` to dane **wyłącznie deweloperskie**,
> tworzone lokalnie przez `docker-compose.yml` na czas tego demo — nie domyślne `guest/guest`
> i nie żaden sekret produkcyjny. Zobacz komentarz w `docker-compose.yml`, dlaczego świadomie
> unikamy tu `guest`.

### 2. Zbuduj i uruchom kolejne tryby (w tej kolejności)

```bash
export PATH="$HOME/.dotnet:$PATH"        # jeśli SDK jest w ~/.dotnet
cd days/2026-09-28/masstransit/code/masstransit-rabbitmq-demo
dotnet build

dotnet run --no-build -- topology        # tworzy exchange/kolejkę/binding, potem się kończy
dotnet run --no-build -- inspect         # pokazuje topologię i 0 wiadomości w kolejce
dotnet run --no-build -- publish 4       # PROCES BEZ KONSUMENTA publikuje 4 wiadomości i kończy się
dotnet run --no-build -- inspect         # kolejka ma 4 wiadomości, 0 podłączonych konsumentów
dotnet run --no-build -- consume 3       # NOWY proces, 3 s okna, odbiera to co czekało
dotnet run --no-build -- inspect         # (po ok. 5-6 s, patrz "Uwagi") kolejka znów pusta
```

### 3. Posprzątaj

```bash
docker stop mt-rabbit-demo && docker rm mt-rabbit-demo
# (lub `docker compose -f days/2026-09-28/masstransit/code/docker-compose.yml down -v`,
# jeśli stawiałeś przez compose)
```

## Zweryfikowany output (prawdziwe uruchomienie, ten sam broker przez cały czas)

```
$ dotnet run --no-build -- publish 4
=== PUBLISH: proces bez konsumenta publikuje 4 wiadomości i kończy się ===
[     0 ms] opublikowano zamówienie f4a6bbdff1fd499e9cedcaa585dba06e (ABC-1 x1)
[     4 ms] opublikowano zamówienie 3a4a077648ce47e39f4792338d21b9a0 (XYZ-9 x2)
[     7 ms] opublikowano zamówienie 755f309f45734afc8848c40f0be041b1 (ABC-1 x3)
[    12 ms] opublikowano zamówienie d7d37839e8ba416cb5335b608d43d0c9 (XYZ-9 x4)
[   171 ms] proces publikujący KOŃCZY SIĘ (Environment.Exit) - żaden konsument w tym demie jeszcze nie działał

$ dotnet run --no-build -- inspect
=== INSPECT: co MassTransit naprawdę utworzył na brokerze (REST API management plugin) ===
--- exchange'y (bez wbudowanych amq.*) ---
  exchange 'MassTransitRabbitMqDemo:OrderSubmitted'  typ=fanout  durable=True
  exchange 'Order'  typ=fanout  durable=True
--- kolejki ---
  kolejka 'Order'  durable=True  messages_ready=4  unacked=0  consumers=0
--- bindingi (exchange -> kolejka), bez amq.* ---
  'MassTransitRabbitMqDemo:OrderSubmitted' --[routing_key='']--> exchange 'Order'
  'Order' --[routing_key='']--> queue 'Order'

$ dotnet run --no-build -- consume 3
=== CONSUME: nowy proces startuje konsumenta i przez 3s odbiera zaległe wiadomości ===
[     0 ms] bus wystartował - zaraz zacznie odbierać to, co leżało w kolejce, zanim ten proces w ogóle istniał
[   590 ms] OrderConsumer: zamówienie 3a4a077648ce47e39f4792338d21b9a0 (XYZ-9 x2), kolejka wejściowa = /Order
[   591 ms] OrderConsumer: zamówienie f4a6bbdff1fd499e9cedcaa585dba06e (ABC-1 x1), kolejka wejściowa = /Order
[   626 ms] OrderConsumer: zamówienie 755f309f45734afc8848c40f0be041b1 (ABC-1 x3), kolejka wejściowa = /Order
[   626 ms] OrderConsumer: zamówienie d7d37839e8ba416cb5335b608d43d0c9 (XYZ-9 x4), kolejka wejściowa = /Order
[  3112 ms] koniec okna odbioru - ten proces odebrał łącznie 4 wiadomości
```

Cztery GUID-y w `consume` to dokładnie te same GUID-y, które wylogował proces `publish` — minuty
wcześniej, w procesie który już nie istnieje. Sprawdzone lokalnie: .NET SDK 10.0.400, MassTransit
8.5.10 + MassTransit.RabbitMQ 8.5.10, RabbitMQ `4.3-management` w Dockerze.

### Uwagi

- **Stan zarządzania (`inspect`) jest opóźniony o kilka sekund.** Odpalone `inspect` *natychmiast*
  po `consume` pokazało jeszcze `messages_ready=4` (stara wartość) — dopiero po ok. 5-6 s API
  managementu pokazało `0`. To nie błąd tego kodu: RabbitMQ odświeża statystyki w UI/REST co kilka
  sekund (nie na żywo), więc `inspect` tuż po operacji może kłamać. Realny stan kolejki (czy broker
  faktycznie doręczył i zaackował) widać dopiero po tym opóźnieniu.
- Domyślny `EndpointNameFormatter` (bez `SetEndpointNameFormatter`, w przeciwieństwie do wydania #4)
  nazwał kolejkę `Order` (PascalCase, obcięte "Consumer"), nie kebab-case — to zachowanie samego
  MassTransit, nie coś skonfigurowanego ręcznie w tym kodzie.
- Niezweryfikowane: `guest/guest` **zadziałał** w tym demie przez port Dockera (nie potwierdzone
  ograniczenie `loopback_users`, którego się spodziewano) — ale to zależy od konfiguracji sieci
  Dockera na danej maszynie, więc traktuj to jako obserwację z tej jednej sesji, nie regułę.
- Niezweryfikowane: retry/error queue (`_error`, wydanie #2) na prawdziwym RabbitMQ, `RoutingSlip`/
  Courier, trwałe repozytoria sag, `topic`/`direct` exchange zamiast domyślnego `fanout`, klaster
  RabbitMQ, TLS/AMQPS.
- `.gitignore` w `code/` pomija `bin/` i `obj/`.
