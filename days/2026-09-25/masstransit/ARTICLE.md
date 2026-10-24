<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #2 — 25 września 2026

![MassTransit](https://img.shields.io/badge/MassTransit-FF6600?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-%C5%9Brednio%20zaawansowany-orange?style=for-the-badge)
![Transport](https://img.shields.io/badge/transport-in--memory-blue?style=for-the-badge)

## 📨 Kiedy consumer wybucha: retry, Fault&lt;T&gt;, `_error`, `_skipped`, redelivery i outbox

</div>

---

> _"W systemach rozproszonych pytanie nie brzmi „czy consumer się wywróci?", tylko
> „co się stanie z wiadomością, gdy to zrobi?"."_

Wczoraj (wydanie #1) był szczęśliwy scenariusz: `Publish` → `Consume` → koniec. Dziś
**nieszczęśliwy**, czyli ten, który w produkcji zdarza się co tydzień: baza na
sekundę nie odpowiada, bramka płatnicza rzuca 503, komunikat ma zły kształt. Cały kod
jest w [`code/`](code/) i **działa na samym transporcie in-memory** - bez RabbitMQ i
Dockera. Każdy fragment outputu niżej pochodzi z prawdziwego uruchomienia
(MassTransit **8.5.10**, .NET 10).

## 🎯 Dlaczego to ważne

Domyślnie (bez żadnej konfiguracji) wyjątek w consumerze = wiadomość ląduje w kolejce
`_error` po **pierwszej** nieudanej próbie (tak mówi dokumentacja; osobno tego dziś nie
mierzyłem). Jedno chwilowe mrugnięcie sieci i zamówienie
wisi w kolejce błędów, czekając na człowieka. Z drugiej strony - naiwne "ponawiaj
zawsze" potrafi zalać zdychającą zależność i zduplikować efekty uboczne. Dziś dostajesz
narzędzia do świadomej decyzji.

| Narzędzie | Odpowiada na pytanie | Gdzie żyje |
|---|---|---|
| 🔁 `UseMessageRetry` | "Ponów **teraz/zaraz**, w tym samym procesie" | filtr na endpointcie, wiadomość nie opuszcza consumera |
| ⏳ `UseDelayedRedelivery` | "Wróć za **sekundy/minuty**, nie blokuj kolejki" | wiadomość wraca do kolejki po opóźnieniu (scheduler) |
| ☠️ `_error` | "Co jeśli nic nie pomogło?" | kolejka `<endpoint>_error` |
| 🗑️ `_skipped` | "Co jeśli nikt nie umie tego przeczytać?" | kolejka `<endpoint>_skipped` |
| 📢 `Fault<T>` | "Kto ma się dowiedzieć o porażce?" | zwykły event, subskrybujesz jak każdy inny |
| 📦 Outbox | "Co z eventami wysłanymi przed awarią?" | filtr wstrzymujący `Publish` do końca `Consume` |

---

## 🔁 1. `UseMessageRetry` - trzy polityki

Retry konfiguruje się **per endpoint** (nie per consumer), w `ReceiveEndpoint`:

```csharp
cfg.ReceiveEndpoint("flaky-endpoint", e =>
{
    e.UseMessageRetry(r => r.Immediate(3));           // 3 ponowienia, bez przerwy
    e.ConfigureConsumer<FlakyChargeConsumer>(context);
});
```

Ważna arytmetyka: `Immediate(3)` to **3 ponowienia, czyli do 4 wywołań** consumera.
Numer próby odczytasz z `context.GetRetryAttempt()` (0 = pierwsza).

### Immediate - błąd nietrwały (consumer psuje się 2 pierwsze razy)

```
[    0 ms] [flaky] próba #1 (GetRetryAttempt=0)
[   18 ms] [flaky] próba #2 (GetRetryAttempt=1)
[   19 ms] [flaky] próba #3 (GetRetryAttempt=2)
[   19 ms] [flaky] SUKCES
```

Wiadomość została przetworzona, nikt niczego nie zauważył (poza logiem). Uwaga: próby
dzieli **1 ms**. Na chwilowy błąd sieciowy to za mało - dlatego są kolejne polityki.

### Interval i Exponential - błąd trwały

```csharp
e.UseMessageRetry(r => r.Interval(3, TimeSpan.FromMilliseconds(300)));

e.UseMessageRetry(r => r.Exponential(4,
    TimeSpan.FromMilliseconds(100), TimeSpan.FromSeconds(2), TimeSpan.FromMilliseconds(100)));
```

Consumery rzucają zawsze. Prawdziwe odstępy między próbami:

```
[  453 ms] [interval] próba #1        [ 2459 ms] [exponential] próba #1
[  757 ms] [interval] próba #2        [ 2636 ms] [exponential] próba #2
[ 1060 ms] [interval] próba #3        [ 2979 ms] [exponential] próba #3
[ 1360 ms] [interval] próba #4        [ 3553 ms] [exponential] próba #4
                                      [ 4770 ms] [exponential] próba #5
```

- **Interval** - równe ~300 ms; 3 ponowienia = 4 wywołania.
- **Exponential** - odstępy rosną (u nas ok. 0,18 → 0,34 → 0,57 → 1,2 s), 4 ponowienia
  = 5 wywołań. Sygnatura: `(retryLimit, minInterval, maxInterval, intervalDelta)`. Odstępy
  nie są matematycznie "czyste" (w kolejnych uruchomieniach różniły się o kilkadziesiąt ms),
  więc traktuj wartości jako rząd wielkości.

> 💡 **Zasada kciuka:** Immediate - na kolizje/deadlocki (błąd znika po milisekundach).
> Interval - gdy znasz czas zdrowienia zależności. Exponential - domyślny wybór dla
> zależności zewnętrznych: nie dobijasz tego, co już leży.

### Filtr wyjątków: nie ponawiaj tego, co się nie poprawi

`ArgumentException` (ujemna kwota) nie zniknie po 5 próbach. `Ignore<T>` wyłącza retry
dla wskazanych wyjątków:

```csharp
e.UseMessageRetry(r =>
{
    r.Ignore<ArgumentException>();
    r.Immediate(5);
});
```

```
[ 4976 ms] [invalid] próba #1              <- i koniec, mimo Immediate(5)
[ 4989 ms] [observer] ConsumeFault<ChargeCardInvalid>: ArgumentException
[ 4992 ms] [Fault<ChargeCardInvalid>] System.ArgumentException: kwota ujemna ...
```

(Jest też odwrotność, `Handle<T>` - ponawiaj *tylko* wskazane wyjątki.)

---

## ☠️ 2. Po wyczerpaniu retry: `Fault<T>` i kolejka `_error`

Gdy ostatnia próba się nie uda, dzieją się **dwie niezależne rzeczy**:

1. MassTransit **publikuje `Fault<T>`** - zwykły event, który niesie oryginalną
   wiadomość + listę wyjątków. Subskrybujesz go jak każdy inny (`IConsumer<Fault<T>>`),
   np. żeby wysłać alert albo wystartować kompensację.
2. Oryginalna wiadomość jest **przenoszona do kolejki `<endpoint>_error`** wraz z
   nagłówkami opisującymi awarię.

Do tego na poziomie busa możesz podpiąć obserwatora (`IConsumeObserver.ConsumeFault`) -
przydatne do metryk "consumer faulted" bez ruszania samych consumerów.

### Czy in-memory naprawdę ma `_error`? Sprawdziłem: tak

To była moja wątpliwość przed uruchomieniem: transport in-memory bywa traktowany jak
"udawany". Zbudowałem "podsłuch" - zwykły endpoint o nazwie `charge-interval_error` z
consumerem tego samego typu. Wynik (po wyczerpaniu 4 wywołań):

```
[ 1523 ms] [observer] ConsumeFault<ChargeCardInterval>: InvalidOperationException
[ 1525 ms] [Fault<ChargeCardInterval>] System.InvalidOperationException: zawsze wybucha (interval) ...
[ 1546 ms] [SPY /charge-interval_error] dotarła ChargeCardInterval
[ 1547 ms] [SPY]     MT-Reason = fault
[ 1547 ms] [SPY]     MT-Fault-ExceptionType = System.InvalidOperationException
[ 1547 ms] [SPY]     MT-Fault-InputAddress = loopback://localhost/charge-interval
[ 1547 ms] [SPY]     MT-Fault-Message = zawsze wybucha (interval)
[ 1547 ms] [SPY]     MT-Fault-ConsumerType = MassTransitRetryDemo.AlwaysFailsIntervalConsumer
[ 1547 ms] [SPY]     MT-Fault-MessageType = MassTransitRetryDemo.ChargeCardInterval
[ 1547 ms] [SPY]     MT-Fault-RetryCount = 3
```

Wniosek: **in-memory tworzy `_error` i dokłada te same nagłówki `MT-Fault-*`** (jest też
`MT-Fault-StackTrace`, wyciąłem go z outputu). `MT-Fault-RetryCount = 3` potwierdza
arytmetykę: 3 ponowienia po pierwszej próbie.

> ⚠️ **Pułapka, w którą sam wpadłem.** W pierwszej wersji dema *publikowałem*
> wiadomość, a endpoint-podsłuch miał consumera tego samego typu - dostał więc kopię od
> razu, jako zwykły subskrybent, z pustymi nagłówkami (widać to było w logu jeszcze przed
> pierwszą próbą consumera). Do testowania `_error` **wysyłaj (`Send`) na konkretną kolejkę**,
> a nie publikuj - inaczej pomylisz fan-out z przeniesieniem do kolejki błędów.

### Co z tymi wiadomościami dalej?

W in-memory - nic, znikają razem z procesem (`_error` też jest w pamięci). W realnym
brokerze (RabbitMQ, ASB) to trwała kolejka, z której robi się ponowne odtwarzanie
("move back to the queue") ręcznie lub narzędziem. Nie sprawdzałem tego dziś - to temat
na wydanie o RabbitMQ.

---

## 🗑️ 3. `_skipped` - wiadomość, której nikt nie umie obsłużyć

`_error` to "consumer się wywrócił". `_skipped` to inna sytuacja: wiadomość **dotarła
poprawnie na endpoint, ale endpoint nie ma consumera na ten typ**. Nie ma sensu jej
ponawiać, więc idzie do `<endpoint>_skipped`. Test: wysłałem `NobodyConsumesThis` na
kolejkę `flaky-endpoint` (która konsumuje tylko `ChargeCard`):

```
[10014 ms] [SPY /flaky-endpoint_skipped] dotarła NobodyConsumesThis
[10014 ms] [SPY]     MT-Reason = dead-letter
```

Ciekawostka z outputu: powód w nagłówku to `dead-letter` (nie "skipped"), a nie ma
tam żadnych `MT-Fault-*` - bo żaden wyjątek nie wystąpił. Takie wiadomości bywają
objawem **niedopasowanych wersji kontraktów** albo błędnego routingu - `_skipped`, która
rośnie, to sygnał alarmowy.

---

## ⏳ 4. Retry vs redelivery - to nie to samo

To najczęściej mylona para. Różnica jest strukturalna:

| | 🔁 `UseMessageRetry` | ⏳ `UseDelayedRedelivery` |
|---|---|---|
| Gdzie czeka wiadomość | **w pamięci** consumera (wątek/zadanie trzyma ją) | **wraca do kolejki** z opóźnieniem (scheduler) |
| Typowy czas | ms .. kilka sekund | sekundy .. minuty .. godziny |
| Blokuje endpoint? | tak - na czas przerw | nie - endpoint obsługuje inne wiadomości |
| Wymaga | nic | schedulera (`UseDelayedMessageScheduler`) |
| Licznik | `GetRetryAttempt()` | `GetRedeliveryCount()` |
| Zysk | prosto, szybko | odciąża zależność na dłużej, nie trzyma zasobów |

Zwykle łączy się je warstwowo: krótki retry na drobne zakłócenia, a gdy nie pomoże -
odroczone redelivery. Konfiguracja z dema:

```csharp
cfg.UseDelayedMessageScheduler();                    // na poziomie busa

cfg.ReceiveEndpoint("charge-redelivery", e =>
{
    e.UseDelayedRedelivery(r => r.Intervals(TimeSpan.FromMilliseconds(500), TimeSpan.FromSeconds(1)));
    e.UseMessageRetry(r => r.Immediate(1));          // retry wewnątrz każdego dostarczenia
    e.ConfigureConsumer<RedeliveryConsumer>(context);
});
```

Prawdziwy output (consumer pada przy dostarczeniach 1 i 2, przechodzi w 3.):

```
[ 5489 ms] [redelivery] dostarczenie #1, retry w tym dostarczeniu=0
[ 5491 ms] [redelivery] dostarczenie #1, retry w tym dostarczeniu=1
[ 6038 ms] [redelivery] dostarczenie #2, retry w tym dostarczeniu=0     <- +~550 ms
[ 6038 ms] [redelivery] dostarczenie #2, retry w tym dostarczeniu=1
[ 7041 ms] [redelivery] dostarczenie #3, retry w tym dostarczeniu=0     <- +~1000 ms
[ 7041 ms] [redelivery] SUKCES
```

Widać strukturę dwupoziomową: 2 wywołania w każdym dostarczeniu (oryginał + 1 retry),
przerwy 0,5 s i 1 s między dostarczeniami - dokładnie z `Intervals(...)`. Zadziałało to
na samym in-memory, bez pluginów brokera. (Uwaga: w RabbitMQ delayed redelivery wymaga
dodatkowego mechanizmu opóźniania - nie sprawdzałem tego dziś.)

**Kolejność w kodzie ma znaczenie:** `UseDelayedRedelivery` deklarujesz **przed**
`UseMessageRetry` (jest "na zewnątrz"), bo to filtry układane w potok - retry jest
wewnątrz redelivery.

---

## 📦 5. Outbox - eventy wysłane przed awarią

Groźniejszy problem niż same powtórki: consumer robi `Publish(OrderShipped)`, **po
czym** wybucha i jest ponawiany. Bez ochrony event wyszedł już na świat, a retry
opublikuje go **drugi raz**. Test na dwóch consumerach, identycznych poza `UseInMemoryOutbox`:

```csharp
cfg.ReceiveEndpoint("ship-safe", e =>
{
    e.UseMessageRetry(r => r.Immediate(2));
    e.UseInMemoryOutbox(context);                 // PO retry, żeby leżał wewnątrz niego
    e.ConfigureConsumer<ShipOrderSafeConsumer>(context);
});
```

```
[ 9001 ms] [bez outboxa] opublikowano OrderShipped (próba #1)
[ 9006 ms] [z outboxem] opublikowano OrderShipped (próba #1)
[ 9007 ms] [bez outboxa] opublikowano OrderShipped (próba #2)
[ 9008 ms] [OrderShipped] odebrano event od: bez-outboxa
[ 9010 ms] [OrderShipped] odebrano event od: bez-outboxa
[ 9012 ms] [z outboxem] opublikowano OrderShipped (próba #2)
[ 9022 ms] [OrderShipped] odebrano event od: z-outboxem
[ 9995 ms] PODSUMOWANIE outbox: OrderShipped bez outboxa = 2, z outboxem = 1
```

Każdy consumer wywołał `Publish` dwa razy (dwie próby), ale **odbiorca dostał 2 eventy
bez outboxa i tylko 1 z outboxem**. In-memory outbox buforuje `Publish`/`Send` w
`ConsumeContext` i wypuszcza je dopiero po pomyślnym zakończeniu `Consume`; przy wyjątku
bufor jest wyrzucany.

> 🧠 **Granice tej gwarancji - bądź uczciwy wobec siebie.** In-memory outbox chroni
> przed *duplikatem z retry w obrębie jednego procesu*. **Nie** chroni przed crashem
> procesu między zapisem do bazy a wysłaniem eventu - do tego służy transakcyjny outbox
> (bazodanowy, np. EF Core) zapisujący wiadomości w tej samej transakcji co dane. Tego dziś
> nie testowałem; zostawiam na osobny odcinek.

---

## 🧪 Szybka ściąga decyzyjna

| Objaw | Rozwiązanie |
|---|---|
| Deadlock, kolizja wersji, błąd znikający po ms | `Immediate(2-3)` |
| Chwilowa niedostępność API/bazy | `Exponential(...)` |
| Zależność leży minutami | `UseDelayedRedelivery` (+ krótki retry) |
| Błąd walidacji/danych - nigdy się nie naprawi | `Ignore<T>` i od razu `Fault` |
| Consumer publikuje eventy i może paść po nich | `UseInMemoryOutbox` (lub outbox z bazą) |
| Rosnące `_skipped` | audyt kontraktów i routingu |
| Rosnące `_error` | alert na `Fault<T>` + runbook odtwarzania |

---

## 🚧 Czego dziś NIE zweryfikowałem

- zachowania `_error`/`_skipped` na prawdziwym brokerze (RabbitMQ) - in-memory zachowuje
  się zgodnie z opisem, ale **kolejki nie są trwałe**;
- transakcyjnego outboxa z bazą danych;
- `UseCircuitBreaker`, `UseRateLimit` i sag z kompensacją - kolejne wydania.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) - dokładne komendy od zera. Cały demo trwa
ok. 10 sekund i kończy się sam.

---

<div align="center">

[← wróć do wydania #2 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
