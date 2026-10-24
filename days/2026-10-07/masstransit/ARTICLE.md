<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #14 — 7 października 2026

![MassTransit](https://img.shields.io/badge/MassTransit-FF6600?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Wzorzec](https://img.shields.io/badge/wzorzec-wiadomo%C5%9B%C4%87%20bez%20trasy-blueviolet?style=for-the-badge)

## 📨 Wiadomość bez trasy: `mandatory`, alternate-exchange i kosz, który nie liczy się w statystykach

</div>

---

> _"Wczoraj broker po cichu połykał wiadomości, których nikt nie chciał. Dziś uczymy go, żeby
> przynajmniej głośno o tym mówił - albo odkładał je do kosza."_

W #13 zmierzyliśmy haczyk: alert `info` bez pasującego wiązania znika bez śladu
(`publish_in=2`, `publish_out=1`), a `Publish` kończy się sukcesem. Zostawiłem wtedy otwarte
pytanie: czy da się to wykryć? Dziś odpowiedź, w dwóch wersjach: **po stronie klienta**
(flaga `mandatory`) i **po stronie brokera** (alternate-exchange). Wszystko na prawdziwym
RabbitMQ `4.3-management` w Dockerze, MassTransit **8.5.10** + `MassTransit.RabbitMQ` **8.5.10**,
.NET 10. Kod: [`code/`](code/). Każdy output poniżej to realny output uruchomionego kodu.

## 🎯 Dlaczego to ważne

Wiadomość bez trasy to najgorszy rodzaj błędu: żadnego wyjątku, żadnego logu, żadnej kolejki
`_error`. Literówka w kluczu routingu, konsument, który jeszcze nie wstał i nie utworzył
wiązania, wdrożenie ze zmienionym wzorcem - i zdarzenie biznesowe (alert, płatność) po prostu
przestaje istnieć. Tu nie chodzi o wydajność, tylko o **utratę danych bez śladu**.

| Mechanizm | Kto wykrywa | Co się dzieje z wiadomością | Koszt |
|---|---|---|---|
| (domyślnie) | nikt | znika | zero, i to jest problem |
| 🚩 `mandatory = true` | **nadawca** | broker zwraca ją; `Publish` rzuca wyjątek | jedna flaga per wiadomość |
| 🗑️ `alternate-exchange` | **broker** | trafia do kosza (zwykła kolejka) | argument exchange'a + kolejka z konsumentem |

---

## 🚩 1. Flaga `mandatory`: broker zwraca, `Publish` rzuca

W MassTransit flagę ustawia się na kontekście wysyłki RabbitMQ, w callbacku `Publish`:

```csharp
await bus.Publish(new Alert("info", "..."), ctx =>
{
    if (ctx.TryGetPayload<RabbitMqSendContext>(out var rmq))
        rmq.Mandatory = true;
});
```

Dwie publikacje tej samej wiadomości `Alert("info")` na exchange `direct`, który ma wiązanie
tylko dla `critical`. Prawdziwy output (tryb `mandatory`):

```
=== MANDATORY: Alert 'info' (bez wiązania), mandatory=true vs false ===
  mandatory=False payload RabbitMqSendContext=True  Publish zakonczony BEZ wyjatku po 877 ms
  mandatory=True  WYJATEK MessageReturnedException: The message was returned by RabbitMQ
    inner PublishReturnException: 312 NO_ROUTE Exchange: MassTransitUnrouted:Alert Routing Key: info
```

Bez flagi: cisza. Z flagą: `MessageReturnedException`, a w niej `PublishReturnException` z
kodem **312 NO_ROUTE**, nazwą exchange'a i kluczem. Dokładnie to, czego brakowało w #13.
(Czas 877 ms dotyczy pierwszej publikacji, która płaci za otwarcie kanału - nie jest to
koszt flagi; osobnego pomiaru narzutu `mandatory` nie robiłem.)

## 🗑️ 2. Alternate-exchange: broker odkłada wiadomość do kosza

`mandatory` wymaga, żeby **każdy nadawca** pamiętał o fladze. Alternate-exchange to
ustawienie **na exchange'u**: wiadomość, która nie ma trasy, jest przekierowana na inny
exchange. W MassTransit to argument exchange'a:

```csharp
cfg.Publish<Notice>(p =>
{
    p.ExchangeType = ExchangeType.Direct;
    p.SetExchangeArgument("alternate-exchange", "unrouted-ae");
});
// kosz: fanout + kolejka z konsumentem
cfg.ReceiveEndpoint("unrouted-sink", e =>
{
    e.ConfigureConsumeTopology = false;
    e.Bind("unrouted-ae", b => b.ExchangeType = ExchangeType.Fanout);
    e.ConfigureConsumer<UnroutedNoticeConsumer>(context);
});
```

Argument musi trafić też do `Bind<Notice>` po stronie konsumenta (`b.SetExchangeArgument(...)`),
bo każdy, kto deklaruje exchange, musi podać te same argumenty (patrz haczyk #3). Dwa typy,
identyczne wiązania `critical`; `Alert` bez AE, `Notice` z AE. Wysyłam po `critical` i `info`
(tryb `run`):

```
=== RUN: Alert (bez AE) i Notice (z alternate-exchange), po 'critical' i 'info' ===
  [notices-critical] Notice critical: certyfikat wygasa
  [alerts-critical ] Alert  critical: dysk pelny
  [unrouted-sink   ] Notice info: wdrozenie zakonczone  | oryginalny klucz routingu = 'info'
--- podsumowanie ---
  alerts-critical   1
  notices-critical  1
  unrouted-sink     1
```

`Alert info` zniknął jak wcześniej, `Notice info` wylądował w koszu. Bonus: konsument kosza
widzi **oryginalny klucz routingu** (`'info'`), odczytany z payloadu
`RabbitMqBasicConsumeContext.RoutingKey` (`context.TryGetPayload<...>`) - to zamyka drugie
pytanie otwarte z #13. W koszu masz więc wiadomość **i** informację, dokąd zmierzała.

## 🔍 3. Co widzi broker (REST API i `rabbitmqctl`)

```
--- exchange'e (typ, argumenty, publish_in/out) ---
  'MassTransitUnrouted:Alert'  typ=direct  args={}  publish_in=4  publish_out=1
  'MassTransitUnrouted:Notice'  typ=direct  args={"alternate-exchange":"unrouted-ae"}  publish_in=2  publish_out=2
  'unrouted-ae'  typ=fanout  args={}  publish_in=0  publish_out=0
--- wiazania ---
  MassTransitUnrouted:Alert  ->  alerts-critical (exchange)  routing_key='critical'
  MassTransitUnrouted:Notice  ->  notices-critical (exchange)  routing_key='critical'
  unrouted-ae  ->  unrouted-sink (exchange)  routing_key=''
```

`rabbitmqctl list_exchanges name type arguments` potwierdza argument:
`MassTransitUnrouted:Notice  direct  [{"alternate-exchange","unrouted-ae"}]`.
(`Alert publish_in=4` bo wcześniej poszły 2 publikacje z trybu `mandatory`, w tym jedna
zwrócona.)

## 🪤 4. Haczyk #1: kosz nie liczy się w statystykach exchange'a kosza

Metoda detekcji z #13 (`publish_in` > `publish_out`) **przestaje działać** na exchange'u z AE:
`Notice` ma `publish_in=2`, `publish_out=2`, bo przekierowanie do AE liczy się jako wyjście.
Zarazem sam `unrouted-ae` pokazuje `publish_in=0 / publish_out=0`, mimo że dostarczył
wiadomość do kolejki (powtórzyłem `inspect` po kilkunastu sekundach, wynik ten sam, więc to
nie opóźnienie REST API znane z #5). Wniosek: **kolejki kosza nie da się monitorować
licznikiem exchange'a**; monitoruj długość kolejki `unrouted-sink` i jej konsumenta.

## 🪤 5. Haczyk #2: `mandatory` + AE = zero zwrotów

Czy flaga `mandatory` zadziała, gdy exchange ma AE? Wiadomość `Notice info` z
`Mandatory = true` (tryb `mandatory-ae`):

```
=== MANDATORY-AE: Notice 'info' (brak wiazania, ale exchange ma AE), mandatory=true ===
  Publish zakonczony BEZ wyjatku
  [unrouted-sink   ] Notice info: mandatory + AE  | oryginalny klucz routingu = 'info'
```

Nie zadziałała: wiadomość uznana za **zroutowaną** (przez AE), więc broker niczego nie
zwraca. Reguła praktyczna: AE zastępuje `mandatory`, nie dopełnia go. Jeśli kosz trafi
na wiadomość, nadawca się o tym nie dowie - musi pilnować kosza ktoś inny.

## 💥 6. Haczyk #3: AE to argument exchange'a, a argumenty są niezmienne

Tak samo jak typ exchange'a w #13: drugi klient deklarujący `Notice` **bez** argumentu AE
(tryb `ae-conflict`):

```
=== AE-CONFLICT: publikacja Notice BEZ argumentu alternate-exchange na istniejacym exchange z AE ===
WYJATEK TaskCanceledException: A task was canceled.
```

Po stronie klienta znów tylko `TaskCanceledException` po moich 10 s. Przyczyna jest w
`docker logs`:

```
operation exchange.declare caused a channel exception precondition_failed: inequivalent arg 'alternate-exchange' for exchange 'MassTransitUnrouted:Notice' in vhost '/': received none but current is the value 'unrouted-ae' of type 'longstr'
```

Wniosek: dodanie AE do **istniejącego** exchange'a to migracja (usunięcie exchange'a albo
RabbitMQ policy), nie zmiana konfiguracji w kodzie. Jeden niezaktualizowany serwis wiesza
publikację.

---

## 🗺️ Ściąga

| Chcę... | Użyj |
|---|---|
| zobaczyć błąd w nadawcy | `ctx.TryGetPayload<RabbitMqSendContext>(out var r)` -> `r.Mandatory = true`; łap `MessageReturnedException` (inner `PublishReturnException`, 312 NO_ROUTE) |
| kosz niezależny od nadawcy | `p.SetExchangeArgument("alternate-exchange", "<nazwa>")` w `Publish<T>` **i** w `Bind<T>` |
| kolejka kosza | `ReceiveEndpoint` z `ConfigureConsumeTopology = false` + `e.Bind("<nazwa>", b => b.ExchangeType = Fanout)` |
| klucz routingu w konsumencie | `context.TryGetPayload<RabbitMqBasicConsumeContext>(out var c)` -> `c.RoutingKey` |
| monitoring | długość kolejki kosza, **nie** `publish_*` exchange'a AE |

---

## 🚧 Czego dziś NIE zweryfikowałem

- Narzutu `mandatory` (pomiaru wydajności nie robiłem) ani zachowania z potwierdzeniami
  publisher confirms w innej konfiguracji niż domyślna MassTransit.
- Zachowania `mandatory` przy `Send` (adresowanym) i przy `Publish` w ramach outboxa.
- Alternate-exchange ustawionego **policy** (`rabbitmqctl set_policy`) zamiast argumentem -
  powinno uniknąć konfliktu z haczyka #3, ale tego nie testowałem.
- Wpływu AE na wiadomość, której kosz też jej nie zroutuje (łańcuch AE).
- Exchange `headers`, klaster, TLS, `UseDelayedRedelivery` na brokerze, trwałe sagi - nadal przed nami.
- `docker-compose.yml` - nie dodałem pliku; `docker run` (patrz `code/README.md`). Brak testów
  `dotnet test`; weryfikacja to realne `dotnet run` przeciw brokerowi.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) - instrukcja od zera, ze sprzątaniem własnego kontenera.

---

<div align="center">

[← wróć do wydania #14 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
