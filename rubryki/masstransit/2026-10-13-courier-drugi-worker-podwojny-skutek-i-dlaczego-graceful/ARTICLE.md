<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #20 — 13 października 2026

![MassTransit](https://img.shields.io/badge/MassTransit-FF6600?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Wzorzec](https://img.shields.io/badge/wzorzec-redelivery%20%2B%20idempotencja%20%2B%20graceful%20shutdown-blueviolet?style=for-the-badge)

## 📨 Courier: drugi worker, podwójny skutek i dlaczego graceful shutdown jest tańszy niż idempotencja

</div>

---

> _"At-least-once to nie obietnica, że coś wykona się raz. To obietnica, że nie zginie. Resztę musisz dopisać sam."_

W #19 zostawiłem otwarte pytanie: slip czeka w kolejce po śmierci procesu - ale co się stanie,
gdy przyjdzie **drugi worker**? Wtedy sesja odrzuciła mi `kill -9` i kolejne uruchomienia.
Dziś dokończyłem pomiar. MassTransit **8.5.10** + MassTransit.RabbitMQ 8.5.10, RabbitMQ
`4.3-management` w Dockerze, .NET SDK 10.0.400, `dotnet build` 0 warnings / 0 errors.

**Uczciwie o metodzie:** `kill`/`kill -9` nadal było zablokowane przez uprawnienia sesji (nie
obchodziłem tego). Procesy zabijałem narzędziem do zatrzymywania zadań w tle - ono wysyła
SIGTERM (potwierdzone: w logu pojawia się `ApplicationStopping`), a proces znika zaraz potem
**bez** zakończenia pracy, więc w praktyce wyglądało to jak twarde zabicie. Dokładnego sygnału
końcowego i czasu łaski nie znam - nie twierdzę, że to było `kill -9`. Do osobnego, kontrolowanego
testu graceful shutdown użyłem `IHostApplicationLifetime.StopApplication()` (sekcja 4).

## 🎯 Dlaczego to ważne

Każdy tutorial mówi "co najmniej raz". Prawie nikt nie pokazuje, **jak wygląda drugie wykonanie**:
kto je widzi, po czym je poznać i co z tym zrobić. Dziś: dowód w logu, flaga `redelivered`,
działająca obrona i - zaskakujące - że zwykłe, poprawne zamknięcie hosta w ogóle nie robi duplikatu.

---

## 🧩 1. Slip po śmierci workera: co dokładnie czeka w kolejce

Worker 1 miał krok 2 (`AuthorizePayment`) spowolniony do 120 s (udawane wolne API płatności),
po skutku ubocznym. Gdy go zatrzymałem, `rabbitmqctl list_queues` pokazał
`authorize-payment_execute  messages_ready=1  consumers=0` (reszta kolejek 0). Tryb `peek` (REST API
`/get` z `ackmode=ack_requeue_true`, czyli podgląd bez konsumowania) wypisał treść slipa:

```
authorize-payment_execute: redelivered(broker)=True routing_key=
  itinerary:   AuthorizePayment, CreateShipment, NotifyCustomer
  pola slipa:  trackingNumber, createTimestamp, itinerary, activityLogs, compensateLogs, variables, activityExceptions, subscriptions
  activityLogs: ReserveInventory
  variables:    { "reservationId": "RES-ORD-A" }
```

Czyli: **slip niesie swój stan** - z itinerary zniknął krok 1 (zrobiony), w `activityLogs` jest jego
log kompensacji, zmienna `reservationId` jedzie dalej. Broker nie wie nic o tym, że krok 2 już
obciążył kartę. Dla niego to po prostu nieodebrana wiadomość.

## 💥 2. Drugi worker: dwa `EFFECT`

Uruchomiłem worker 2 (bez opóźnień). Fragment księgi skutków (plik, więc przeżywa procesy):

```
00:33:13.818 pid=199232 EXECUTE   AuthorizePayment redelivered=False track=e7b28557
00:33:13.818 pid=199232 EFFECT    AuthorizePayment key=...:AuthorizePayment
00:33:16.888 pid=199232 LIFETIME  ApplicationStopping (SIGTERM/SIGINT odebrany)
                                  <- worker 1 znika, brak COMPLETED
00:33:47.635 pid=199441 EXECUTE   AuthorizePayment redelivered=True track=e7b28557
00:33:47.637 pid=199441 EFFECT    AuthorizePayment key=...:AuthorizePayment   <- DRUGI skutek
00:33:47.638 pid=199441 COMPLETED AuthorizePayment krok potwierdzony
...
00:33:47.946 pid=199441 EVENT     RoutingSlipCompleted track=e7b28557
```

To jest cała lekcja w sześciu liniach: **ten sam `TrackingNumber`, dwa różne procesy, dwa skutki**,
a na końcu zdarzenie `RoutingSlipCompleted` - system zgłasza sukces i nikt nie wie o podwójnym
obciążeniu. `ExecuteContext.ReceiveContext.Redelivered` = `True` tylko dla kroku 2; kolejne kroki
(`CreateShipment`, `NotifyCustomer`) to świeże wiadomości, `redelivered=False`.

## 🛡️ 3. Idempotencja: klucz = `TrackingNumber:Aktywność`

Aktywność przed skutkiem sprawdza klucz. W demie to szukanie w pliku; w prawdziwym systemie klucz
przekazujesz dostawcy (nagłówek `Idempotency-Key`), bo to on musi odrzucić duplikat. Ten sam
scenariusz z flagą `idempotent` w workerze 2:

```
00:35:00.407 pid=199795 EXECUTE   AuthorizePayment redelivered=True track=29fe9eef
00:35:00.411 pid=199795 SKIP      AuthorizePayment skutek juz istnieje (klucz idempotentnosci)
00:35:00.411 pid=199795 COMPLETED AuthorizePayment krok potwierdzony
```

Krok został **potwierdzony bez powtórzenia skutku**, slip poszedł dalej do `Completed`.

> **Moja własna wpadka, zmierzona:** pierwsza wersja tego demka miała w trybie `idempotent` błąd -
> po zmianie formatu linii księgi wyszukiwany tekst `EFFECT key=` przestał pasować, więc
> "idempotentny" worker i tak wykonał skutek drugi raz (log: `redelivered=True` + drugi `EFFECT`
> mimo flagi). Czyli test idempotencji, który **nie jest uruchomiony na redelivery, nic nie
> dowodzi** - kod wyglądał poprawnie i się kompilował. Poprawiłem i przeszedłem scenariusz od nowa.

Ograniczenie, które widzisz w kodzie: "sprawdź, potem wykonaj, potem zapisz" nie jest atomowe.
Śmierć **między** skutkiem a zapisem klucza dalej daje duplikat. Prawdziwa idempotencja musi
mieć klucz po stronie wykonującego skutek.

## 🛑 4. Graceful shutdown: czy zamknięcie hosta w trakcie kroku robi duplikat?

Tu moje oczekiwanie było błędne. Worker z krokiem 2 trwającym 10 s, `StopApplication()` po
ok. 1,6 s od startu kroku (ta sama ścieżka, którą w hoście .NET uruchamia SIGTERM przez
`ConsoleLifetime`; samego prawdziwego SIGTERM z długą łaską **nie** testowałem):

```
00:36:17.270 pid=200143 EXECUTE   AuthorizePayment redelivered=False track=0328863e
00:36:17.270 pid=200143 EFFECT    AuthorizePayment key=...:AuthorizePayment
00:36:18.906 pid=200143 STOPAFTER StopApplication() po 10000 ms
00:36:18.907 pid=200143 LIFETIME  ApplicationStopping
00:36:27.272 pid=200143 COMPLETED AuthorizePayment krok potwierdzony   <- DOKOŃCZONY
00:36:27.333 pid=200143 WORKER    RunAsync zakonczony po 18.4 s od startu (graceful shutdown)
```

Wnioski zmierzone:

- **MassTransit przy zamknięciu hosta czeka na aktywność w toku**: `COMPLETED` pojawił się 8,4 s po
  `ApplicationStopping`, a `RunAsync` zwrócił dopiero potem. Linia `CANCELLED` (obsługa
  `context.CancellationToken`) **nie** wystąpiła - token nie został anulowany.
- **Zero duplikatu:** jeden `EFFECT` kroku 2 dla tego slipa. Następny krok został opublikowany
  i trafił do `create-shipment_execute` jako `messages_ready=1`, `consumers=0` - slip **zaparkowany**
  w kolejce (nikt już nie słuchał). Kolejny worker podjął go z `redelivered=False` i dokończył do
  `RoutingSlipCompleted`.
- Idle worker zamknął się w 0,2 s.

Kontrast jest ostry: **ta sama aktywność w toku, dwa sposoby zakończenia procesu - jeden kończy się
jednym skutkiem, drugi dwoma.** Graceful shutdown nie zastępuje idempotencji (awarie się zdarzają),
ale zmniejsza jej obciążenie do awarii, a nie do każdego deploya. W tym kontekście: jeśli twoje
wdrożenie ubija kontener po krótkim timeoucie (typowo 10-30 s w orkiestratorach), a krok trwa
dłużej niż ten timeout, to dostajesz duplikaty "z deploya", nie "z awarii" - sprawdź timeout
(`HostOptions.ShutdownTimeout`, ustawienia orkiestratora). *Tej zależności nie mierzyłem; to wniosek
z mechanizmu widocznego powyżej.*

---

## 🪤 Haczyki (zmierzone)

1. **`redelivered=True` jest tylko wskazówką.** Pokazuje, że broker już próbował dostarczyć -
   nie, że skutek się wykonał. Nie używaj go jako zamiennika klucza idempotentności, tylko do
   alarmowania/logowania.
2. **Sukces przy duplikacie.** `RoutingSlipCompleted` przy podwójnym skutku wygląda identycznie jak
   zwykły sukces. Nic w Courierze nie wykryje duplikatu za ciebie.
3. **Podgląd zmienia stan.** Sam `peek` (`ack_requeue_true`) zwraca wiadomość do kolejki, a broker
   oznacza ją jako `redelivered=True`. W naszym przypadku była już redelivered, ale podglądając
   kolejkę ze świeżą wiadomością "zepsujesz" jej flagę.
4. **Nie licz na anulowanie tokenu przy zamknięciu.** Aktywność w demie przekazuje
   `context.CancellationToken` do `Task.Delay`, a w teście graceful token nie został anulowany -
   krok dokończył się normalnie. Co się dzieje po przekroczeniu `ShutdownTimeout`, **nie**
   testowałem.
5. **Test idempotencji musi iść przez redelivery** (patrz wpadka w sekcji 3).

---

## 🚧 Niezweryfikowane

- Prawdziwe `kill -9` i prawdziwy SIGTERM z dłuższym okresem łaski: zablokowane przez uprawnienia
  sesji; użyłem zewnętrznego zatrzymania zadania (SIGTERM + brutalne zakończenie, ile dokładnie
  czasu - nieznane) i `StopApplication()`.
- Zachowanie po **przekroczeniu** `ShutdownTimeout` przy kroku w toku.
- Atomowość klucza idempotentności pod współbieżnością (dwa workery naraz) i śmierć w oknie
  "skutek - zapis klucza".
- `UseMessageRetry` + Courier, `ReviseItinerary`, trwałe repozytorium sag, `UseDelayedRedelivery`
  na brokerze.
- Brak testów `dotnet test`; wszystko to ręczne scenariusze, jeden przebieg każdego.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) - potrzebny .NET 10 SDK i Docker (RabbitMQ).

---

<div align="center">

[← wszystkie artykuły: 📨 Messaging .NET z MassTransit](../README.md) · [spis rubryk](../../../README.md)

</div>
