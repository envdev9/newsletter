<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #7 — 30 września 2026

![MassTransit](https://img.shields.io/badge/MassTransit-FF6600?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Wzorzec](https://img.shields.io/badge/wzorzec-RoutingSlip%2FCourier-blueviolet?style=for-the-badge)

## 📨 RoutingSlip/Courier: rozproszona transakcja, która sama się cofa, gdy coś pójdzie nie tak

</div>

---

> _"Nie musisz pisać kodu kompensacji "na wszelki wypadek" w każdym kroku. Wystarczy powiedzieć
> frameworkowi, JAK cofnąć krok - resztą zajmie się sam, w odwrotnej kolejności."_

W poprzednim wydaniu przenieśliśmy się z in-memory na prawdziwy RabbitMQ i pokazaliśmy topologię
oraz trwałość. Dziś budujemy na tym fundamencie coś, czego ani `Publish`/`Send` (#1), ani sama saga
(#3) nie dają za darmo: **transakcję rozłożoną na kilka niezależnych kroków (aktywności), z których
każdy leci przez osobną kolejkę na RabbitMQ, a jeśli którykolwiek zawiedzie - MassTransit sam
COFA wszystkie wcześniejsze kroki, w odwrotnej kolejności, bez ani jednej linijki kodu "if fail then
rollback" napisanej przez nas ręcznie**. To wzorzec **RoutingSlip** (implementowany w MassTransit
jako **Courier**). Kod: [`code/`](code/), MassTransit **8.5.10** + `MassTransit.RabbitMQ` **8.5.10**,
RabbitMQ `4.3-management` w Dockerze, .NET 10, output prawdziwy - łącznie ze ścieżką błędu i
kompensacji.

## 🎯 Dlaczego to ważne

Wyobraź sobie proces zamówienia: **zarezerwuj towar → obciąż kartę**. To dwa niezależne kroki, mogą
nawet siedzieć w dwóch różnych mikroserwisach, każdy ze swoją kolejką. Jeśli krok 2 (płatność)
zawiedzie, krok 1 (rezerwacja) musi zostać **cofnięty** - inaczej towar zostaje zablokowany na
zawsze dla zamówienia, które nigdy nie zostało opłacone. Ręczne pisanie tego ("spróbuj, jak się nie
uda, wywołaj kompensację poprzedniego kroku, a jak i to się nie uda...") szybko robi się nieczytelne,
zwłaszcza gdy kroków jest więcej niż dwa. RoutingSlip odwraca ten problem: **budujesz plan podróży
(itinerary)** - listę aktywności do wykonania po kolei - i wysyłasz go w świat. Framework sam pilnuje
kolejności, sam wykonuje kompensację wstecz przy błędzie i sam publikuje jedno z dwóch zdarzeń na
koniec: `RoutingSlipCompleted` albo `RoutingSlipFaulted`.

| Pojęcie | Co robi | W naszym demie |
|---|---|---|
| 🧭 **`RoutingSlipBuilder`** | buduje plan (itinerary) - listę aktywności do wykonania | `AddActivity("ReserveInventory", ...)`, `AddActivity("ChargePayment", ...)` |
| ⚙️ **`IExecuteActivity<TArgs>`** | krok "do przodu" - robi jedną rzecz, w swojej własnej kolejce | `ReserveInventoryActivity`, `ChargePaymentActivity` |
| ↩️ **`ICompensateActivity<TLog>`** | krok "cofnij" - wywoływany TYLKO gdy późniejszy krok zawiódł | `ReserveInventoryActivity` (ma), `ChargePaymentActivity` (nie ma - execute-only) |
| 🧩 **`IActivity<TArgs, TLog>`** | wygodny interfejs łączący execute+compensate w jednej klasie | implementowany przez `ReserveInventoryActivity` |
| 🏁 **`RoutingSlipCompleted`/`Faulted`** | zdarzenie końcowe całej transakcji | konsument `RoutingSlipEventsConsumer` |
| 📬 **`bus.Execute(routingSlip)`** | wysyła plan do pierwszej aktywności i uruchamia całość | `await bus.Execute(routingSlip)` |

---

## 🧭 1. Dwie aktywności, jedna z kompensacją, druga bez

Kontrakty argumentów/logów to zwykłe recordy - dokładnie jak wiadomości `Publish`/`Send` we
wcześniejszych wydaniach:

```csharp
public record ReserveInventoryArguments(string OrderId, string Sku, int Qty);
public record ReserveInventoryLog(string OrderId, string Sku, int Qty);

public record ChargePaymentArguments(string OrderId, decimal Amount);
```

Aktywność **z kompensacją** implementuje `IActivity<TArguments, TLog>` (połączenie
`IExecuteActivity<TArguments>` i `ICompensateActivity<TLog>` - MassTransit wymaga tego jednego,
połączonego interfejsu, samo zaimplementowanie obu osobno nie wystarczy do rejestracji przez
`AddActivity<T, TArgs, TLog>`):

```csharp
public class ReserveInventoryActivity : IActivity<ReserveInventoryArguments, ReserveInventoryLog>
{
    public Task<ExecutionResult> Execute(ExecuteContext<ReserveInventoryArguments> context)
    {
        var a = context.Arguments;
        // "rezerwacja" - w realnym świecie zapis do magazynu.
        var log = new ReserveInventoryLog(a.OrderId, a.Sku, a.Qty);
        return Task.FromResult(context.Completed(log));   // log trafia do RoutingSlip.CompensateLogs
    }

    public Task<CompensationResult> Compensate(CompensateContext<ReserveInventoryLog> context)
    {
        var l = context.Log;   // dokładnie to, co przekazaliśmy do Completed(log) wyżej
        // zwolnienie rezerwacji - wywoływane TYLKO jeśli kolejny krok zawiedzie
        return Task.FromResult(context.Compensated());
    }
}
```

Aktywność **bez kompensacji** implementuje tylko `IExecuteActivity<TArguments>` i rejestruje się
inną metodą (`AddExecuteActivity`, nie `AddActivity`) - nie ma czego cofać po jej własnej stronie:

```csharp
public class ChargePaymentActivity : IExecuteActivity<ChargePaymentArguments>
{
    public Task<ExecutionResult> Execute(ExecuteContext<ChargePaymentArguments> context)
    {
        var a = context.Arguments;
        if (a.Amount > 1000m)
            throw new InvalidOperationException($"Karta odrzucona dla kwoty {a.Amount:0.00} zł");

        return Task.FromResult(context.Completed());
    }
}
```

Rejestracja w DI - dwie różne metody dla dwóch różnych "kształtów" aktywności:

```csharp
x.SetEndpointNameFormatter(KebabCaseEndpointNameFormatter.Instance);
x.AddActivity<ReserveInventoryActivity, ReserveInventoryArguments, ReserveInventoryLog>();
x.AddExecuteActivity<ChargePaymentActivity, ChargePaymentArguments>();

x.UsingRabbitMq((context, cfg) =>
{
    cfg.Host("localhost", "/", h => { h.Username(RabbitUser); h.Password(RabbitPass); });
    // Tworzy TERAZ nie tylko kolejkę zwykłego konsumenta, ale osobną kolejkę execute
    // (i compensate, jeśli aktywność ją ma) DLA KAŻDEJ zarejestrowanej aktywności.
    cfg.ConfigureEndpoints(context);
});
```

## 🧩 2. Budowa i wysyłka planu podróży (itinerary)

Adresów kolejek execute **nie zgadujemy** - pytamy o nie ten sam `IEndpointNameFormatter`, którego
użyje `ConfigureEndpoints`. To świadome unikanie pułapki z wydania #5 (domyślna nazwa kolejki bywa
inna, niż się wydaje):

```csharp
var formatter = host.Services.GetRequiredService<IEndpointNameFormatter>();
var reserveExecuteAddress = new Uri($"queue:{formatter.ExecuteActivity<ReserveInventoryActivity, ReserveInventoryArguments>()}");
var chargeExecuteAddress  = new Uri($"queue:{formatter.ExecuteActivity<ChargePaymentActivity, ChargePaymentArguments>()}");
var eventsConsumerAddress = new Uri($"queue:{formatter.Consumer<RoutingSlipEventsConsumer>()}");

var builder = new RoutingSlipBuilder(Guid.NewGuid());
builder.AddSubscription(eventsConsumerAddress, RoutingSlipEvents.Completed | RoutingSlipEvents.Faulted);
builder.AddActivity("ReserveInventory", reserveExecuteAddress, new { OrderId = orderId, Sku = "ABC-1", Qty = 2 });
builder.AddActivity("ChargePayment", chargeExecuteAddress, new { OrderId = orderId, Amount = amount });
var routingSlip = builder.Build();

await bus.Execute(routingSlip);
```

`AddSubscription` mówi frameworkowi: "gdy cała transakcja się skończy (sukcesem albo błędem), wyślij
zdarzenie **wprost** pod ten adres" - to zwykły punkt-punkt `Send` po adresie `queue:`, dokładnie jak
w wydaniu #4, nie fanout `Publish`.

## ✅ 3. Ścieżka sukcesu: `RoutingSlipCompleted`

Kwota w limicie (250 zł, limit karty to 1000 zł) - obie aktywności lecą po kolei, kompensacja nigdy
nie jest wywoływana:

```
=== RUN OK: routing slip zamówienia, kwota płatności = 250.00 zł (limit karty = 1000 zł) ===
[    73 ms] wysyłam routing slip 021452dc-5ee7-4495-b90a-38d13e36a384 dla zamówienia a4e247b4 (itinerary: ReserveInventory -> ChargePayment)
[   911 ms] [ReserveInventory]  EXECUTE   rezerwuję 2x ABC-1 dla zamówienia a4e247b4
[  1038 ms] [ChargePayment]     EXECUTE   próbuję obciążyć 250.00 zł za zamówienie a4e247b4
[  1038 ms] [ChargePayment]     EXECUTE   płatność zaakceptowana
[  1102 ms] [EVENTS] RoutingSlipCompleted 021452dc-5ee7-4495-b90a-38d13e36a384 po 1030 ms - WSZYSTKIE aktywności ukończone, nic nie kompensowano
```

## 💥 4. Ścieżka błędu: automatyczna kompensacja wstecz

Kwota nad limitem (1500 zł) - `ChargePayment` rzuca wyjątek. MassTransit **sam** wywołuje
`Compensate` na `ReserveInventoryActivity`, używając dokładnie tego logu, który zwróciliśmy z
`Execute` (`context.Completed(log)`), i dopiero potem publikuje `RoutingSlipFaulted`:

```
=== RUN FAIL: routing slip zamówienia, kwota płatności = 1500.00 zł (limit karty = 1000 zł) ===
[    67 ms] wysyłam routing slip 2e25737d-0b71-4a06-ab5d-de06e6f6e31f dla zamówienia bf8f6b90 (itinerary: ReserveInventory -> ChargePayment)
[   955 ms] [ReserveInventory]  EXECUTE   rezerwuję 2x ABC-1 dla zamówienia bf8f6b90
[  1071 ms] [ChargePayment]     EXECUTE   próbuję obciążyć 1500.00 zł za zamówienie bf8f6b90
[  1071 ms] [ChargePayment]     EXECUTE   karta ODRZUCONA (kwota 1500.00 zł > limit 1000 zł)
[  1304 ms] [ReserveInventory]  COMPENSATE  zwalniam rezerwację 2x ABC-1 dla zamówienia bf8f6b90 - dalszy krok routing slipa zawiódł
[  1357 ms] [EVENTS] RoutingSlipFaulted 2e25737d-0b71-4a06-ab5d-de06e6f6e31f po 1299 ms - transakcja NIE powiodła się, kompensacja poprzednich aktywności już wykonana
[  1358 ms] [EVENTS]   aktywność 'ChargePayment' rzuciła: System.InvalidOperationException: Karta odrzucona dla kwoty 1500.00 zł
```

Zwróć uwagę na kolejność: **COMPENSATE (1304 ms) leci PRZED RoutingSlipFaulted (1357 ms)**. To nie
przypadek - MassTransit gwarantuje, że wszystkie kompensacje wcześniejszych kroków dokończą się,
zanim ktokolwiek na zewnątrz zobaczy `RoutingSlipFaulted`. Konsument zdarzeń dostaje informację o
błędzie dopiero, gdy system jest już w spójnym stanie (rezerwacja zwolniona).

## 🏛️ 5. Topologia: każda aktywność to osobna kolejka, a `RoutingSlip` NIE idzie przez fanout

REST API managementu po uruchomieniu `topology` + obu scenariuszy:

```
--- kolejki ---
  kolejka 'charge-payment_execute'          durable=True  messages_ready=0  unacked=0  consumers=0
  kolejka 'reserve-inventory_compensate'    durable=True  messages_ready=0  unacked=0  consumers=0
  kolejka 'reserve-inventory_execute'       durable=True  messages_ready=0  unacked=0  consumers=0
  kolejka 'routing-slip-events'             durable=True  messages_ready=0  unacked=0  consumers=0
--- bindingi ---
  'MassTransit.Courier.Contracts:RoutingSlipCompleted' --[routing_key='']--> exchange 'routing-slip-events'
  'MassTransit.Courier.Contracts:RoutingSlipFaulted'   --[routing_key='']--> exchange 'routing-slip-events'
  'MassTransit:Fault--MassTransit.Courier.Contracts:RoutingSlip--' --[routing_key='']--> exchange 'MassTransit:Fault'
  'charge-payment_execute'       --[routing_key='']--> queue 'charge-payment_execute'
  'reserve-inventory_compensate' --[routing_key='']--> queue 'reserve-inventory_compensate'
  'reserve-inventory_execute'    --[routing_key='']--> queue 'reserve-inventory_execute'
  'routing-slip-events'          --[routing_key='']--> queue 'routing-slip-events'
```

Ciekawa asymetria, potwierdzona realnym outputem (i skrzyżowana z `rabbitmqctl list_exchanges` -
te same nazwy): **`reserve-inventory_execute` i `charge-payment_execute` NIE mają osobnego
"exchange'a wiadomości"** takiego jak `OrderSubmitted` w wydaniu #5 (`MassTransitRabbitMqDemo:...`)
- mają tylko swój własny exchange kolejki. To dlatego, że `RoutingSlip` trafia tam wyłącznie przez
**adresowany `Send`** (`queue:reserve-inventory_execute`), nigdy przez `Publish`. Natomiast
`RoutingSlipCompleted`/`RoutingSlipFaulted` **mają** pełny łańcuch exchange wiadomości → exchange
kolejki → kolejka (`MassTransit.Courier.Contracts:RoutingSlipCompleted` → `routing-slip-events` →
`routing-slip-events`) - bo `RoutingSlipEventsConsumer` jest zarejestrowany jako zwykły
`IConsumer<T>`, a `ConfigureEndpoints` zawsze tworzy pełną topologię pod konsumowane typy wiadomości,
niezależnie od tego, czy w praktyce dotrą tam przez `Send` czy `Publish`.

> ⚠️ **Bonus, niezapowiedziany:** w topologii pojawia się też `MassTransit:Fault` i
> `MassTransit:Fault--MassTransit.Courier.Contracts:RoutingSlip--` - to ten sam mechanizm
> `Fault<T>` z wydania #2, zadeklarowany automatycznie dla `RoutingSlip` jako konsumowanego typu na
> kolejce `charge-payment_execute`. Nic tam nie trafiło (żadna kolejka nie jest do niego
> zbindowana) - transport-owy `Fault<RoutingSlip>` i **kurierowy** `RoutingSlipFaulted` to dwa
> osobne mechanizmy, które akurat współistnieją na tej samej kolejce.

## ⏱️ 6. Pułapka (kontynuacja z #5): opóźnienie REST API dotyczy też `consumers`, nie tylko `messages_ready`

W wydaniu #5 ustaliliśmy, że `messages_ready` w REST API bywa nieaktualne przez kilka sekund po
operacji. Dziś to samo zaobserwowaliśmy dla licznika `consumers`: `inspect` odpalony **od razu** po
zakończeniu procesu `run fail` pokazał `consumers=1` na `reserve-inventory_execute`, mimo że proces,
który się z tą kolejką łączył, już nie istniał (host był zatrzymany przed zakończeniem `Main`).
Dopiero `inspect` po ok. 6 sekundach pokazał `consumers=0`. Wniosek ten sam co poprzednio: nie ufaj
REST API managementu "na gorąco" tuż po operacji.

---

## 🗺️ Ściąga

| Chcę... | Użyj |
|---|---|
| zdefiniować krok z możliwością cofnięcia | `class X : IActivity<TArgs, TLog>` + `x.AddActivity<X, TArgs, TLog>()` |
| zdefiniować krok bez kompensacji | `class X : IExecuteActivity<TArgs>` + `x.AddExecuteActivity<X, TArgs>()` |
| zwrócić log kompensacji z `Execute` | `return context.Completed(log);` (zamiast `context.Completed()`) |
| cofnąć krok w `Compensate` | `return context.Compensated();` (albo `context.Failed(ex)`, jeśli SAMA kompensacja się nie uda) |
| poznać adres kolejki execute/compensate | `formatter.ExecuteActivity<TActivity, TArgs>()` / `formatter.CompensateActivity<TActivity, TLog>()` |
| wysłać plan i uruchomić transakcję | `await bus.Execute(routingSlip);` |
| dostać zdarzenie końcowe (sukces/błąd) | `builder.AddSubscription(adres, RoutingSlipEvents.Completed \| RoutingSlipEvents.Faulted)` + `IConsumer<RoutingSlipCompleted>`, `IConsumer<RoutingSlipFaulted>` |

---

## 🚧 Czego dziś NIE zweryfikowałem

- Kompensację, która SAMA zawodzi (`context.Failed(ex)` w `Compensate`) - w demie kompensacja zawsze
  się udaje.
- Itinerary z 3+ aktywnościami i częściową kompensacją (np. druga z trzech aktywności ma log, trzecia
  nie) - demo ma dokładnie 2 aktywności.
- `ReviseItinerary` (dynamiczne dopisywanie kolejnych aktywności w trakcie wykonania planu).
- Trwałe repozytorium sag (EF/Mongo/Redis) - RoutingSlip/Courier jest z natury bezstanowy (plan
  podróży leci w samej wiadomości), więc to osobny temat, nadal nie tknięty.
- Interakcję Couriera z `UseMessageRetry` z wydania #2 - czy retry na kolejce `_execute` próbuje
  ponownie CAŁĄ aktywność, zanim framework w ogóle uzna ją za faulted i zacznie kompensować.
- Topic/direct exchange (nadal tylko domyślny `fanout`), klaster RabbitMQ, TLS/AMQPS.
- `ConcurrentMessageLimit` (wydanie #4) zastosowany do aktywności Couriera.
- Realne opóźnienie odświeżania licznika `consumers` w REST API (zaobserwowane ok. 6 s w tej sesji,
  tak jak dla `messages_ready` w #5 - nie sprawdzałem, czy to ten sam interwał).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) - pełna instrukcja od zera, włącznie ze sprzątaniem
kontenera Dockera po sobie.

---

<div align="center">

[← wróć do wydania #7 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
