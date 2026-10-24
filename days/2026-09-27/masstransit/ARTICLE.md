<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #4 — 27 września 2026

![MassTransit](https://img.shields.io/badge/MassTransit-FF6600?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Transport](https://img.shields.io/badge/transport-in--memory-blue?style=for-the-badge)

## 📨 Routing: nazwy kolejek, Request/Response i filtry - kto, dokąd i przez co

</div>

---

> _"Wiadomość ma adres. Jeśli nie wiesz, jaki - wiadomość też nie wie."_

Do tej pory MassTransit "po prostu działał": `ConfigureEndpoints` stawiał kolejki, a my
publikowaliśmy. Dziś zaglądamy pod maskę **routingu**: jak powstają nazwy kolejek, jak zrobić
**pytanie-odpowiedź** (Request/Response) na komunikatach, i jak wpiąć **filtry** (middleware) w
potok wysyłania i konsumowania. Kod: [`code/`](code/), transport in-memory (bez RabbitMQ i Dockera),
output prawdziwy (MassTransit **8.5.10**, .NET 10).

## 🎯 Dlaczego to ważne

Na produkcyjnym brokerze nazwy kolejek to **kontrakt operacyjny**: po nich monitorujesz, ustawiasz
alerty, kierujesz ruch i - co gorsza - zmiana nazwy klasy consumera potrafi po cichu utworzyć nową
kolejkę, a starą z nieprzetworzonymi wiadomościami zostawić na pastwę losu. Kto kontroluje nazwy,
kontroluje deploy.

| Pojęcie | Co robi | W naszym demie |
|---|---|---|
| 🏷️ **`EndpointNameFormatter`** | reguła zamiany nazwy consumera na nazwę kolejki | kebab-case + prefiks `dev` |
| 🧩 **`ConsumerDefinition`** | nadpisuje nazwę kolejki i ustawia parametry endpointu | `pings-special`, limit współbieżności 1 |
| 🔌 **`ConfigureEndpoints`** | tworzy kolejkę na każdy consumer wg powyższych reguł | jedno wywołanie na busie |
| 🙋 **`IRequestClient<T>`** | wyślij i poczekaj na odpowiedź, z timeoutem | `GetPrice` -> `PriceResult` |
| 🧱 **Filtry** (`IFilter<T>`) | middleware wokół consume/send/publish | pomiar czasu, nagłówek `x-trace` |

---

## 🏷️ 1. Skąd się biorą nazwy kolejek

Domyślnie nazwa = nazwa klasy consumera bez sufiksu `Consumer`. Zmieniamy to jedną linią:

```csharp
x.SetEndpointNameFormatter(new KebabCaseEndpointNameFormatter("dev", includeNamespace: false));
x.AddConsumer<PriceConsumer>();
x.AddConsumer<PingConsumer, PingConsumerDefinition>();
```

Formatter (wywołany wprost, żeby zobaczyć wynik) i to, co realnie zrobiła kolejka:

```
formatter dla PriceConsumer -> dev-price
formatter dla PingConsumer  -> dev-ping (ale definicja nadpisuje nazwę)
PriceConsumer: kolejka wejściowa = /dev-price
PingConsumer: 'cześć', ..., kolejka = /pings-special
```

`PriceConsumer` trafił do `dev-price`. Natomiast `PingConsumerDefinition` ustawia
`EndpointName = "pings-special"` i **ta nazwa wygrywa nad formatterem** - łącznie z pominięciem
prefiksu `dev`. To ważne przy prefiksach środowiskowych: jawna nazwa w definicji **nie dostaje
prefiksu** (na in-memory to widać wprost; zachowanie na RabbitMQ nie było testowane).

```csharp
public class PingConsumerDefinition : ConsumerDefinition<PingConsumer>
{
    public PingConsumerDefinition()
    {
        EndpointName = "pings-special";
        ConcurrentMessageLimit = 1;     // tylko jedna wiadomość naraz na tej kolejce
    }
}
```

Tak powstałą kolejkę można adresować bezpośrednio: `new Uri("queue:pings-special")` (sekcja 4).

## 🙋 2. Request/Response - pytanie z odpowiedzią

`IRequestClient<T>` publikuje request, a consumer odpowiada `context.RespondAsync(...)`. Klient
może oczekiwać **jednego z kilku typów** odpowiedzi - bez wyjątków do sterowania przepływem:

```csharp
var (ok, notFound) = await client.GetResponse<PriceResult, SkuNotFound>(new GetPrice(sku));
if (ok.IsCompletedSuccessfully) ... else ...
```

Prawdziwy output dla `ABC-1` (jest w cenniku) i `NOPE` (nie ma):

```
[  604 ms] PriceConsumer: kolejka wejściowa = /dev-price
[  676 ms] odpowiedź: ABC-1 kosztuje 42.50 zł
[  679 ms] PriceConsumer: kolejka wejściowa = /dev-price
[  691 ms] odpowiedź: SkuNotFound NOPE
```

Pierwsze żądanie trwa ~70 ms - to rozruch (JIT, tworzenie odbiornika odpowiedzi); drugie ~12 ms.

### Gdy consumer się wywali

```
klient złapał RequestFaultException: baza cen niedostępna
```

Wyjątek z consumera wraca do klienta jako `RequestFaultException` z oryginalnym komunikatem w
`ex.Fault.Exceptions` - klient nie wisi do timeoutu.

### Gdy nikt nie słucha

`GetStock` nie ma consumera. Klient z `RequestTimeout.After(s: 1)`:

```
[ 1904 ms] klient złapał RequestTimeoutException
```

Czas: ~1 s od poprzedniego kroku (~0,7 s -> ~1,9 s) - dokładnie timeout. **Wniosek:** Request/Response
bez consumera to nie błąd routingu, tylko cisza i timeout, więc timeout ustawiaj świadomie.

## 🧱 3. Filtry - middleware wokół wiadomości

Filtr to `IFilter<ConsumeContext<T>>` (lub `SendContext<T>`, `PublishContext<T>`). Dwa z dema:

```csharp
public class TimingConsumeFilter<T> : IFilter<ConsumeContext<T>> where T : class
{
    public async Task Send(ConsumeContext<T> context, IPipe<ConsumeContext<T>> next)
    {
        Log.Line($"filtr(consume) PRZED {typeof(T).Name}");
        var sw = Stopwatch.StartNew();
        try { await next.Send(context); }
        finally { Log.Line($"filtr(consume) PO {typeof(T).Name}, {sw.ElapsedMilliseconds} ms"); }
    }
    public void Probe(ProbeContext context) => context.CreateFilterScope("timing");
}
```

Rejestracja: filtry generyczne trzeba dodać do DI jako open generic
(`AddScoped(typeof(TimingConsumeFilter<>))`), a na busie:
`cfg.UseConsumeFilter(typeof(TimingConsumeFilter<>), context)` oraz analogicznie `UseSendFilter`.
Zobacz "PRZED"/"PO" wokół consumera w outpucie powyżej: filtr owija cały `Consume`, także gdy ten
rzuca wyjątek (`finally`) - w sekcji 3 widać `PO GetPrice, 152 ms` mimo faultu.

> ⚠️ **Pułapka 1: `Publish` nie przechodzi przez filtr `Send`.** Filtr `TraceSendFilter` dokleja
> nagłówek `x-trace`. Efekt:
>
> ```
> PingConsumer: 'cześć', ...                     nagłówek trace = (brak)       <- bus.Publish
> PingConsumer: 'prosto do pings-special', ...   nagłówek trace = trace-Ping   <- endpoint.Send
> ```
>
> Wiadomość opublikowana **nie dostała nagłówka**, wysłana przez `Send` - dostała. Filtry
> `Send` i `Publish` to osobne potoki (`UseSendFilter` vs `UsePublishFilter`); jeśli chcesz
> korelacji dla obu, zarejestruj oba. (Wersji z `UsePublishFilter` nie uruchamiałem w tym demie.)

> ⚠️ **Pułapka 2: klient dostaje odpowiedź, zanim filtr consume skończy.**
> W scenariuszu `NOPE` odpowiedź dotarła do klienta (`691 ms`) **zanim** filtr zalogował `PO`
> (`693 ms` - wydruk wylądował już pod nagłówkiem następnej sekcji). Odpowiedź jest wysyłana wewnątrz
> `Consume`, więc klient rusza dalej, gdy consumer jeszcze się "domyka". Nie zakładaj, że po
> `await GetResponse` filtr consume skończył pracę.

## 📮 4. Send po adresie

```csharp
var ep = await bus.GetSendEndpoint(new Uri("queue:pings-special"));
await ep.Send(new Ping("prosto do pings-special"));
```

`Send` = punkt-punkt do nazwanej kolejki (w przeciwieństwie do `Publish` - fan-out do wszystkich
subskrybentów, wydanie #1). Zadziałało, bo kolejka istnieje dzięki `ConfigureEndpoints` +
`ConsumerDefinition`.

## 🧪 Pełny zweryfikowany output

```
=== 1. Nazwy kolejek wg EndpointNameFormatter / ConsumerDefinition ===
[    0 ms] formatter dla PriceConsumer -> dev-price
[    0 ms] formatter dla PingConsumer  -> dev-ping (ale definicja nadpisuje nazwę)
[  258 ms]   filtr(consume) PRZED Ping
[  282 ms] PingConsumer: 'cześć', kolejka = /pings-special, nagłówek trace = (brak)
[  286 ms]   filtr(consume) PO Ping, 27 ms

=== 2. Request/Response: dwa typy odpowiedzi (Response<A, B>) ===
[  601 ms]   filtr(consume) PRZED GetPrice
[  604 ms] PriceConsumer: kolejka wejściowa = /dev-price
[  653 ms]   filtr(consume) PO GetPrice, 51 ms
[  676 ms] odpowiedź: ABC-1 kosztuje 42.50 zł
[  678 ms]   filtr(consume) PRZED GetPrice
[  679 ms] PriceConsumer: kolejka wejściowa = /dev-price
[  691 ms] odpowiedź: SkuNotFound NOPE

=== 3. Wyjątek w konsumencie propaguje się do klienta ===
[  693 ms]   filtr(consume) PO GetPrice, 14 ms
[  703 ms]   filtr(consume) PRZED GetPrice
[  704 ms] PriceConsumer: kolejka wejściowa = /dev-price
[  856 ms]   filtr(consume) PO GetPrice, 152 ms
[  874 ms] klient złapał RequestFaultException: baza cen niedostępna

=== 4. Brak konsumenta: RequestTimeoutException ===
[ 1904 ms] klient złapał RequestTimeoutException

=== 5. Send po adresie: kolejka pod nazwą z ConsumerDefinition; filtr Send widzi wiadomość ===
[ 1916 ms]   filtr(consume) PRZED Ping
[ 1917 ms] PingConsumer: 'prosto do pings-special', kolejka = /pings-special, nagłówek trace = trace-Ping
[ 1918 ms]   filtr(consume) PO Ping, 1 ms

Koniec.
```

## 🗺️ Ściąga

| Chcę... | Użyj |
|---|---|
| jednolitych nazw kolejek per środowisko | `SetEndpointNameFormatter(new KebabCaseEndpointNameFormatter("prefiks", false))` |
| stałej, jawnej nazwy / limitu współbieżności | `ConsumerDefinition` (`EndpointName`, `ConcurrentMessageLimit`) |
| wysłać punkt-punkt | `GetSendEndpoint(new Uri("queue:nazwa"))` + `Send` |
| zapytać i poczekać | `IRequestClient<T>.GetResponse<A, B>` + timeout |
| przekrojowej logiki (trace, metryki) | filtr `IFilter<...>` + `UseConsumeFilter`/`UseSendFilter` |

---

## 🚧 Czego dziś NIE zweryfikowałem

- **RabbitMQ**: exchange'e, bindingi, topologia (`ConfigureConsumeTopology`, exchange per typ) - demo
  działa na in-memory; nie sprawdzałem, czy prefiks/nazwa z definicji zachowują się tak samo na brokerze;
- filtra `Publish` (`UsePublishFilter`) i kolejności wielu filtrów;
- `RoutingSlip`/Courier, trwałych repozytoriów sag - zostają na kolejne wydania;
- czy odpowiedzi Request/Response przechodzą przez filtr `Send` (w logu nie sprawdzałem);
- wpływu `ConcurrentMessageLimit = 1` (ustawiony, nie mierzony).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Demo trwa ok. 2 sekundy i kończy się samo.

---

<div align="center">

[← wróć do wydania #4 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
