<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #26 — 19 października 2026

![MassTransit](https://img.shields.io/badge/MassTransit-FF6600?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Status](https://img.shields.io/badge/uruchomienie-ZWERYFIKOWANE-brightgreen?style=for-the-badge)

## 📨 Saga na PostgreSQL: dwa eventy, zero wyjątków i zgubiona aktualizacja

</div>

---

> **Uczciwie na wstępie.** Wszystko poniżej uruchomiłem naprawdę: MassTransit 8.5.10,
> .NET SDK 10.0.400, PostgreSQL 16 w Dockerze, `dotnet build` 0 warnings / 0 errors. Każdy
> scenariusz wykonałem **jeden raz** (wyścig jest niedeterministyczny). To domyka
> niewykonane scenariusze z wydania #21 (SQLite) - tym razem na bazie, która ma prawdziwe blokady wierszy.

## 🎯 Dlaczego to ważne

Wydanie #21 obiecało: stan sagi w tabeli, restart bez utraty zamówień. Prawda jest mniej
wygodna. Saga skonfigurowana „jak w tutorialu” (EF Core, `ISagaVersion`, tryb
optymistyczny) potrafi **po cichu zgubić aktualizację**: dwa eventy przychodzą naraz, oba
handlery kończą się sukcesem, w logu zero błędów, a w bazie licznik pokazuje, że
zastosowano 2 eventy zamiast 3. Żadnego `Fault`, żadnego alarmu. Poniżej dowód, przyczyna
(widoczna w SQL) i trzy sposoby naprawy z ich kosztami.

## 🧩 1. Zestaw doświadczalny

Saga `OrderState` z trzema eventami: `OrderSubmitted` (stan początkowy), potem
`PaymentReceived` i `ItemPacked` w stanie `Submitted`. Każdy handler „pracuje” 300 ms, żeby
dwa eventy realnie się nakładały, i zwiększa `EventsApplied` oraz dopisuje do `Trail`.
Poprawny wynik wyścigu to zawsze `eventsApplied=3` i w `trail` trzy wpisy.

Dwie praktyczne pułapki już na starcie:

- `Npgsql.EntityFrameworkCore.PostgreSQL` 9.0.4 **nie zbuduje się** z `MassTransit.EntityFrameworkCore`
  8.5.10: `NU1107`, bo ten ciągnie EF Core 10. Trzeba Npgsql EF 10.0.0.
- Dla trybu pesymistycznego trzeba dać dialekt: `r.LockStatementProvider = new PostgresLockStatementProvider()`.

## ✅ 2. Restart procesu: działa

Dwa osobne procesy, ta sama baza (transport in-memory, więc wiadomości nie są trwałe, trwały
jest stan):

```
$ dotnet MassTransitPgSagaDemo.dll submit 11111111-1111-1111-1111-111111111111
pid=572936 mode=submit concurrency=Optimistic retry=False
  11111111 state=Submitted version=0 paid=False packed=False eventsApplied=1 trail=Submitted;

$ dotnet MassTransitPgSagaDemo.dll pay 11111111-1111-1111-1111-111111111111
pid=572963 mode=pay concurrency=Optimistic retry=False
  11111111 state=Submitted version=0 paid=True packed=False eventsApplied=2 trail=Submitted;Paid;
```

Nowy proces (inny `pid`) podjął sagę z wiersza. Zwróć uwagę na `version=0` po dwóch
aktualizacjach - to jest trop.

## 🪤 3. Haczyk: optymistyczny tryb, który niczego nie pilnuje

```
race optimistic noretry
  4eb8ee07 state=Submitted version=0 paid=True packed=True eventsApplied=2 trail=Submitted;Paid;
race optimistic retry
  cc56d6de state=Submitted version=0 paid=True packed=True eventsApplied=2 trail=Submitted;Paid;
```

`paid=True` i `packed=True` - więc wygląda dobrze. Ale `eventsApplied=2` i w `trail` brak
`Packed;`. Retry też nic nie zmienia, bo nie ma czego ponawiać: nie poleciał żaden wyjątek.
Przyczynę widać po włączeniu logu SQL (argument `sql`):

```
UPDATE "OrderState" SET "EventsApplied" = @p0, "Packed" = @p1, "Trail" = @p2
WHERE "CorrelationId" = @p3 AND "Version" = @p4;
UPDATE "OrderState" SET "EventsApplied" = @p0, "Paid" = @p1, "Trail" = @p2
WHERE "CorrelationId" = @p3 AND "Version" = @p4;
```

Dwie rzeczy. Po pierwsze, `Version` nigdzie nie rośnie (w SET go nie ma), więc oba UPDATE-y
mają `WHERE Version = 0` i oba przechodzą. Po drugie, EF aktualizuje tylko zmienione kolumny:
`Paid` i `Packed` są rozłączne (obie lądują w bazie), ale `EventsApplied` i `Trail` pisze
każdy handler - ostatni wygrywa. To klasyczny lost update, tyle że ukryty za „poprawnymi”
flagami. W realnym systemie odpowiednikiem `EventsApplied` jest każde pole liczone z
poprzedniej wartości (suma, lista pozycji, status zbiorczy).

Wniosek: sama kolumna `int Version` z `IsConcurrencyToken()` **nie jest** mechanizmem
współbieżności, jeśli nikt jej nie podbija. W tym teście MassTransit tego nie zrobił (nie
sprawdzałem w źródłach, czy to zamierzone, ani czy ręczne `Version++` w sadze by pomogło).

## 🔧 4. Naprawa A: prawdziwy token - `xmin` z PostgreSQL

```csharp
entity.Property<uint>("xmin").IsRowVersion();   // kolumna systemowa, zmienia się przy każdym UPDATE
```

Bez retry teraz głośno (jeden event przepada, wynik poprawny dla zwycięzcy):

```
FAULT<ItemPacked>: Microsoft.EntityFrameworkCore.DbUpdateConcurrencyException ; The database operation was expected to affect 1 row(s), but actually affected 0 row(s)...
  3b74ed0d state=Submitted version=0 paid=True packed=False eventsApplied=2 trail=Submitted;Paid;
```

Z `UseMessageRetry(r => r.Immediate(5))` przegrany event czyta świeży stan i się domyka:

```
R-RETRY ... DbUpdateConcurrencyException
  2c1dc8fe state=Submitted version=0 paid=True packed=True eventsApplied=3 trail=Submitted;Packed;Paid;
```

Kolejność w `trail` jest odwrotna niż poprzednio - ten sam wyścig, inny zwycięzca. Jeśli
logika zależy od kolejności, optymistyczna współbieżność jej nie gwarantuje.

## 🔒 5. Naprawa B: tryb pesymistyczny - blokada jest, ale nie wszystko

SQL w trybie `Pessimistic` zawiera to, czego oczekujemy:

```
SELECT e."CorrelationId", ..., e."Version"
FROM (SELECT *, xmin FROM "OrderState" WHERE "CorrelationId" = @p0 FOR UPDATE) AS e
LIMIT 2
```

Ale z domyślnymi ustawieniami drugi event **nie czeka** na blokadę, tylko pada:

```
Npgsql.PostgresException: 40001: could not serialize access due to concurrent update
FAULT<ItemPacked>: System.InvalidOperationException ; An exception has been raised that is likely due to a transient failure.
  fec7f46b state=Submitted version=0 paid=True packed=False eventsApplied=2 trail=Submitted;Paid;
```

SQLSTATE 40001 to błąd serializacji. Wnioskuję (nie sprawdzałem w kodzie), że domyślny poziom
izolacji transakcji sagi jest wyższy niż `ReadCommitted`; potwierdza to eksperyment: po
`r.IsolationLevel = IsolationLevel.ReadCommitted` błąd znika i drugi event grzecznie czeka na
`FOR UPDATE`:

```
race pessimistic noretry readcommitted
  cf155cdf state=Submitted version=0 paid=True packed=True eventsApplied=3 trail=Submitted;Paid;Packed;
```

Bez retry, bez Fault, wynik poprawny. Z domyślną izolacją i `retry` też działa (jeden `R-RETRY`
na błąd 40001, `eventsApplied=3`), więc 40001 trzeba traktować jak błąd przejściowy, nie awarię.
Uwaga: błąd 40001 jest opakowany w `InvalidOperationException` ("likely due to a transient
failure"), więc filtr `r.Handle<...>()`/`Ignore<...>()` piszesz na ten typ, nie na `PostgresException`.

## 📊 Podsumowanie pomiarów (po jednym przebiegu)

| Konfiguracja | `eventsApplied` | Hałas |
|---|---|---|
| optimistic (Version int) | 2 - **zgubiony update** | brak |
| optimistic (Version int) + retry | 2 - **zgubiony update** | brak |
| optimistic + `xmin` | 2 (przegrany event w Fault) | `DbUpdateConcurrencyException` |
| optimistic + `xmin` + retry | 3 | jeden `R-RETRY` |
| pessimistic, domyślna izolacja | 2 (przegrany event w Fault) | SQLSTATE 40001 |
| pessimistic + retry | 3 | jeden `R-RETRY` |
| pessimistic + `ReadCommitted` | 3 | brak |

## 🚧 Czego NIE zweryfikowałem

- Czasu oczekiwania na blokadę przy `ReadCommitted` (nie mierzyłem) ani zachowania pod obciążeniem
  / wielu powtórzeń - to pojedyncze przebiegi, nie statystyka.
- Wyścigu z dwóch **procesów** (tu oba eventy konsumował jeden proces; przy kilku instancjach
  blokady/xmin powinny działać tak samo, ale tego nie uruchomiłem).
- Czy ręczne podbijanie `Version` w sadze naprawia tryb optymistyczny.
- Domyślnego poziomu izolacji (to wnioskowanie z błędu 40001 i działania `ReadCommitted`).
- `UseDelayedRedelivery`, sag na RabbitMQ, `ReviseItinerary`, brak testów `dotnet test`.

## ▶️ Następny krok

Kod: [`code/README.md`](code/README.md). Następny poziom: powtórzyć wyścig z dwóch procesów i
zmierzyć czas oczekiwania na blokadę; sprawdzić ręczne `Version++`; `UseDelayedRedelivery` na
brokerze; `UseMessageRetry` z Courierem.

---

<div align="center">

[← wróć do wydania #26 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
