<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #13 — 6 października 2026

![MassTransit](https://img.shields.io/badge/MassTransit-FF6600?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Wzorzec](https://img.shields.io/badge/wzorzec-topic%20%2F%20direct%20exchange-blueviolet?style=for-the-badge)

## 📨 Routing po kluczu na RabbitMQ: topic, direct i jedna cicha pułapka

</div>

---

> _"Fanout mówi: wszyscy dostają wszystko. Topic mówi: dostajesz to, co pasuje do Twojego wzorca -
> a co nie pasuje nikomu, znika bez słowa."_

Od wydania #5 każdy nasz exchange na RabbitMQ był **fanout**: MassTransit publikuje typ
wiadomości, a każda związana kolejka dostaje kopię. Dziś pierwszy raz sięgamy po **routing po
kluczu**: exchange typu `topic` (wzorce `*` i `#`) oraz `direct` (dokładne dopasowanie).
Wszystko na prawdziwym brokerze, MassTransit **8.5.10** + `MassTransit.RabbitMQ` **8.5.10**,
RabbitMQ `4.3-management` w Dockerze, .NET 10. Kod: [`code/`](code/). Każdy output poniżej to
realny output komend, które uruchomiłem.

## 🎯 Dlaczego to ważne

Fanout skaluje się źle w jednym wymiarze: gdy konsument chce tylko "temperatury z dowolnego
regionu" albo "alerty krytyczne", przy fanoucie musiałby odebrać **wszystko** i odrzucać w kodzie.
Routing po kluczu przenosi filtrowanie **na broker** - zanim wiadomość trafi do kolejki, więc
nie płacisz za transfer, deserializację ani ACK wiadomości, których i tak nie chcesz.

| Pojęcie | Co robi | W naszym demie |
|---|---|---|
| 🔀 `cfg.Publish<T>(p => p.ExchangeType = ExchangeType.Topic)` | exchange wiadomości staje się topic | `SensorReading` |
| 🏷️ `cfg.Send<T>(s => s.UseRoutingKeyFormatter(...))` | klucz routingu liczony z treści wiadomości | `"{Region}.{Kind}"`, np. `eu.temp` |
| 🔗 `e.ConfigureConsumeTopology = false` + `e.Bind<T>(b => b.RoutingKey = ...)` | ręczne wiązanie kolejki z własnym wzorcem | `eu.#`, `*.temp`, `#` |
| 🎯 `ExchangeType.Direct` | dokładne dopasowanie klucza | `Alert` -> `critical` |
| 🕳️ brak pasującego wiązania | wiadomość **znika po cichu** | alert `info` |

---

## 🔀 1. Strona publikująca: typ exchange'a i klucz routingu

```csharp
cfg.Publish<SensorReading>(p => p.ExchangeType = ExchangeType.Topic);
cfg.Send<SensorReading>(s => s.UseRoutingKeyFormatter(ctx => $"{ctx.Message.Region}.{ctx.Message.Kind}"));
```

Dwie osobne decyzje: **jakiego typu** ma być exchange (`Publish<T>`) i **jaki klucz** dostaje
konkretna wiadomość (`Send<T>` + formatter). Kod publikujący pozostaje zwykłym
`bus.Publish(new SensorReading("eu", "temp", 21.5))` - routing jest konfiguracją, nie logiką
w miejscu wywołania.

## 🔗 2. Strona konsumująca: własne wiązanie zamiast domyślnego

```csharp
cfg.ReceiveEndpoint("sensors-eu", e =>
{
    e.ConfigureConsumeTopology = false;   // wyłącz domyślne wiązanie (bez klucza)
    e.Bind<SensorReading>(b => { b.ExchangeType = ExchangeType.Topic; b.RoutingKey = "eu.#"; });
    e.ConfigureConsumer<EuConsumer>(context);
});
```

Trzy kolejki z różnymi wzorcami: `eu.#` (wszystko z `eu`), `*.temp` (temperatura skądkolwiek),
`#` (audyt - wszystko). W topic `*` to dokładnie jedno słowo, `#` - zero lub więcej.
Opublikowałem 4 odczyty i 2 alerty. Prawdziwy output:

```
=== RUN: 4 odczyty (topic) + 2 alerty (direct) ===
publish SensorReading routing key = eu.temp
publish SensorReading routing key = eu.humidity
  [temp-anywhere  ] dostał eu.temp=21.5
  [audit          ] dostał eu.temp=21.5
  [eu-all         ] dostał eu.temp=21.5
publish SensorReading routing key = us.temp
  [audit          ] dostał eu.humidity=60
publish SensorReading routing key = asia.pressure
  [eu-all         ] dostał eu.humidity=60
publish Alert routing key = critical
  [temp-anywhere  ] dostał us.temp=30
  [audit          ] dostał us.temp=30
  [audit          ] dostał asia.pressure=1013
  [alerts-critical] dostał critical: dysk pełny
publish Alert routing key = info   (nikt nie ma wiązania 'info')
--- podsumowanie: kto ile dostał ---
  eu-all           2
  temp-anywhere    2
  audit            4
  naive-default    0
  alerts-critical  1
```

Zgadza się z wzorcami: `eu.temp` trafia do trzech kolejek, `asia.pressure` tylko do audytu.
Kolejność linii między konsumentami nie jest gwarantowana (różne kolejki, różne wątki).

## 🔍 3. Co broker faktycznie ma - dowód z REST API

```
--- exchange'e wiadomości (MassTransitTopicRouting) ---
  'MassTransitTopicRouting:Alert'  typ=direct  publish_in=2  publish_out=1
  'MassTransitTopicRouting:SensorReading'  typ=topic  publish_in=4  publish_out=8
--- wiązania exchange -> (exchange|kolejka), routing_key ---
  MassTransitTopicRouting:Alert  ->  alerts-critical (exchange)  routing_key='critical'
  MassTransitTopicRouting:SensorReading  ->  sensors-audit (exchange)  routing_key='#'
  MassTransitTopicRouting:SensorReading  ->  sensors-eu (exchange)  routing_key='eu.#'
  MassTransitTopicRouting:SensorReading  ->  sensors-naive (exchange)  routing_key=''
  MassTransitTopicRouting:SensorReading  ->  sensors-temp (exchange)  routing_key='*.temp'
```

Liczby się sumują: 4 publikacje, **8** kopii wyjściowych = 2 (eu) + 2 (temp) + 4 (audit) + 0
(naive). Potwierdziłem `rabbitmqctl list_exchanges`: oba exchange'e wiadomości mają typy `topic`
i `direct`, a **exchange'e kolejek** (`sensors-eu` itd.) nadal są `fanout` - wzorzec jest
dopasowywany tylko na pierwszym skoku (wiadomość -> exchange kolejki), tak jak w #5, gdzie
każda kolejka ma własny exchange o tej samej nazwie. Statystyki REST API mają opóźnienie
(ok. 6 s, znane z #5), więc `inspect` odpaliłem po ok. 8 s.

## 🪤 4. Haczyk #1: konsument "naiwny" nie dostaje nic

`sensors-naive` zostawiłem na domyślnej topologii. MassTransit związał go z exchange'em
`SensorReading` z kluczem **pustym** (`routing_key=''`, widać w wiązaniach wyżej). Na
exchange'u topic pusty klucz nie pasuje do `eu.temp`, więc: `naive-default 0` z 4 wiadomości.
Brak błędu, brak ostrzeżenia, kolejka istnieje i konsument jest zdrowy - po prostu cisza. Po
przejściu na topic **każdy** konsument tego typu musi dostać jawne `Bind` z kluczem.

## 🕳️ 5. Haczyk #2: wiadomość bez pasującego wiązania znika po cichu

Alert `info` nie ma żadnego wiązania. Dowód w statystykach exchange'a: `publish_in=2`,
`publish_out=1` - jedna wiadomość weszła i nie wyszła nigdzie. Żadnego `_skipped`, żadnego
`_error`, `Publish` zakończył się sukcesem. Zmierzone dla MassTransit 8.5.10 z domyślnymi
ustawieniami publikacji. Czy da się to wykryć po stronie klienta (flaga `mandatory`/return) -
**nie sprawdzałem**.

## 💥 6. Haczyk #3: zmiana typu exchange'a na istniejącym brokerze

Exchange'u nie da się zadeklarować ponownie z innym typem. Drugi klient bez
`cfg.Publish<SensorReading>(... Topic)` (domyślnie fanout) próbuje zadeklarować go jako fanout:

```
=== CONFLICT: publikacja SensorReading BEZ cfg.Publish<T>(ExchangeType.Topic) na brokerze, gdzie exchange jest topic ===
WYJĄTEK TaskCanceledException: A task was canceled.
```

Po stronie klienta zobaczyłem **tylko** `TaskCanceledException` (mój 10-sekundowy token) -
publikacja po prostu wisi. Prawdziwa przyczyna jest w logu brokera (`docker logs`):

```
operation exchange.declare caused a channel exception precondition_failed: inequivalent arg 'type' for exchange 'MassTransitTopicRouting:SensorReading' in vhost '/': received 'fanout' but current is 'topic'
```

Broker logował to wielokrotnie (ponowne próby klienta w ciągu tych 10 s). Wniosek: zmiana
typu istniejącego exchange'a to migracja (usunąć exchange / nowa nazwa), nie zmiana
konfiguracji. I: gdy publikacja "wisi", zajrzyj do logu brokera.

---

## 🗺️ Ściąga

| Chcę... | Użyj |
|---|---|
| exchange topic dla typu | `cfg.Publish<T>(p => p.ExchangeType = ExchangeType.Topic)` |
| klucz z treści wiadomości | `cfg.Send<T>(s => s.UseRoutingKeyFormatter(ctx => ...))` |
| własny wzorzec dla kolejki | `e.ConfigureConsumeTopology = false` + `e.Bind<T>(b => b.RoutingKey = "...")` |
| dokładne dopasowanie | `ExchangeType.Direct` zarówno w `Publish<T>`, jak i w `Bind<T>` |
| sprawdzić, czy coś ginie | REST API: `publish_in` vs `publish_out` exchange'a |

---

## 🚧 Czego dziś NIE zweryfikowałem

- Flagi `mandatory`/publisher returns - czy MassTransit potrafi zgłosić wiadomość bez trasy.
- Konsumenta czytającego klucz routingu z kontekstu (nie sprawdzałem).
- Exchange typu `headers`, klaster, TLS/AMQPS.
- `UseDelayedRedelivery` na RabbitMQ i trwałe repozytorium sag - nadal przed nami.
- `docker-compose.yml` - nie dodałem pliku; użyłem `docker run` (patrz `code/README.md`).
- Zachowania pod dużym wolumenem; testów jednostkowych (`dotnet test`) nie było - weryfikacja
  to realne `dotnet run` przeciw brokerowi.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) - instrukcja od zera, ze sprzątaniem własnego kontenera.

---

<div align="center">

[← wróć do wydania #13 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
