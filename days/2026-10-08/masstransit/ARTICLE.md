<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #15 — 8 października 2026

![MassTransit](https://img.shields.io/badge/MassTransit-FF6600?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Wzorzec](https://img.shields.io/badge/wzorzec-Courier%20%2B%20kompensacja-blueviolet?style=for-the-badge)

## 📨 Courier w czterech krokach: kolejność kompensacji, zmienne slipa i kompensacja, która sama zawodzi

</div>

---

> _"Cofnięcie transakcji też może się nie udać. Pytanie, czy twój framework powie ci o tym głośno."_

W #7 zbudowaliśmy routing slip z dwiema aktywnościami i zobaczyliśmy, że porażka drugiej
kompensuje pierwszą. Zostawiłem wtedy otwarte: itinerary z 3+ aktywnościami, kompensacja,
która sama zawodzi (`context.Failed`). Dziś właśnie to - na czterech aktywnościach, z
**realnym** outputem. MassTransit **8.5.10**, .NET 10, transport in-memory (tu broker jest
bez znaczenia - Courier jedzie po zwykłych kolejkach; RabbitMQ z #7 niczego by nie zmienił
w logice, ale tego nie sprawdzałem). Kod: [`code/`](code/).

## 🎯 Dlaczego to ważne

Saga/routing slip ma sens dopiero wtedy, gdy wiesz, co się stanie **w najgorszym
scenariuszu**: krok 4 pada, a kompensacja kroku 2 też. Czy reszta jest cofana? Czy dostaniesz
`RoutingSlipFaulted`? Odpowiedzi poniżej są inne, niż podpowiada intuicja - i wprost
wpływają na to, czy zostawisz w systemie zarezerwowany towar bez właściciela.

| Scenariusz | Wynik końcowy slipa | Co zostało skompensowane |
|---|---|---|
| ✅ `ok` | `RoutingSlipCompleted` | nic |
| 💥 `fail` (krok 4 rzuca) | `RoutingSlipFaulted` | 3, 2, 1 (odwrotna kolejność) |
| ☠️ `fail-comp` (krok 4 rzuca, kompensacja kroku 2 zawodzi) | `RoutingSlipCompensationFailed` | tylko 3; **krok 1 nietknięty** |

---

## 🧩 1. Itinerary z czterema aktywnościami

`ReserveInventory -> AuthorizePayment -> CreateShipment -> NotifyCustomer`. Wszystkie cztery
mają kompensację (`IActivity<TArgs, TLog>`), dziedziczą po wspólnej klasie bazowej, żeby kod
zmieścił się w jednym pliku. Zdarzenia z całego slipa zbiera jeden konsument przez
`slip.AddSubscription(adres, RoutingSlipEvents.All)`.

Sukces (`ok`), prawdziwy output:

```
[    0 ms]   EXECUTE     ReserveInventory (produkuje zmienna ReservationId)
[  190 ms]   [event] ActivityCompleted           ReserveInventory
[  217 ms]   EXECUTE     AuthorizePayment reservationId=RES-ORD-1
...
[  244 ms]   [event] ActivityCompleted           NotifyCustomer
[  282 ms]   [event] RoutingSlipCompleted
```

Zwróć uwagę na `reservationId=RES-ORD-1` - to prowadzi do punktu 2.

## 📦 2. Zmienne slipa: dane płyną między aktywnościami bez ręcznego wiązania

`ReserveInventory` kończy się przez `context.CompletedWithVariables(log, new { ReservationId = ... })`.
W itinerary **nie podałem** `ReservationId` w argumentach pozostałych aktywności, a mimo to
`AuthorizePayment`, `CreateShipment` i `NotifyCustomer` mają go w `Arguments.ReservationId`
(wypełnił go MassTransit po nazwie właściwości `StepArgs.ReservationId`). Dowód: powyższy
output - każdy kolejny krok drukuje `reservationId=RES-ORD-1`.

Pierwsza próba kompilacji ujawniła ciekawostkę API: `context.Completed(log, new { ... })` **nie
istnieje** (drugi parametr to callback opcji), zmienne ustawia się metodą
`CompletedWithVariables`.

## 💥 3. Porażka w kroku 4: kompensacja idzie od końca

`NotifyCustomer` rzuca wyjątek (tryb `fail`). Prawdziwy output:

```
[  134 ms]   EXECUTE     NotifyCustomer   rzuca wyjatek
[  304 ms]   [event] ActivityFaulted             NotifyCustomer: NotifyCustomer nie powiodl sie
[  333 ms]   COMPENSATE  CreateShipment   ok
[  352 ms]   COMPENSATE  AuthorizePayment ok
[  355 ms]   COMPENSATE  ReserveInventory ok
[  367 ms]   [event] RoutingSlipFaulted
[  368 ms] WYNIK koncowy slipa: Faulted
```

Kolejność: **3, 2, 1** - odwrotna do wykonania - a `RoutingSlipFaulted` dopiero **po**
ostatniej kompensacji (potwierdza obserwację z #7 na dłuższym łańcuchu). Aktywność, która
sama rzuciła (`NotifyCustomer`), nie jest kompensowana - jej Execute się nie ukończył.
(Przerwa ~170 ms między wyjątkiem a `ActivityFaulted` zdarza się przy pierwszym rzucie wyjątku w
procesie; nie badałem jej przyczyny.)

## ☠️ 4. Kompensacja, która sama zawodzi: `context.Failed(ex)`

Tryb `fail-comp`: krok 4 rzuca, a kompensacja kroku 2 (`AuthorizePayment`) zwraca
`context.Failed(new InvalidOperationException(...))`:

```
[  248 ms]   [event] ActivityFaulted             NotifyCustomer: NotifyCustomer nie powiodl sie
[  279 ms]   COMPENSATE  CreateShipment   ok
[  298 ms]   [event] ActivityCompensated         CreateShipment
[  299 ms]   COMPENSATE  AuthorizePayment ZAWODZI (context.Failed)
[  319 ms]   [event] ActivityCompensationFailed  AuthorizePayment: kompensacja AuthorizePayment zawiodla
[  328 ms]   [event] RoutingSlipCompensationFailed: kompensacja AuthorizePayment zawiodla
[  329 ms] WYNIK koncowy slipa: CompensationFailed
```

Co z tego wynika (zmierzone, nie założone):

- **Łańcuch kompensacji zatrzymuje się** na pierwszej nieudanej. `ReserveInventory` (krok 1) **nie
  został skompensowany** - po wyniku odczekałem jeszcze 500 ms, żadnego `COMPENSATE ReserveInventory`.
- Zamiast `RoutingSlipFaulted` przychodzi osobne zdarzenie `RoutingSlipCompensationFailed`. Jeśli
  twój konsument nasłuchuje tylko `Completed`/`Faulted` (jak w #7), **ten przypadek ci umknie**.
- Zostajesz z niespójnym stanem (towar zarezerwowany, płatność w limbo) i musisz go posprzątać
  ręcznie albo własnym procesem.

## 🪤 Haczyki

1. **Kompensacja widzi tylko log.** `CompensateContext<TLog>` nie ma `Arguments` ani `Variables`
   (kompilator odrzucił `context.Variables`). Wszystko, czego potrzebujesz do cofnięcia, musisz
   zapisać w logu w `Execute` - dlatego w demie `StepLog` niesie flagę `BreakCompensation`.
2. **`CompensationFailed` to inny typ zdarzenia niż `Faulted`.** Subskrybuj oba, albo użyj
   `RoutingSlipEvents.All`.
3. **Zawiedziona kompensacja przerywa resztę łańcucha** - nie ma automatycznego "spróbuj dalej".

---

## 🗺️ Ściąga

| Chcę... | Użyj |
|---|---|
| przekazać dane dalej w itinerary | `context.CompletedWithVariables(log, new { Prop = ... })`; odbiorca ma właściwość o tej samej nazwie w `TArgs` |
| zgłosić porażkę kompensacji | `return context.Failed(ex)` w `Compensate` |
| wszystkie zdarzenia slipa | `builder.AddSubscription(adres, RoutingSlipEvents.All)` + `IConsumer<RoutingSlip...>` |
| zdarzenie po nieudanej kompensacji | `RoutingSlipCompensationFailed` (nie `Faulted`) |

---

## 🚧 Czego dziś NIE zweryfikowałem

- Dokładnego znaczenia pozostałych wariantów (`RoutingSlipEvents.Supplemental`, filtry
  `Completed | Faulted` itp.) poza `All`.
- Zachowania na RabbitMQ (tu in-memory) ani przy ponownym uruchomieniu procesu w trakcie slipa.
- `ReviseItinerary`, dodawania aktywności w trakcie wykonania, `AddSubscription` z
  `RoutingSlipEventContents` (filtrowanie treści zdarzeń).
- Interakcji z `UseMessageRetry` na kolejce execute (czy retry odbywa się przed `ActivityFaulted`).
- Przyczyny ~170 ms przerwy przed `ActivityFaulted`.
- Trwałych sag (EF/Mongo/Redis) i `UseDelayedRedelivery` - nadal przed nami. Brak testów
  `dotnet test`; weryfikacja to `dotnet run`.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) - instrukcja od zera (bez Dockera, sam .NET 10 SDK).

---

<div align="center">

[← wróć do wydania #15 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
