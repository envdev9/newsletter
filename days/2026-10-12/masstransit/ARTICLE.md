<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #19 — 12 października 2026

![MassTransit](https://img.shields.io/badge/MassTransit-FF6600?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Wzorzec](https://img.shields.io/badge/wzorzec-Courier%20na%20RabbitMQ%20%2B%20awaria%20procesu-blueviolet?style=for-the-badge)

## 📨 Courier na RabbitMQ: co się dzieje ze slipem, gdy proces umiera w połowie kroku

</div>

---

> _"Routing slip nie żyje w twoim procesie. Żyje w brokerze. Pytanie brzmi: co twój proces zdąży zrobić, zanim umrze?"_

W #15 policzyliśmy kompensacje na czterech krokach, ale w pamięci (in-memory) i z
zastrzeżeniem, że "restart procesu w trakcie slipa" zostaje niezweryfikowany. Dziś przenoszę
ten sam czterokrokowy itinerary na **prawdziwy RabbitMQ** i zadaję pytanie o awarię.
MassTransit **8.5.10** + MassTransit.RabbitMQ 8.5.10, RabbitMQ `4.3-management`, .NET SDK 10.
**Uwaga o uczciwości:** ta sesja nie dobiegła do końca zaplanowanego scenariusza - część
eksperymentów została mi odrzucona przez system uprawnień (szczegóły w sekcji
"Niezweryfikowane"). Poniżej jest wyraźnie rozdzielone to, co zmierzyłem, od tego, co tylko
przygotowałem w kodzie.

## 🎯 Dlaczego to ważne

Courier wygląda jak "transakcja rozproszona", ale nią nie jest. Nie ma tu stanu trzymanego
przez koordynatora: **cały slip (itinerary, log wykonanych kroków, zmienne) jest treścią jednej
wiadomości**, która wędruje po kolejkach `*_execute`. Konsekwencje dla ciebie:

- nie potrzebujesz repozytorium sag ani bazy - brokerem jest stan,
- ale gwarancja to **co najmniej raz** (at-least-once): jeśli proces padnie po skutku ubocznym,
  a przed potwierdzeniem kroku, krok wykona się **drugi raz**.

Od dziś widzisz to na własne oczy, nie tylko w dokumentacji.

---

## 🧩 1. Ta sama aktywność, prawdziwy broker, ścieżka szczęśliwa

Cztery aktywności (`ReserveInventory -> AuthorizePayment -> CreateShipment -> NotifyCustomer`),
każda dopisuje wiersz do **księgi skutków ubocznych** (plik tekstowy - przeżyje zabicie
procesu) z `EFFECT`, a po `Task.Delay` w kroku 2 (udawane wolne wywołanie dostawcy płatności,
12 s) - `COMPLETED`. Proces wysyłający slip (`start`) to **osobny, krótki proces**: wysyła
i się kończy, nie ma konsumentów, więc nie podkrada pracy workerowi. Zmierzony output
(worker jest jeden, wszystko przeszło):

```
00:32:22.260 EXECUTE   ReserveInventory redelivered=False
00:32:22.262 EFFECT key=fbb23b77...:ReserveInventory
00:32:22.262 COMPLETED ReserveInventory krok potwierdzony
00:32:22.446 EXECUTE   AuthorizePayment redelivered=False
00:32:22.446 EFFECT key=fbb23b77...:AuthorizePayment
00:32:34.447 COMPLETED AuthorizePayment krok potwierdzony      <- 12 s pozniej
00:32:34.473 EXECUTE   CreateShipment   redelivered=False
...
00:32:34.487 COMPLETED NotifyCustomer   krok potwierdzony
00:32:34.535 EVENT     RoutingSlipCompleted track=fbb23b77...
```

(Zmiennej `ReservationId` z `CompletedWithVariables` w tym demie nie wypisywałem - nie
twierdzę nic ponad #15.) Subskrypcja zdarzeń (`RoutingSlipEvents.Completed | Faulted | CompensationFailed`) trafia
do kolejki `slip-events` jako zwykły `Send` po adresie.

## 💀 2. Awaria: proces ginie po skutku, przed potwierdzeniem

Drugi przebieg: worker z flagą `crash` i krokiem 2 trwającym 4 s. Po skutku ubocznym i
odczekaniu proces wywołuje `Environment.FailFast` - bez finalizerów, bez graceful shutdown,
połączenie TCP z brokerem po prostu znika (to najbliższe "kill -9", jakie mogłem zrobić -
właściwe `kill -9` zostało mi odrzucone przez uprawnienia sesji). Prawdziwy output:

```
00:33:02.174 EXECUTE   AuthorizePayment redelivered=False
00:33:02.175 EFFECT key=210c9836...:AuthorizePayment  <- skutek uboczny wykonany
00:33:06.176 CRASH     AuthorizePayment Environment.FailFast - proces ginie bez potwierdzenia
Process terminated.   (exit code 134)
```

Stan brokera zaraz po awarii (`rabbitmqctl list_queues`):

```
authorize-payment_execute    messages_ready=1  messages_unacknowledged=0  consumers=0
reserve-inventory_execute    0 0 0
create-shipment_execute      0 0 0
slip-events                  0 0 0
```

Czyli: **slip nie zginął**. Wiadomość z itinerary wróciła do kolejki kroku 2 (`ready=1`,
`consumers=0`), a kolejka kroku 1 jest pusta (0/0/0) - ale co dokładnie slip niesie w środku, nie podejrzałem.
Skutek uboczny kroku 2 (obciążenie) już się wydarzył, a broker o tym nie wie.

## 🪤 Haczyki (zmierzone)

1. **REST API kłamie zaraz po awarii.** Dwukrotnie wywołałem `inspect` (REST API management)
   po śmierci procesu i oba razy pokazał `consumers=1`, `ready=0` - nieaktualne statystyki
   (to ta sama ~6 s zwłoka z #5/#7). `rabbitmqctl list_queues` pokazał prawdę. Do dowodów po
   awarii używaj `rabbitmqctl`.
2. **Krótki `ExecutionId` w logu mylący:** pierwsze 8 znaków `ExecuteContext.ExecutionId`
   (`NewId`) jest z czasu - u mnie identyczne dla wszystkich kroków (`e1840000`). Pierwsza
   wersja demka tak logowała; w kodzie poprawiłem na ostatnie 12 znaków (różne dla kroków).
3. **Slip z awarią nie daje żadnego zdarzenia.** Nikt nie dostał `Faulted` - to nie jest
   wyjątek aktywności, tylko śmierć procesu. Jeśli ktoś czeka na zdarzenie końcowe, musi mieć
   własny timeout (patrz saga z `Schedule` w #3).

---

## 🚧 Niezweryfikowane (i dlaczego)

Kod w repo ma tryby, których **nie zdążyłem uruchomić**, bo kolejne uruchomienia workera
oraz zapytanie `curl` zostały odrzucone przez system uprawnień sesji (nie obchodziłem tego):

- **Ponowne dostarczenie po restarcie:** czy nowy worker dostanie krok 2 z
  `redelivered=True` i wykona `EFFECT` drugi raz (podwójne obciążenie). To jest hipoteza
  z semantyki at-least-once, nie pomiar. Czy `ExecuteContext.ReceiveContext.Redelivered`
  faktycznie jest `True` - kompiluje się, ale nie widziałem wartości.
- **Tryb `idempotent`** (sprawdzenie klucza `TrackingNumber:Aktywność` przed skutkiem):
  skompilowany, nieuruchomiony. W prawdziwym systemie klucz idempotentności przekazuje się
  dostawcy płatności, nie sprawdza w pliku.
- **Graceful shutdown w trakcie kroku** (SIGTERM): czy MassTransit dokończy aktywność i
  przekaże slip dalej, czy odda wiadomość - niezmierzone.
- Zawartość wiadomości slipa w kolejce (podgląd `ack_requeue_true`).
- Pozostałe z listy: `ReviseItinerary`, interakcja z `UseMessageRetry`, trwałe sagi.
- Brak testów `dotnet test`; `FailFast` to symulacja awarii, nie realne zabicie procesu.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) - potrzebny .NET 10 SDK i Docker (RabbitMQ).

---

<div align="center">

[← wróć do wydania #19 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
