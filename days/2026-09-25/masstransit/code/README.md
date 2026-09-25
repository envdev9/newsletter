# Kod do wydania #2 — MassTransit: retry, Fault<T>, _error/_skipped, redelivery, outbox

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej fragment artykułu + jak odpalić kod.

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`). Jeśli SDK jest w
`~/.dotnet`, dodaj je do PATH: `export PATH="$HOME/.dotnet:$PATH"`. Nie potrzeba
RabbitMQ ani Dockera - wszystko działa na transporcie in-memory.

## Fragment prasówki, którego dotyczy ten kod

> Retry konfiguruje się per endpoint: `UseMessageRetry(r => r.Immediate(3))` to 3
> ponowienia, czyli do 4 wywołań consumera. `Interval` daje równe przerwy,
> `Exponential` - rosnące; `Ignore<ArgumentException>()` wyłącza ponawianie
> błędów, które się nie naprawią. Po wyczerpaniu retry MassTransit publikuje
> `Fault<T>` (zwykły event) i przenosi wiadomość do kolejki `<endpoint>_error` z
> nagłówkami `MT-Fault-*`. Wiadomość bez pasującego consumera trafia do
> `<endpoint>_skipped`. Transport in-memory tworzy obie kolejki (sprawdzone
> doświadczalnie). `UseMessageRetry` trzyma wiadomość w pamięci consumera, a
> `UseDelayedRedelivery` odsyła ją do kolejki z opóźnieniem - to dwa poziomy, które
> się łączy. `UseInMemoryOutbox` wstrzymuje `Publish` z consumera do udanego końca
> `Consume`, więc retry po awarii nie duplikuje eventów (nie chroni jednak przed
> crashem procesu - do tego służy outbox transakcyjny, niesprawdzany tutaj).

## Struktura projektu

```
masstransit-retry-demo/
├── MassTransitRetryDemo.csproj   # MassTransit 8.5.10 + Microsoft.Extensions.Hosting
├── Messages.cs                   # kontrakty, consumery, Fault<T>, observer, "podsłuchy" _error/_skipped
└── Program.cs                    # konfiguracja endpointów + 7 scenariuszy po kolei
```

## Jak uruchomić od zera

```bash
export PATH="$HOME/.dotnet:$PATH"
cd masstransit-retry-demo
dotnet restore
dotnet build
dotnet run
```

(z katalogu głównego repo: `dotnet run --project days/2026-09-25/masstransit/code/masstransit-retry-demo`)

Demo trwa ok. 10 s i kończy się samo (kod wyjścia 0). Wartości `[xxx ms]` to czas od
startu procesu - zmienią się w Twoim uruchomieniu (odstępy exponential nie są
identyczne między uruchomieniami).

## Zweryfikowany output (prawdziwe uruchomienie)

```
=== 1. Immediate(3): błąd nietrwały, sukces na 3. próbie ===
[    0 ms] [flaky] próba #1 (GetRetryAttempt=0)
[   18 ms] [flaky] próba #2 (GetRetryAttempt=1)
[   19 ms] [flaky] próba #3 (GetRetryAttempt=2)
[   19 ms] [flaky] SUKCES

=== 2. Interval(3, 300 ms): błąd trwały -> Fault<T> + _error ===
[  453 ms] [interval] próba #1
[  757 ms] [interval] próba #2
[ 1060 ms] [interval] próba #3
[ 1360 ms] [interval] próba #4
[ 1523 ms] [observer] ConsumeFault<ChargeCardInterval>: InvalidOperationException
[ 1525 ms] [Fault<ChargeCardInterval>] System.InvalidOperationException: zawsze wybucha (interval) (FaultedMessageId: True, wiadomość: ChargeCardInterval)
[ 1546 ms] [SPY /charge-interval_error] dotarła ChargeCardInterval
[ 1547 ms] [SPY]     MT-Reason = fault
[ 1547 ms] [SPY]     MT-Fault-ExceptionType = System.InvalidOperationException
[ 1547 ms] [SPY]     MT-Fault-InputAddress = loopback://localhost/charge-interval
[ 1547 ms] [SPY]     MT-Fault-Message = zawsze wybucha (interval)
[ 1547 ms] [SPY]     MT-Fault-Timestamp = 2026-09-25T21:32:52.4112955Z
[ 1547 ms] [SPY]     MT-Fault-ConsumerType = MassTransitRetryDemo.AlwaysFailsIntervalConsumer
[ 1547 ms] [SPY]     MT-Fault-MessageType = MassTransitRetryDemo.ChargeCardInterval
[ 1547 ms] [SPY]     MT-Fault-RetryCount = 3

=== 3. Exponential(4, 100 ms..2 s): błąd trwały ===
[ 2459 ms] [exponential] próba #1
[ 2636 ms] [exponential] próba #2
[ 2979 ms] [exponential] próba #3
[ 3553 ms] [exponential] próba #4
[ 4770 ms] [exponential] próba #5
[ 4786 ms] [observer] ConsumeFault<ChargeCardExponential>: InvalidOperationException

=== 4. Ignore<ArgumentException>: brak retry, od razu Fault ===
[ 4976 ms] [invalid] próba #1
[ 4989 ms] [observer] ConsumeFault<ChargeCardInvalid>: ArgumentException
[ 4992 ms] [Fault<ChargeCardInvalid>] System.ArgumentException: kwota ujemna - retry nic tu nie pomoże (FaultedMessageId: True, wiadomość: ChargeCardInvalid)

=== 5. Delayed redelivery: 3 dostarczenia, każde z 1 retry ===
[ 5489 ms] [redelivery] dostarczenie #1, retry w tym dostarczeniu=0
[ 5491 ms] [redelivery] dostarczenie #1, retry w tym dostarczeniu=1
[ 6038 ms] [redelivery] dostarczenie #2, retry w tym dostarczeniu=0
[ 6038 ms] [redelivery] dostarczenie #2, retry w tym dostarczeniu=1
[ 7041 ms] [redelivery] dostarczenie #3, retry w tym dostarczeniu=0
[ 7041 ms] [redelivery] SUKCES

=== 6. Outbox: bez i z (publish w consumerze + awaria po nim) ===
[ 9001 ms] [bez outboxa] opublikowano OrderShipped (próba #1)
[ 9006 ms] [z outboxem] opublikowano OrderShipped (próba #1)
[ 9007 ms] [bez outboxa] opublikowano OrderShipped (próba #2)
[ 9008 ms] [OrderShipped] odebrano event od: bez-outboxa
[ 9010 ms] [OrderShipped] odebrano event od: bez-outboxa
[ 9012 ms] [z outboxem] opublikowano OrderShipped (próba #2)
[ 9022 ms] [OrderShipped] odebrano event od: z-outboxem
[ 9995 ms] PODSUMOWANIE outbox: OrderShipped bez outboxa = 2, z outboxem = 1

=== 7. _skipped: wiadomość, której endpoint nie umie skonsumować ===
[10014 ms] [SPY /flaky-endpoint_skipped] dotarła NobodyConsumesThis
[10014 ms] [SPY]     MT-Reason = dead-letter

Koniec.
```

Z outputu usunięto tylko: nagłówki `MT-Host-*` i `MT-Fault-StackTrace` (filtruje je sam
kod - patrz `ErrorQueueSpy.Dump`) oraz logi `R-RETRY`/`R-FAULT` z ich stack trace'ami
(wyciszone filtrem `MassTransit.ReceiveTransport` w `Program.cs`; w produkcji zostaw je
włączone).

Sprawdzone lokalnie na `.NET SDK 10`, pakiet `MassTransit 8.5.10`, przed publikacją.

### Uwagi

- Scenariusz 2 używa `Send` na `queue:charge-interval`, a nie `Publish` - inaczej
  "podsłuch" na `_error` dostałby kopię wiadomości jako zwykły subskrybent typu (patrz
  ostrzeżenie w artykule).
- `_error`/`_skipped` w in-memory istnieją tylko w pamięci procesu - po zakończeniu
  programu nie zostaje po nich nic.
