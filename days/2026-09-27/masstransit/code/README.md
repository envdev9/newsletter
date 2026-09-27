# Kod do wydania #4 — MassTransit: routing (EndpointNameFormatter, Request/Response, filtry)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej fragment artykułu + jak odpalić kod.

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`). Jeśli SDK jest w `~/.dotnet`:
`export PATH="$HOME/.dotnet:$PATH"`. Nie potrzeba RabbitMQ ani Dockera (transport in-memory).

## Fragment prasówki, którego dotyczy ten kod

> Nazwy kolejek to kontrakt operacyjny. `KebabCaseEndpointNameFormatter("dev", false)` zamienia
> `PriceConsumer` na `dev-price`, ale `ConsumerDefinition` z jawnym `EndpointName` wygrywa z
> formatterem (i nie dostaje prefiksu). `IRequestClient<T>.GetResponse<A, B>` pozwala oczekiwać kilku
> typów odpowiedzi; wyjątek consumera wraca jako `RequestFaultException`, a brak consumera to
> `RequestTimeoutException`. Filtry (`IFilter<ConsumeContext<T>>`, `SendContext<T>`) owijają potok -
> ale `Publish` nie przechodzi przez filtr `Send`, a klient dostaje odpowiedź, zanim filtr consume
> skończy pracę.

## Struktura projektu

```
masstransit-routing-demo/
├── MassTransitRoutingDemo.csproj   # MassTransit 8.5.10 + Microsoft.Extensions.Hosting
├── Demo.cs                         # kontrakty, consumery, ConsumerDefinition, filtry
└── Program.cs                      # rejestracja + 5 scenariuszy
```

## Jak uruchomić

```bash
export PATH="$HOME/.dotnet:$PATH"
dotnet run --project days/2026-09-27/masstransit/code/masstransit-routing-demo
```

Demo trwa ok. 2 s i kończy się samo. Czasy `[xxx ms]` będą u Ciebie inne.

## Zweryfikowany output (prawdziwe uruchomienie)

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

Sprawdzone lokalnie na `.NET SDK 10`, MassTransit 8.5.10. Logi MassTransit wyciszone filtrem
`LogLevel.Critical` w `Program.cs`.

### Uwagi

- Niezweryfikowane: RabbitMQ (exchange, bindingi), `UsePublishFilter`, RoutingSlip/Courier, trwałe
  repozytoria sag.
- `.gitignore` w `code/` pomija `bin/` i `obj/`.
