<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #12 — 5 października 2026

![MassTransit](https://img.shields.io/badge/MassTransit-FF6600?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Wzorzec](https://img.shields.io/badge/wzorzec-retry%2F_error%2F_skipped%20na%20RabbitMQ-blueviolet?style=for-the-badge)

## 📨 `_error` i `_skipped` na PRAWDZIWYM RabbitMQ: broker pamięta, proces nie musi

</div>

---

> _"Retry mówi: spróbuj jeszcze raz, zanim się poddasz. `_error` mówi: poddałeś się - ale
> ktoś/coś musi o tym wiedzieć, nawet jeśli Ty już nie żyjesz."_

W wydaniu #2 (in-memory) ustaliliśmy teorię: `UseMessageRetry` próbuje ponownie w tym samym
procesie, a gdy to nie pomoże, wiadomość trafia do `Fault<T>` i kolejki `<endpoint>_error`;
`_skipped` to zupełnie inny przypadek - wiadomość, której **nikt na endpointcie nie umie
skonsumować**. Transport in-memory nie ma jednak trwałości - te kolejki znikały wraz z procesem.
Dziś, po czterech wydaniach na prawdziwym RabbitMQ (#5, #7 i okolice), domykamy tę teorię
**dowodem**: stawiamy broker, odpalamy proces, który świadomie pada z błędem, **zabijamy go**, i w
**zupełnie nowym, niezależnym procesie** sprawdzamy, co broker naprawdę zapamiętał - łącznie z
treścią wiadomości i nagłówkami `MT-*`. Po drodze obalamy jedno błędne przypuszczenie, które
zrobiliśmy przy pisaniu tego kodu (zobacz punkt 4). Kod: [`code/`](code/), MassTransit **8.5.10** +
`MassTransit.RabbitMQ` **8.5.10**, RabbitMQ `4.3-management` w Dockerze, .NET 10, output prawdziwy -
łącznie z crosscheckiem przez `rabbitmqctl` i `GET`/`get` na REST API managementu.

## 🎯 Dlaczego to ważne

W in-memory demo z #2 `_error`/`_skipped` były ciekawostką widoczną tylko "pod mikroskopem" tego
samego procesu. W produkcji konsument pada, deploy się restartuje, proces znika - a wiadomość,
która nie przeszła, **musi** przeżyć to wszystko, inaczej cały sens error queue (ktoś z zespołu
operacyjnego kiedyś to przerobi) pada razem z procesem. To jest **jedyny** powód, dla którego
w ogóle używa się brokera, a nie kolejki w pamięci - i dziś to sprawdzamy namacalnie, nie na
słowo.

| Pojęcie | Co robi | W naszym demie |
|---|---|---|
| 🔁 `UseMessageRetry(r => r.Interval(...))` | ponawia Consume W TYM SAMYM procesie, bez rundy przez broker | `FlakyConsumerDefinition` - 2 porażki, 3. próba OK |
| ☠️ `<endpoint>_error` | tu ląduje wiadomość po wyczerpaniu retry (albo po `Ignore<T>`) | `always-failing_error`, `skippable_error` |
| 🗑️ `<endpoint>_skipped` | tu ląduje wiadomość, dla której NIKT na endpointcie nie ma `IConsumer<T>` | `flaky_skipped` (wysłane `NobodyConsumesThis` wprost na kolejkę `flaky`) |
| 🧯 `r.Ignore<TException>()` | wyłącza retry dla danego wyjątku - **od razu** `_error`, NIE `_skipped` (sprostowanie, patrz pkt. 4) | `SkippableConsumerDefinition` |
| 🏷️ `MT-Reason` | nagłówek na wiadomości w kolejce błędów - `fault` vs `dead-letter` | widoczny przez `peek` |
| 🔍 `POST /api/queues/.../get` (ackmode=`ack_requeue_true`) | podgląd treści wiadomości w kolejce BEZ jej usunięcia | tryb `peek` |

---

## 🔁 1. Trzy konsumenty, trzy polityki `UseMessageRetry` per-endpoint

Retry konfigurujemy w `ConsumerDefinition<T>` (ten sam mechanizm z `EndpointName`/
`ConcurrentMessageLimit` z wydania #4) - **per endpoint**, nie globalnie:

```csharp
public class FlakyConsumerDefinition : ConsumerDefinition<FlakyConsumer>
{
    protected override void ConfigureConsumer(
        IReceiveEndpointConfigurator endpointConfigurator,
        IConsumerConfigurator<FlakyConsumer> consumerConfigurator,
        IRegistrationContext context)
    {
        // 3 próby, odstęp 300 ms - wystarczy, żeby "2 porażki + sukces" się udało.
        endpointConfigurator.UseMessageRetry(r => r.Interval(3, TimeSpan.FromMilliseconds(300)));
    }
}
```

> ⚠️ Sygnatura `ConfigureConsumer` z **dwoma** parametrami (bez `IRegistrationContext`) **kompiluje
> się, ale rzuca warningiem CS0672** - jest `[Obsolete]` w MassTransit 8.5.10. Zweryfikowane
> realnie (`dotnet build`): dodanie trzeciego parametru `IRegistrationContext context` usuwa
> warning do zera. Drobiazg, ale dokładnie taki, który "działa, ale naprawdę nie powinien" -
> pominięcie go w kodzie z internetu to częsty sposób na ukryty warning w CI.

Drugi konsument ma błąd **trwały** (2 ponowienia, odstęp 200 ms - 3 próby łącznie, zawsze
porażka), trzeci ma wyjątek oznaczony jako niewarty ponawiania:

```csharp
endpointConfigurator.UseMessageRetry(r => r.Interval(2, TimeSpan.FromMilliseconds(200)));         // AlwaysFailing
endpointConfigurator.UseMessageRetry(r =>
{
    r.Interval(2, TimeSpan.FromMilliseconds(200));   // ten limit NIE zadziała dla tego wyjątku...
    r.Ignore<KnownBadDataException>();               // ...bo Ignore<T> pomija retry CAŁKOWICIE
});                                                                                                  // Skippable
```

## ✅ 2. Ścieżka sukcesu: retry w tym samym procesie, broker nawet nie wie, że coś szwankowało

```
=== RUN FLAKY: 48815418 zawiedzie 2 razy, uda się przy 3. próbie (UseMessageRetry.Interval) ===
[     0 ms] [Flaky]          próba 1/3 dla 48815418 - wyjątek PRZEJŚCIOWY, retry za chwilę
[   324 ms] [Flaky]          próba 2/3 dla 48815418 - wyjątek PRZEJŚCIOWY, retry za chwilę
[   641 ms] [Flaky]          próba 3/3 dla 48815418 - SUKCES, retry nie jest już potrzebny
```

Odstępy **324 ms** i **317 ms** między próbami - bardzo blisko skonfigurowanego `300 ms`. To
potwierdza to, co było tylko teorią w #2: `UseMessageRetry` to filtr w pipeline odbioru, NIE
round-trip przez broker - wiadomość ani raz nie wraca na RabbitMQ, dlatego zachowanie samego retry
jest **identyczne** na in-memory i na prawdziwym brokerze. Różnica, którą dziś sprawdzamy, jest
wyłącznie po stronie tego, co się dzieje, gdy retry **nie pomoże**.

## ☠️ 3. Ścieżka trwałej porażki: `_error` przeżywa zamknięcie procesu

```
=== RUN FAIL: 1fd64b81 zawiedzie TRWALE - po 2 retry MassTransit przenosi wiadomość do kolejki _error ===
[     0 ms] [AlwaysFailing]  próba 1 dla 1fd64b81 - błąd TRWAŁY, nigdy się nie uda
[   226 ms] [AlwaysFailing]  próba 2 dla 1fd64b81 - błąd TRWAŁY, nigdy się nie uda
[   434 ms] [AlwaysFailing]  próba 3 dla 1fd64b81 - błąd TRWAŁY, nigdy się nie uda
[  2063 ms] host ZATRZYMANY (proces się kończy) - żaden konsument już nie jest podłączony do brokera
```

Proces **kończy się** (`host.StopAsync()`, cały `dotnet run` schodzi). Teraz odpalamy **nowy,
całkowicie niezależny proces** (`dotnet run -- inspect`), który nigdy nie widział poprzedniego:

```
=== INSPECT: co broker naprawdę ma w kolejkach _error/_skipped - BEZ ŻADNEGO podłączonego konsumenta ===
--- kolejki (główne + _error/_skipped) ---
  kolejka 'always-failing'  durable=True  messages_ready=0  unacked=0  consumers=0
  kolejka 'always-failing_error'  durable=True  messages_ready=1  unacked=0  consumers=0
```

**`messages_ready=1`, `consumers=0`** - wiadomość siedzi na brokerze, mimo że proces, który ją
"zepsuł", już nie istnieje. Potwierdzone niezależnie przez `rabbitmqctl list_queues` (te same
liczby - `always-failing_error  true  1  0`). To jest cała różnica względem #2: tam `_error`
umierał z procesem, bo in-memory transport **jest** tym procesem. Tu `_error` to osobna, trwała
encja na RabbitMQ.

## 🧯 4. Sprostowanie: `Ignore<T>` NIE idzie do `_skipped` - idzie PROSTO do `_error`

Pisząc ten kod, założyłem (błędnie), że `r.Ignore<KnownBadDataException>()` wysyła wiadomość do
`_skipped`, tak jak pisałem w skrócie w #2 ("błąd walidacji/danych → `Ignore<T>` **i od razu
`Fault`**" - to zdanie było poprawne, moje pierwsze przypuszczenie przy kodzeniu było z nim
niezgodne). Realny output z `inspect` to sprostowało natychmiast:

```
kolejka 'skippable_error'  durable=True  messages_ready=1  unacked=0  consumers=0
```

Nie `skippable_skipped` - **`skippable_error`**. `peek` na nagłówki potwierdza mechanizm: dla
`AlwaysFailingConsumer` (3 próby retry) nagłówek `MT-Fault-RetryCount = 2` jest obecny, dla
`SkippableConsumer` (Ignore) **nagłówek `MT-Fault-RetryCount` nie istnieje wcale** - bo retry nigdy
nie wystartował, nie dlatego, że go "wyczerpano":

```
--- always-failing_error ---
  header MT-Fault-ExceptionType = MassTransitRetryErrorDemo.OrderRejectedException
  header MT-Fault-RetryCount = 2
  header MT-Reason = fault

--- skippable_error ---
  header MT-Fault-ExceptionType = MassTransitRetryErrorDemo.KnownBadDataException
  header MT-Reason = fault                      <- brak MT-Fault-RetryCount w ogóle
```

`Ignore<T>` = "nie trać czasu na ponawianie TEGO wyjątku, od razu uznaj za faulted" - to skraca
czas do `_error` (1 próba zamiast 3), ale **kolejka docelowa jest ta sama co dla wyczerpanego
retry**. `_skipped` to mechanizm z zupełnie innej przyczyny - zobacz punkt 5.

## 🗑️ 5. Prawdziwy `_skipped` na RabbitMQ: wiadomość, której NIKT nie umie przeczytać

Żeby wywołać `_skipped` naprawdę, trzeba zrobić to, co opisało #2: wysłać typ, dla którego na
endpointcie nie ma `IConsumer<T>`. Tu: `NobodyConsumesThis` wysłane **wprost** (adresowany `Send`,
jak w #4) na kolejkę `flaky`, która konsumuje tylko `FlakyOperation`:

```csharp
var flakyQueue = await bus.GetSendEndpoint(new Uri("queue:flaky"));
await flakyQueue.Send(new NobodyConsumesThis(id));
```

```
kolejka 'flaky_skipped'  durable=True  messages_ready=1  unacked=0  consumers=0
```

Nagłówki na tej wiadomości **nie mają ani jednego `MT-Fault-*`** - bo żaden wyjątek nigdy nie
wystąpił (nie ma czego "zawinić"):

```
--- flaky_skipped ---
  header MT-Reason = dead-letter
```

Dokładnie to samo rozpoznanie co w #2 (`MT-Reason = dead-letter`, nie "skipped"), tylko dziś
potwierdzone na **trwałej, prawdziwej** kolejce RabbitMQ, nie na in-memory endpointcie, który
zniknąłby wraz z procesem.

## 🔍 6. Nowa technika: zajrzyj do wiadomości bez jej konsumowania

W #5/#7 sprawdzaliśmy tylko **liczniki** (`messages_ready`, `consumers`) przez REST API. Dziś
idziemy o krok dalej - management plugin ma endpoint `POST /api/queues/%2f/<kolejka>/get`, który
**zdejmuje** wiadomość z kolejki, ale z `ackmode=ack_requeue_true` odkłada ją z powrotem:

```csharp
var body = JsonSerializer.Serialize(new { count = 5, ackmode = "ack_requeue_true", encoding = "auto" });
var response = await http.PostAsync($"/api/queues/%2f/{queueName}/get",
    new StringContent(body, Encoding.UTF8, "application/json"));
```

Zweryfikowane: `inspect` **przed** i **po** `peek` pokazuje identyczne `messages_ready=1` - żadna
wiadomość nie zginęła. To jest realny sposób na podgląd "co tam właściwie leży" w kolejce błędów
bez pisania osobnego konsumenta i bez ryzyka przypadkowego zjedzenia wiadomości produkcyjnej.

## 🪤 7. Pułapka: topologia `_error`/`_skipped` jest LENIWA, nie deklarowana z góry

Przed pierwszym `run` (czyli po samym `topology`), `inspect` pokazuje **tylko 3 kolejki główne** -
`always-failing`, `flaky`, `skippable`. Żadnych `_error`/`_skipped`, żadnych exchange'ów `Fault`.
MassTransit tworzy te kolejki **dopiero w momencie, gdy faktycznie czegoś potrzebuje tam odłożyć**,
nie przy starcie hosta - inaczej niż kolejki execute/compensate z Couriera w #7, które powstawały
od razu dla KAŻDEJ zarejestrowanej aktywności. To ma sens operacyjny (nie zaśmiecasz brokera
dziesiątkami pustych `_error` dla endpointów, które nigdy nie zawiodły), ale jeśli monitorujesz
"czy `_error` istnieje" jako health-check zaraz po deployu - zobaczysz "nie istnieje" i to będzie
**prawidłowy** stan, nie błąd.

---

## 🗺️ Ściąga

| Chcę... | Użyj |
|---|---|
| ponowić w tym samym procesie, bez rundy przez broker | `endpointConfigurator.UseMessageRetry(r => r.Interval(n, odstęp))` w `ConsumerDefinition<T>.ConfigureConsumer` (3 parametry - `IRegistrationContext` na końcu, inaczej CS0672) |
| wyłączyć retry dla konkretnego wyjątku (od razu `_error`) | `r.Ignore<TException>()` - **NIE** trafia do `_skipped` |
| zobaczyć realną kolejkę błędów po wyczerpaniu retry | `<endpoint>_error`, nagłówek `MT-Reason=fault` + `MT-Fault-RetryCount` |
| zobaczyć realną kolejkę "nikt nie umie przeczytać" | wyślij typ bez konsumenta `Send`-em wprost na kolejkę; `<endpoint>_skipped`, `MT-Reason=dead-letter`, brak `MT-Fault-*` |
| podglądnąć treść wiadomości w kolejce bez jej usuwania | `POST /api/queues/%2f/<kolejka>/get` z `ackmode: "ack_requeue_true"` |
| sprawdzić, że `_error` przeżył zamknięcie procesu | zatrzymaj host, odpal NOWY proces z `inspect`/`peek` |

---

## 🚧 Czego dziś NIE zweryfikowałem

- `UseDelayedRedelivery` (opóźnione ponowienie przez scheduler) na prawdziwym RabbitMQ - wymaga
  dodatkowej infrastruktury (scheduler/plugin delayed-exchange), nie testowane w tym demie.
- Interakcję `Ignore<T>`/`UseMessageRetry` z `ConcurrentMessageLimit` (#4) albo z Courierem (#7).
- Trwałe repozytorium sag (EF/Mongo/Redis) - nadal osobny temat, nie tknięty.
- Topic/direct exchange (cały czas tylko domyślny `fanout`), klaster RabbitMQ, TLS/AMQPS.
- Dokładne ponowne zmierzenie opóźnienia licznika `consumers` w REST API (znane z #5/#7, ok. 6 s) -
  w tym wydaniu `consumers=0` było widoczne od razu przy każdym `inspect`, ale nie mierzyłem tego
  systematycznie na tym demie.
- Co się stanie, gdy `_error`/`_skipped` urośnie do tysięcy wiadomości (limity pamięci/dysku
  brokera) - demo ma dokładnie po 1 wiadomości w każdej kolejce błędów.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) - pełna instrukcja od zera, włącznie ze sprzątaniem
kontenera Dockera po sobie.

---

<div align="center">

[← wróć do wydania #12 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
