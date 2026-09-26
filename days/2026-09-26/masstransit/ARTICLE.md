<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #3 — 26 września 2026

![MassTransit](https://img.shields.io/badge/MassTransit-FF6600?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Transport](https://img.shields.io/badge/transport-in--memory-blue?style=for-the-badge)

## 📨 Saga: cykl życia zamówienia jako maszyna stanów - Initially, During, Finally, Schedule i composite event

</div>

---

> _"Retry ratuje pojedynczą wiadomość. Saga ratuje **proces**, który składa się z wielu wiadomości
> rozłożonych w czasie."_

Dwa poprzednie wydania dotyczyły jednej wiadomości i jednego consumera. Realny biznes to jednak
proces: zamówienie zostaje **złożone**, potem **opłacone**, potem **spakowane i wysłane** - a po
drodze klient może nie zapłacić, płatność może przyjść przed potwierdzeniem magazynu albo po nim,
a na końcu ktoś musi to wszystko dopilnować. Dziś stawiamy to na **sadze** (`MassTransitStateMachine`).
Cały kod jest w [`code/`](code/), działa na transporcie in-memory (bez RabbitMQ i Dockera), a każdy
output niżej pochodzi z prawdziwego uruchomienia (MassTransit **8.5.10**, .NET 10).

## 🎯 Dlaczego to ważne

Bez sagi ten proces rozłazi się na luźne consumery i pola `Status` w bazie, a reguły typu "co jeśli
przyjdzie płatność po anulowaniu?" lądują w rozsianych `if`-ach. Saga zbiera to w **jednym miejscu**:

| Pojęcie | Co robi | W naszym demie |
|---|---|---|
| 🧾 **Instancja sagi** (`SagaStateMachineInstance`) | jeden wiersz stanu na proces | `OrderState` - kwota, `CurrentState`, flagi composite |
| 🔗 **Korelacja** | który event należy do której instancji | `CorrelateById(m => m.Message.OrderId)` |
| 🚦 **`Initially`** | co robi event startujący sagę | `OrderSubmitted` tworzy instancję |
| ⏱️ **`During(stan, ...)`** | jakie eventy są legalne w danym stanie | np. `PaymentReceived` tylko w `Submitted` |
| 🧩 **Composite event** | "odpal, gdy zaszły OBA zdarzenia, w dowolnej kolejności" | płatność + rezerwacja stocku = `ReadyToShip` |
| ⏳ **`Schedule`** | timeout jako zaplanowana wiadomość | anulowanie po 1,5 s bez płatności |
| 🏁 **`Finally`** + `SetCompletedWhenFinalized` | sprzątanie i usunięcie instancji z repozytorium | po `Finalize()` |

---

## 🧱 1. Stan, eventy, maszyna

Instancja to zwykła klasa z `CorrelationId` i nazwą stanu (tu jako `string` - najprostsza do
utrwalenia w bazie):

```csharp
public class OrderState : SagaStateMachineInstance
{
    public Guid CorrelationId { get; set; }          // = OrderId
    public string CurrentState { get; set; } = "";
    public decimal Amount { get; set; }
    public int ReadyFlags { get; set; }              // bitmapa composite eventu
    public Guid? PaymentTimeoutTokenId { get; set; } // token zaplanowanego timeoutu
}
```

Maszyna dziedziczy po `MassTransitStateMachine<OrderState>`. Stany (`State`), eventy (`Event<T>`)
i harmonogram (`Schedule<,>`) to **właściwości**, które MassTransit sam inicjalizuje po nazwach
właściwości - w konstruktorze tylko je opisujesz:

```csharp
InstanceState(x => x.CurrentState);
Event(() => OrderSubmitted, e => e.CorrelateById(m => m.Message.OrderId));
// ... to samo dla PaymentReceived, StockReserved, ShipmentDispatched
```

Przepływ, który zbudowałem:

```
 OrderSubmitted ─► Submitted ──PaymentReceived──► Paid ─┐
   (Initially)         │  └──StockReserved (dowolna kolejność)  ├─ composite ReadyToShip ─► Shipping ─ShipmentDispatched─► Final
                       └──timeout 1,5 s──► Cancelled            ┘
```

## ⏱️ 2. `Initially`, `During` i timeout przez `Schedule`

```csharp
Schedule(() => PaymentTimeout, x => x.PaymentTimeoutTokenId, s =>
{
    s.Delay = TimeSpan.FromSeconds(1.5);
    s.Received = r => r.CorrelateById(m => m.Message.OrderId);
});

Initially(
    When(OrderSubmitted)
        .Then(c => c.Saga.Amount = c.Message.Amount)
        .Schedule(PaymentTimeout, c => new PaymentExpired(c.Saga.CorrelationId))
        .TransitionTo(Submitted));

During(Submitted,
    When(PaymentReceived)
        .Unschedule(PaymentTimeout)                       // płatność odwołuje timeout
        ...,
    When(PaymentTimeout.Received)                         // a brak płatności - anuluje
        .Publish(c => new OrderCancelled(c.Saga.CorrelationId, "brak płatności w terminie"))
        .TransitionTo(Cancelled));
```

`Schedule` w in-memory wymaga schedulera: `x.AddDelayedMessageScheduler()` w rejestracji i
`cfg.UseDelayedMessageScheduler()` na busie (ten sam mechanizm, co przy delayed redelivery w wydaniu
#2). Token zaplanowanej wiadomości MassTransit zapisuje w `PaymentTimeoutTokenId` - dzięki niemu
`Unschedule` wie, co odwołać.

Scenariusz **timeout** - nikt nie płaci:

```
[ 1071 ms] saga 4b3b5b38: OrderSubmitted (49.00 zł) -> Submitted, start timeoutu
[ 2588 ms] saga 4b3b5b38: TIMEOUT - brak płatności -> Cancelled
[ 2604 ms] [wynik] OrderCancelled 4b3b5b38: brak płatności w terminie
```

Od startu do timeoutu minęło ~1,5 s, dokładnie jak w `Delay`.

Scenariusz **płatność na czas** - po 200 ms; czekamy potem 2,2 s (dłużej niż timeout) i nic nie
anuluje zamówienia, więc `Unschedule` zadziałał:

```
[ 3776 ms] saga 926ec99c: OrderSubmitted (10 zł) -> Submitted, start timeoutu
[ 3977 ms] saga 926ec99c: PaymentReceived (stan przed: Submitted), timeout odwołany
[ 6177 ms] repozytorium: 4b3b5b38=Cancelled, 926ec99c=Paid
```

## 🧩 3. Composite event - "oba, w dowolnej kolejności"

W prawdziwym systemie płatność i rezerwacja towaru to dwie niezależne usługi; nie wiesz, która
odpowie pierwsza. Composite event rozwiązuje to bez ręcznego liczenia flag:

```csharp
CompositeEvent(() => ReadyToShip, x => x.ReadyFlags, PaymentReceived, StockReserved);

During(Submitted, Paid,
    When(ReadyToShip)
        .Publish(c => new ShipOrder(c.Saga.CorrelationId))   // komenda do magazynu
        .TransitionTo(Shipping));
```

Trzeba tylko dać mu pole `int` w instancji na bitmapę. W demie **celowo** stock przychodzi przed
płatnością. Prawdziwy przebieg całej ścieżki (od `Finalize` po `Finally`):

```
[    0 ms] saga 607a81b6: OrderSubmitted (199.99 zł) -> Submitted, start timeoutu
[  166 ms] saga 607a81b6: StockReserved (stan: Submitted)
[  483 ms] saga 607a81b6: composite ReadyToShip (płatność + stock) -> Shipping
[  529 ms] magazyn: pakuję i wysyłam 607a81b6
[  543 ms] saga 607a81b6: PaymentReceived (stan przed: Shipping), timeout odwołany
[  554 ms] saga 607a81b6: ShipmentDispatched -> koniec
[  568 ms] saga 607a81b6: Finally - sprzątanie
[  571 ms] [wynik] OrderCompleted 607a81b6
[ 1068 ms] repozytorium po zakończeniu: (pusto)
```

Migawki repozytorium w trakcie (`repozytorium: 607a81b6=Submitted`) i puste po końcu potwierdzają,
że `SetCompletedWhenFinalized()` usuwa instancję po `Finalize()`. Migawki bierzemy z
`IQuerySagaRepository<OrderState>` + `ILoadSagaRepository<OrderState>` - zarejestrowanych przez
`.InMemoryRepository()`.

> ⚠️ **Pułapka, w którą wpadłem (i którą widać w powyższym logu).** Zwróć uwagę na linijkę
> `PaymentReceived (stan przed: Shipping)`. Handler samego `PaymentReceived` wykonał się **po tym**, jak
> composite już przeniósł sagę do `Shipping`. W pierwszej wersji ten handler kończył się
> `TransitionTo(Paid)` - i **cofał** zamówienie z `Shipping` do `Paid`. Skutek: `ShipmentDispatched`
> od magazynu wpadł w stan, który go nie obsługuje, saga wybuchła (`Not accepted in state Paid`), a
> instancja została w repozytorium na zawsze. Lekarstwo w kodzie - guard:
> `.If(c => c.Saga.CurrentState != nameof(Shipping), x => x.TransitionTo(Paid))`. Wniosek: przy
> composite **kolejność wykonania aktywności dla składnika nie jest intuicyjna** - zawsze testuj
> ścieżkę, w której składnik domykający composite przychodzi jako ostatni. (Nie sprawdzałem, czy
> da się to ładniej rozwiązać kolejnością deklaracji; guard działa i jest jawny.)

## 🚧 4. Co się dzieje, gdy event nie pasuje do stanu

Tu saga jest **surowa**: event bez zdefiniowanej reakcji w bieżącym stanie to błąd, nie cichy no-op.
Test - `ShipmentDispatched` dla zamówienia, które jest tylko `Paid`:

```
[ 6802 ms] [Fault<ShipmentDispatched>] MassTransit.NotAcceptedStateMachineException: The ShipmentDispatched event is not handled during the Paid state for the OrderStateMachine state machine
```

Wyjątek `UnhandledEventException` opakowany w `NotAcceptedStateMachineException` przechodzi przez
zwykły pipeline: wiadomość dostaje się do `Fault<T>` (który możesz skonsumować jak w wydaniu #2).
Jeśli event jest **dopuszczalny, ale nieistotny** - deklarujesz to wprost przez `Ignore`:

```csharp
During(Cancelled,
    Ignore(PaymentReceived),
    Ignore(StockReserved));
```

Spóźniona płatność po anulowaniu (scenariusz 3) przeszła bez śladu, a stan pozostał `Cancelled`.
Uczciwie: nie uruchomiłem wariantu **bez** `Ignore`, więc nie pokażę outputu, jak by wtedy
zareagowała - z zasady z pkt 4 spodziewam się faultu, ale to nie jest zweryfikowane.

Osobny przypadek - event dla **nieistniejącej** sagi (`PaymentReceived` z losowym `OrderId`, który
nie startuje sagi): w demie nic się nie pojawiło ani w logu, ani w repozytorium (nie powstała
instancja). Nie sprawdzałem, dokąd poszła wiadomość (czy np. do `_skipped`) - odnotowuję tylko
obserwację.

## 🧪 Ściąga: kiedy saga, a kiedy consumer

| Sytuacja | Wybór |
|---|---|
| Jedna wiadomość, jedna akcja | zwykły consumer |
| Proces z wieloma krokami i stanem | saga |
| "Czekaj na A i B, kolejność dowolna" | composite event |
| "Jeśli nic się nie stanie w X czasu" | `Schedule` + `Unschedule` |
| Ochrona przed nietypowymi eventami | jawne `During` + `Ignore`, reszta = fault |
| Proces musi przeżyć restart | **nie** in-memory - potrzebne trwałe repozytorium (EF Core, Mongo, Redis) |

---

## 🚧 Czego dziś NIE zweryfikowałem

- **trwałych repozytoriów sag** (EF Core, MongoDB, Redis) i współbieżności/wersjonowania instancji
  (optymistyczne blokowanie) - in-memory repo znika z procesem, a scheduler in-memory z nim;
- działania `Schedule` na RabbitMQ (wymaga pluginu opóźnień lub Quartz) i na Azure Service Bus;
- zachowania **wyścigu**: `PaymentReceived` i `PaymentExpired` przychodzą w tym samym momencie;
- wariantu sagi bez `Ignore` w stanie `Cancelled` oraz losu wiadomości do nieznanej sagi;
- kompensacji (odwracania skutków kroków) - to kolejny odcinek.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) - dokładne komendy od zera. Demo trwa ok. 7 sekund i
kończy się samo.

---

<div align="center">

[← wróć do wydania #3 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
