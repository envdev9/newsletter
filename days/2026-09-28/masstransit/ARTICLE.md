<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #5 — 28 września 2026

![MassTransit](https://img.shields.io/badge/MassTransit-FF6600?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Transport](https://img.shields.io/badge/transport-RabbitMQ-orange?style=for-the-badge)

## 📨 Prawdziwy broker: RabbitMQ, topologia i trwałość, której in-memory nigdy nie miał

</div>

---

> _"Kolejka in-memory umiera razem z procesem. Kolejka na brokerze - nie."_

Cztery poprzednie wydania tej rubryki - `Publish`/`Send`, retry/`Fault`, sagi, routing/filtry -
uczyły się MassTransit na transporcie `UsingInMemory`. Wygodne do nauki, ale ukrywające coś
fundamentalnego: kolejka in-memory to zwykła kolekcja w RAM-ie *tego samego procesu*. Dziś pierwszy
raz w tej rubryce podłączamy się do **prawdziwego RabbitMQ w Dockerze** i pokazujemy dwie rzeczy,
których in-memory pokazać nie mógł: **topologię** utworzoną automatycznie na brokerze i
**trwałość niezależną od tego, czy jakikolwiek proces klienta w ogóle istnieje**. Kod:
[`code/`](code/), MassTransit **8.5.10** + `MassTransit.RabbitMQ` **8.5.10**, RabbitMQ
`4.3-management` w Dockerze, .NET 10, output prawdziwy.

## 🎯 Dlaczego to ważne

Na in-memory "kolejka" znika, gdy proces się kończy - więc demo zawsze musiało publikować i
konsumować w tym samym `dotnet run`. Na RabbitMQ kolejka **żyje na brokerze**, niezależnie od tego,
ile razy Twoja aplikacja się wywali, zrestartuje albo w ogóle nie zostanie jeszcze napisana. To
zmienia sposób myślenia o deployu: możesz wypuścić producenta bez konsumenta (wiadomości poczekają),
zrestartować konsumenta w trakcie ruchu (nic nie ginie) i zobaczyć realną topologię - exchange'e i
bindingi - w narzędziach operacyjnych (`rabbitmqctl`, REST API managementu), zamiast zgadywać, co
"pod maską" robi in-memory transport.

| Pojęcie | Co robi | W naszym demie |
|---|---|---|
| 🔌 **`cfg.UsingRabbitMq(...)`** | zamiana transportu, ta sama reszta API | `cfg.Host("localhost", "/", h => {...})` |
| 🏛️ **Exchange wiadomości** | fanout-exchange nazwany wg typu wiadomości | `MassTransitRabbitMqDemo:OrderSubmitted` |
| 🧱 **Exchange kolejki** | pośredni fanout-exchange o nazwie kolejki | `Order` |
| 📥 **Kolejka** | trwała (`durable=true`), przeżywa restart klienta | `Order`, `durable=True` |
| 🔎 **REST API managementu** | podgląd topologii i liczników bez GUI | `/api/exchanges`, `/api/queues`, `/api/bindings` |
| 💾 **Trwałość** | wiadomość czeka na brokerze bez żadnego konsumenta | `publish` bez konsumenta → `consume` w nowym procesie |

---

## 🔌 1. Migracja: jedna metoda, nie architektura

Kontrakt (`OrderSubmitted`) i consumer (`OrderConsumer`) wyglądają identycznie jak na in-memory.
Zmienia się tylko konfiguracja transportu:

```csharp
builder.Services.AddMassTransit(x =>
{
    x.AddConsumer<OrderConsumer>();

    x.UsingRabbitMq((context, cfg) =>
    {
        cfg.Host("localhost", "/", h =>
        {
            h.Username("newsletter_dev");   // NIE "guest" - patrz sekcja 4
            h.Password("newsletter_dev_local_only");
        });

        cfg.ConfigureEndpoints(context);    // dokładnie ta sama linia co na in-memory
    });
});
```

`ConfigureEndpoints` z wydania #4 to ta sama metoda, ale na RabbitMQ robi dużo więcej niż na
in-memory: **deklaruje realną topologię na brokerze** (exchange, kolejkę, binding) - trwale,
niezależnie od życia procesu.

## 🏛️ 2. Topologia: co MassTransit naprawdę utworzył

Po uruchomieniu samego konsumenta (`dotnet run -- topology`) i wywołaniu REST API managementu
(`http://localhost:15672/api/exchanges/%2f` itd.), widać **trzy węzły**, nie jeden:

```
--- exchange'y ---
  exchange 'MassTransitRabbitMqDemo:OrderSubmitted'  typ=fanout  durable=True
  exchange 'Order'                                    typ=fanout  durable=True
--- kolejki ---
  kolejka 'Order'  durable=True  messages_ready=0  unacked=0  consumers=0
--- bindingi ---
  'MassTransitRabbitMqDemo:OrderSubmitted' --[routing_key='']--> exchange 'Order'
  'Order' --[routing_key='']--> queue 'Order'
```

MassTransit nie wiąże exchange'a wiadomości bezpośrednio z kolejką - wstawia **pośredni exchange o
nazwie kolejki**. Dzięki temu wiele typów wiadomości może trafiać do jednej kolejki (każdy typ ma
swój exchange, wszystkie zbindowane do tego samego exchange'a kolejki), bez przebudowywania samej
kolejki. Potwierdzone niezależnie dwoma narzędziami - REST API i `rabbitmqctl list_exchanges` /
`list_bindings` w kontenerze - dały te same nazwy i te same bindingi.

> ⚠️ **Pułapka: domyślna nazwa kolejki to `Order`, nie `order` ani `order-consumer`.** Bez
> `SetEndpointNameFormatter` (który w wydaniu #4 wymuszał kebab-case) domyślny formatter po prostu
> obcina sufiks `Consumer` z nazwy klasy i **zostawia PascalCase**. Na RabbitMQ to widać wprost w
> nazwie kolejki - jeśli chcesz kebab-case jak poprzednio, trzeba go jawnie ustawić także tutaj
> (nie sprawdzałem, czy formatter zmienia coś w samej strukturze exchange-exchange-kolejka, tylko
> nazewnictwo).

## 💾 3. Trwałość: wiadomości czekają, choć żaden klient jeszcze nie istniał

To jest test, którego in-memory w ogóle nie da się zrobić: **trzy osobne procesy**, w tej
kolejności.

**Proces A (`publish 4`)** - bus bez zarejestrowanego konsumenta, tylko publikuje i kończy działanie:

```
[     0 ms] opublikowano zamówienie f4a6bbdff1fd499e9cedcaa585dba06e (ABC-1 x1)
[     4 ms] opublikowano zamówienie 3a4a077648ce47e39f4792338d21b9a0 (XYZ-9 x2)
[     7 ms] opublikowano zamówienie 755f309f45734afc8848c40f0be041b1 (ABC-1 x3)
[    12 ms] opublikowano zamówienie d7d37839e8ba416cb5335b608d43d0c9 (XYZ-9 x4)
[   171 ms] proces publikujący KOŃCZY SIĘ - żaden konsument w tym demie jeszcze nie działał
```

Proces A kończy się (`return`, proces znika z listy procesów systemu). **REST API zaraz potem**:

```
kolejka 'Order'  durable=True  messages_ready=4  unacked=0  consumers=0
```

Cztery wiadomości leżą na brokerze. `consumers=0` - w tym momencie **żaden proces na całej maszynie
nie ma otwartego połączenia z tą kolejką**. To nie "consumer offline, spróbuje ponownie" jak przy
in-memory outboksie (wydanie #2) - to po prostu stan trwały na dysku/w RAM-ie brokera, całkowicie
odłączony od cyklu życia jakiejkolwiek aplikacji.

**Proces B (`consume 3`)** - świeży proces, wystartowany długo po tym jak proces A już nie istniał:

```
[     0 ms] bus wystartował - zaraz zacznie odbierać to, co leżało w kolejce
[   590 ms] OrderConsumer: zamówienie 3a4a077648ce47e39f4792338d21b9a0 (XYZ-9 x2), kolejka = /Order
[   591 ms] OrderConsumer: zamówienie f4a6bbdff1fd499e9cedcaa585dba06e (ABC-1 x1), kolejka = /Order
[   626 ms] OrderConsumer: zamówienie 755f309f45734afc8848c40f0be041b1 (ABC-1 x3), kolejka = /Order
[   626 ms] OrderConsumer: zamówienie d7d37839e8ba416cb5335b608d43d0c9 (XYZ-9 x4), kolejka = /Order
[  3112 ms] koniec okna odbioru - ten proces odebrał łącznie 4 wiadomości
```

Te same cztery GUID-y co u procesu A. Proces B nie ma z procesem A **nic wspólnego** poza tym, że
oba łączyły się do tego samego brokera - żadnej współdzielonej pamięci, żadnego IPC. To jest
konkretna różnica względem in-memory: tam kolejka to pole w obiekcie w RAM-ie hosta, więc gdyby
proces A się skończył przed konsumpcją, wiadomości **przepadłyby bezpowrotnie** (nie ma ich do czego
"dołożyć" po restarcie, bo nowy proces to nowa, pusta kolejka in-memory).

## ⏱️ 4. Pułapka: REST API managementu kłamie przez kilka sekund

Odpalenie `inspect` **od razu** po `consume` pokazało wciąż `messages_ready=4`, mimo że w logu
konsumenta widać wyraźnie 4 odebrane wiadomości. Dopiero `inspect` po ok. 5-6 sekundach pokazał
`messages_ready=0`. RabbitMQ nie liczy statystyk UI/REST na żywo - odświeża je periodycznie. Wniosek
praktyczny: jeśli pijesz z REST API do automatycznych testów/alertów "czy kolejka jest pusta", nie
odpytuj natychmiast po operacji - dostaniesz nieaktualny wynik, nie błąd.

## 🔐 5. Dlaczego nie `guest`/`guest`

RabbitMQ domyślnie ogranicza użytkownika `guest` do połączeń z prawdziwego `127.0.0.1`
(`loopback_users`). W tym demie faktycznie **przetestowałem** `guest`/`guest` przez port
przekierowany przez Docker i - wbrew oczekiwaniom - zadziałało (patrz sekcja "czego nie
zweryfikowałem" - to zależy od konfiguracji sieci Dockera na danej maszynie, więc nie jest to
pewnik). Mimo to demo używa osobnego, jednorazowego loginu deweloperskiego
(`newsletter_dev`/`newsletter_dev_local_only`, tworzonego przez `docker-compose.yml` na czas tej
sesji) - bo to repo jest publiczne, a zostawianie działających poświadczeń `guest/guest` w gotowym
do skopiowania `docker-compose.yml` to zła praktyka niezależnie od tego, czy akurat by zadziałały.

## 🧪 Pełny zweryfikowany output

```
$ dotnet run --no-build -- topology
=== TOPOLOGY: startuję konsumenta, MassTransit deklaruje exchange/kolejkę/binding na RabbitMQ ===
[     0 ms] bus wystartował, topologia zadeklarowana na brokerze
[   682 ms] host zatrzymany (proces zaraz się kończy) - kolejka na brokerze ZOSTAJE, bo jest trwała

$ dotnet run --no-build -- inspect
=== INSPECT: co MassTransit naprawdę utworzył na brokerze (REST API management plugin) ===
--- exchange'y (bez wbudowanych amq.*) ---
  exchange 'MassTransitRabbitMqDemo:OrderSubmitted'  typ=fanout  durable=True
  exchange 'Order'  typ=fanout  durable=True
--- kolejki ---
  kolejka 'Order'  durable=True  messages_ready=0  unacked=0  consumers=0
--- bindingi (exchange -> kolejka), bez amq.* ---
  'MassTransitRabbitMqDemo:OrderSubmitted' --[routing_key='']--> exchange 'Order'
  'Order' --[routing_key='']--> queue 'Order'

$ dotnet run --no-build -- publish 4
=== PUBLISH: proces bez konsumenta publikuje 4 wiadomości i kończy się ===
[     0 ms] opublikowano zamówienie f4a6bbdff1fd499e9cedcaa585dba06e (ABC-1 x1)
[     4 ms] opublikowano zamówienie 3a4a077648ce47e39f4792338d21b9a0 (XYZ-9 x2)
[     7 ms] opublikowano zamówienie 755f309f45734afc8848c40f0be041b1 (ABC-1 x3)
[    12 ms] opublikowano zamówienie d7d37839e8ba416cb5335b608d43d0c9 (XYZ-9 x4)
[   171 ms] proces publikujący KOŃCZY SIĘ (Environment.Exit) - żaden konsument w tym demie jeszcze nie działał

$ dotnet run --no-build -- inspect
--- kolejki ---
  kolejka 'Order'  durable=True  messages_ready=4  unacked=0  consumers=0

$ dotnet run --no-build -- consume 3
=== CONSUME: nowy proces startuje konsumenta i przez 3s odbiera zaległe wiadomości ===
[     0 ms] bus wystartował - zaraz zacznie odbierać to, co leżało w kolejce, zanim ten proces w ogóle istniał
[   590 ms] OrderConsumer: zamówienie 3a4a077648ce47e39f4792338d21b9a0 (XYZ-9 x2), kolejka wejściowa = /Order
[   591 ms] OrderConsumer: zamówienie f4a6bbdff1fd499e9cedcaa585dba06e (ABC-1 x1), kolejka wejściowa = /Order
[   626 ms] OrderConsumer: zamówienie 755f309f45734afc8848c40f0be041b1 (ABC-1 x3), kolejka wejściowa = /Order
[   626 ms] OrderConsumer: zamówienie d7d37839e8ba416cb5335b608d43d0c9 (XYZ-9 x4), kolejka wejściowa = /Order
[  3112 ms] koniec okna odbioru - ten proces odebrał łącznie 4 wiadomości

$ dotnet run --no-build -- inspect        # natychmiast po consume - PUŁAPKA
--- kolejki ---
  kolejka 'Order'  durable=True  messages_ready=4  unacked=0  consumers=0    # nieaktualne!

$ sleep 6 && dotnet run --no-build -- inspect   # po odczekaniu - dopiero teraz widać prawdę
--- kolejki ---
  kolejka 'Order'  durable=True  messages_ready=0  unacked=0  consumers=0
```

## 🗺️ Ściąga

| Chcę... | Użyj |
|---|---|
| przełączyć transport na RabbitMQ | `x.UsingRabbitMq((ctx, cfg) => { cfg.Host(...); cfg.ConfigureEndpoints(ctx); })` |
| zobaczyć realną topologię | REST API `http://<host>:15672/api/{exchanges,queues,bindings}/%2f` albo `rabbitmqctl list_exchanges`/`list_bindings` |
| sprawdzić, ile wiadomości czeka | `GET /api/queues/%2f` → `messages_ready` (pamiętaj o opóźnieniu statystyk, sekcja 4) |
| uniknąć ograniczenia `guest` | osobny użytkownik przez `RABBITMQ_DEFAULT_USER`/`_PASS`, nie `guest` |
| zachować kebab-case nazw kolejek na RabbitMQ | `SetEndpointNameFormatter` tak samo jak na in-memory (wydanie #4) - domyślnie dostaniesz PascalCase |

---

## 🚧 Czego dziś NIE zweryfikowałem

- Czy `guest`/`guest` faktycznie zawsze zawodzi przez Docker (`loopback_users`) - w tej sesji
  zadziałał, więc nie mogę potwierdzić powszechnie cytowanego ograniczenia jako pewnika; zależy
  najpewniej od konfiguracji sieci Dockera (userland-proxy vs iptables NAT) na danej maszynie.
- Retry/`_error`/`_skipped` (wydanie #2) na prawdziwym RabbitMQ - działanie sprawdzone tylko na
  in-memory.
- `RoutingSlip`/Courier, trwałe repozytoria sag (EF/Mongo/Redis na RabbitMQ) - zostają na kolejne
  wydania.
- Topologia dla `topic`/`direct` exchange (używaliśmy tylko domyślnego `fanout`), routing key inny
  niż pusty, klaster RabbitMQ, TLS/AMQPS, `mandatory`/dead-lettering na poziomie brokera.
- Zachowanie `ConsumerDefinition`/`ConcurrentMessageLimit` z wydania #4 na prawdziwym brokerze
  (limit współbieżności był mierzony tylko na in-memory).
- Dokładny mechanizm/interwał odświeżania statystyk RabbitMQ (zaobserwowano opóźnienie ok. 5-6 s,
  nie sprawdzałem dokumentacji ani czy jest konfigurowalny).
- `docker-compose.yml` dołączony do `code/` - w środowisku, w którym budowałem to demo, nie było
  dostępne ani `docker compose`, ani `docker-compose`, więc realnie zweryfikowałem tylko równoważny
  `docker run` (te same parametry). Sam plik compose nie był uruchomiony.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) - włącznie z tym, jak postawić RabbitMQ przez
`docker-compose` i jak posprzątać po sobie (`docker compose down -v`).

---

<div align="center">

[← wróć do wydania #5 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
