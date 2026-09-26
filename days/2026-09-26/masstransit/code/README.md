# Kod do wydania #3 — MassTransit: saga (state machine), Schedule, composite event

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej fragment artykułu + jak odpalić kod.

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`). Jeśli SDK jest w
`~/.dotnet`, dodaj je do PATH: `export PATH="$HOME/.dotnet:$PATH"`. Nie potrzeba
RabbitMQ ani Dockera - wszystko działa na transporcie in-memory.

## Fragment prasówki, którego dotyczy ten kod

> Saga w MassTransit to maszyna stanów (`MassTransitStateMachine<TState>`) z jedną instancją stanu
> na proces. `CorrelateById` wiąże eventy z instancją, `Initially` opisuje event startujący,
> `During(stan, ...)` - eventy dozwolone w danym stanie, a `Finally` + `SetCompletedWhenFinalized()`
> sprząta i usuwa instancję po `Finalize()`. `Schedule` daje timeout jako zaplanowaną wiadomość
> (`Unschedule` go odwołuje), a `CompositeEvent` odpala się, gdy zaszły wszystkie składniki - w
> dowolnej kolejności. Event bez zdefiniowanej reakcji w bieżącym stanie kończy się faultem
> (`Ignore` to jawny no-op). Uwaga: handler składnika composite'u wykonuje się po tym, jak composite
> już przeniósł sagę dalej - stąd guard przed `TransitionTo(Paid)` w kodzie. Repozytorium in-memory
> i scheduler in-memory znikają z procesem - produkcja wymaga trwałego repozytorium.

## Struktura projektu

```
masstransit-saga-demo/
├── MassTransitSagaDemo.csproj   # MassTransit 8.5.10 + Microsoft.Extensions.Hosting
├── OrderSaga.cs                 # kontrakty, OrderState, OrderStateMachine, consumery, Log
└── Program.cs                   # rejestracja (in-memory repo + scheduler) + 6 scenariuszy
```

## Jak uruchomić od zera

```bash
export PATH="$HOME/.dotnet:$PATH"
cd masstransit-saga-demo
dotnet restore
dotnet build
dotnet run
```

(z katalogu głównego repo: `dotnet run --project days/2026-09-26/masstransit/code/masstransit-saga-demo`)

Demo trwa ok. 7 s i kończy się samo (kod wyjścia 0). Wartości `[xxx ms]` to czas od startu procesu
i skrócone GUID-y zamówień będą u Ciebie inne.

## Zweryfikowany output (prawdziwe uruchomienie)

```
=== 1. Happy path: stock przed płatnością, composite ReadyToShip ===
[    0 ms] saga 607a81b6: OrderSubmitted (199.99 zł) -> Submitted, start timeoutu
[  144 ms] repozytorium: 607a81b6=Submitted
[  166 ms] saga 607a81b6: StockReserved (stan: Submitted)
[  453 ms] repozytorium: 607a81b6=Submitted
[  483 ms] saga 607a81b6: composite ReadyToShip (płatność + stock) -> Shipping
[  529 ms] magazyn: pakuję i wysyłam 607a81b6
[  543 ms] saga 607a81b6: PaymentReceived (stan przed: Shipping), timeout odwołany
[  554 ms] saga 607a81b6: ShipmentDispatched -> koniec
[  568 ms] saga 607a81b6: Finally - sprzątanie
[  571 ms] [wynik] OrderCompleted 607a81b6
[ 1068 ms] repozytorium po zakończeniu: (pusto)

=== 2. Timeout: nikt nie płaci (Schedule 1,5 s) ===
[ 1071 ms] saga 4b3b5b38: OrderSubmitted (49.00 zł) -> Submitted, start timeoutu
[ 2588 ms] saga 4b3b5b38: TIMEOUT - brak płatności -> Cancelled
[ 2604 ms] [wynik] OrderCancelled 4b3b5b38: brak płatności w terminie
[ 3272 ms] repozytorium: 4b3b5b38=Cancelled

=== 3. Spóźniona płatność w stanie Cancelled (Ignore) ===
[ 3775 ms] repozytorium: 4b3b5b38=Cancelled

=== 4. Płatność przed upływem czasu odwołuje timeout (Unschedule) ===
[ 3776 ms] saga 926ec99c: OrderSubmitted (10 zł) -> Submitted, start timeoutu
[ 3977 ms] saga 926ec99c: PaymentReceived (stan przed: Submitted), timeout odwołany
[ 6177 ms] repozytorium: 4b3b5b38=Cancelled, 926ec99c=Paid

=== 5. PaymentReceived dla nieznanego zamówienia ===
[ 6679 ms] repozytorium: 4b3b5b38=Cancelled, 926ec99c=Paid

=== 6. ShipmentDispatched w stanie Paid (niezdefiniowane przejście) ===
[ 6802 ms] [Fault<ShipmentDispatched>] MassTransit.NotAcceptedStateMachineException: The ShipmentDispatched event is not handled during the Paid state for the OrderStateMachine state machine
[ 7180 ms] repozytorium: 4b3b5b38=Cancelled, 926ec99c=Paid

Koniec.
```

Logi MassTransit (`R-FAULT` ze stack trace'ami) są wyciszone filtrem `LogLevel.Critical` w
`Program.cs`; w produkcji zostaw je włączone.

Sprawdzone lokalnie na `.NET SDK 10`, pakiet `MassTransit 8.5.10`, przed publikacją.

### Uwagi

- Niezweryfikowane: trwałe repozytoria sag (EF Core/Mongo/Redis), RabbitMQ/ASB, wyścig płatności z
  timeoutem, wariant bez `Ignore` w `Cancelled`, los eventu dla nieznanej sagi.
- Stan `Paid` w scenariuszu 4 zostaje w repozytorium celowo (demo nie kończy tego zamówienia).
