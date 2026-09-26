<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #3 — 26 września 2026

![.NET Aspire](https://img.shields.io/badge/.NET_Aspire-512BD4?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-średnio_zaawansowany-orange?style=for-the-badge)

## Dwa serwisy, zero adresów: `WithReference`, `WaitFor` i telemetria, którą napisałeś sam

</div>

---

> _"`WaitFor` nie czeka, aż proces wstanie. Czeka, aż serwis powie, że jest gotowy.
> To dwie zupełnie różne rzeczy — i pierwsza z nich to źródło połowy lokalnych 'flaky startów'."_

W [wydaniu #1](../../2026-09-24/aspire/ARTICLE.md) mieliśmy jeden zasób. Dziś robi się
prawdziwie **rozproszenie**: `CatalogApi` (katalog produktów) i `StoreApi` (wycena
zamówienia, która woła katalog). Do tego wspólny projekt `ServiceDefaults` z health
checkami i OpenTelemetry oraz **własny** `ActivitySource` i `Meter`. Całość
zweryfikowana bez `curl` i bez przeglądarki: jedno polecenie `dotnet run` podnosi cały
AppHost w procesie testowym i sprawdza wszystko `HttpClient`em. Wersje:
`.NET SDK 10.0.400`, `Aspire 13.5.2`. Kod: [`code/`](code/).

---

### Problem: skąd `StoreApi` wie, gdzie jest `CatalogApi`?

Aspire przydziela porty **dynamicznie** — za każdym uruchomieniem inne. Więc
`http://localhost:5301` w `appsettings.json` odpada. Klasyczne obejścia (stałe porty,
ręczne kopiowanie URL-i) to dokładnie to, przed czym Aspire miał chronić.

Rozwiązanie to dwie linijki w AppHost:

```csharp
var catalog = builder.AddProject<Projects.CatalogApi>("catalog")
    .WithHttpHealthCheck("/health");

builder.AddProject<Projects.StoreApi>("store")
    .WithReference(catalog)
    .WaitFor(catalog);
```

### `WithReference` — adres jako konfiguracja

`WithReference(catalog)` wstrzykuje do procesu `store` zmienną środowiskową
`services__catalog__http__0=http://localhost:<port>`. To zwykła konfiguracja .NET
(`services:catalog:http:0`) — endpoint `/discovery` w `StoreApi` wypisuje ją wprost.
Prawdziwy wynik z uruchomienia:

```
GET store /discovery -> {"catalogHttp":"http://localhost:46155","catalogHttps":null,"otlpEndpoint":true,"serviceName":"store"}
```

Zauważ też `otlpEndpoint: true` i `serviceName: "store"` — Aspire dorzuca
`OTEL_EXPORTER_OTLP_ENDPOINT` i `OTEL_SERVICE_NAME` sam, bez Twojego udziału.

Po stronie kodu `StoreApi` nie ma żadnego portu:

```csharp
builder.Services.AddHttpClient<CatalogClient>(c => c.BaseAddress = new Uri("http://catalog"));
```

`http://catalog` to **nie DNS**. To nazwa zasobu z AppHost, a rozwiązuje ją handler
z `AddServiceDiscovery()` (włączony globalnie przez `ConfigureHttpClientDefaults` w
`ServiceDefaults`). Log `store` z realnego przebiegu pokazuje to podmienienie:

```
Start processing HTTP request GET http://catalog/products/KB-001
Sending HTTP request GET http://localhost:35483/products/KB-001
```

Ten sam kod, bez zmian, zadziała potem w środowisku, gdzie `catalog` to inny host —
zmienia się tylko to, kto dostarcza konfigurację `services:catalog:*`.

### `WaitFor` — zdrowy, nie tylko uruchomiony

Tu jest haczyk. `WaitFor(catalog)` czeka na stan zasobu. Ale co znaczy "gotowy"?

- **Bez health checku** — proces wystartował (`Running`). Kestrel może jeszcze
  nie nasłuchiwać, cache nie jest rozgrzany, migracje się nie skończyły.
- **Z `WithHttpHealthCheck("/health")`** — zasób jest `Healthy` dopiero, gdy
  `GET /health` zwróci 200.

Żeby to było widać gołym okiem, `CatalogApi` ma wstawioną 3-sekundową "rozgrzewkę":
własny `IHealthCheck` zwraca `Unhealthy("warming up")`, dopóki `BackgroundService` nie
ustawi flagi:

```csharp
builder.Services.AddSingleton<WarmupState>();
builder.Services.AddHostedService<WarmupService>();      // Task.Delay(3s) -> Ready = true
builder.Services.AddHealthChecks().AddCheck<WarmupHealthCheck>("warmup");
```

Prawdziwy log — Aspire odpytuje `/health` i dostaje 503, dopóki katalog się nie rozgrzeje:

```
Health check catalog_http_/health_200_check with status Unhealthy ... 'Request to http://localhost:46155/health returned 503 ServiceUnavailable'
```

Dopiero po pierwszym 200 zasób `store` przechodzi z "czekam" do startu procesu. W logach
z pierwszego, nieprzyciętego przebiegu widać to w kolejności: `catalog` odpowiada
`/health - 200`, a *dopiero potem* pojawia się `[sys] Starting process...` dla `store`.
Test dodatkowo pilnuje warunku `catalog healthy >= 3 s`.

> **Uwaga o `/health` i `/alive`:** `ServiceDefaults` mapuje dwa endpointy.
> `/health` wymaga *wszystkich* checków (gotowość — to on blokuje `WaitFor`),
> `/alive` tylko tych z tagiem `live` (żywotność). Rozdzielenie ma sens:
> rozgrzewający się serwis jest **żywy**, ale jeszcze **niegotowy**. Mapowane są
> tylko w `Development` — na produkcji to decyzja z konsekwencjami bezpieczeństwa
> (szablon Aspire sam o tym ostrzega w komentarzu).

### ServiceDefaults — jedna metoda, cztery zachowania

`builder.AddServiceDefaults()` w każdym serwisie robi:

| Co | Mechanizm |
|---|---|
| Service discovery | `AddServiceDiscovery()` + `http.AddServiceDiscovery()` na każdym `HttpClient` |
| Resilience | `AddStandardResilienceHandler()` (retry, circuit breaker, timeouty; w logu `Polly ... Standard-Retry`) |
| Health checks | check `self` z tagiem `live` + `MapDefaultEndpoints()` |
| OpenTelemetry | logi + metryki (ASP.NET Core, HttpClient, runtime) + trace'y, eksport OTLP gdy jest `OTEL_EXPORTER_OTLP_ENDPOINT` |

Ważne: `ServiceDefaults` to zwykły projekt biblioteczny (`IsAspireSharedProject`),
**Twój kod** — wygenerowany szablonem `aspire-servicedefaults`, potem edytowalny. Dziś
zmieniamy w nim jedną rzecz.

### Własna telemetria: `ActivitySource` i `Meter`

Domyślna instrumentacja mówi "wpadł request HTTP". Nie powie, że *biznesowo* zrobiłeś
lookup SKU i go nie znalazłeś. Do tego są własne źródła. W `CatalogApi`:

```csharp
static class CatalogTelemetry
{
    public static readonly ActivitySource Source = new("Store.Catalog");
    public static readonly Meter Meter = new("Store.Catalog");
    public static readonly Counter<long> Lookups =
        Meter.CreateCounter<long>("catalog.lookups", unit: "{lookup}");
}

// w endpoincie:
using var activity = CatalogTelemetry.Source.StartActivity("catalog.lookup");
activity?.SetTag("catalog.sku", sku);
CatalogTelemetry.Lookups.Add(1, new KeyValuePair<string, object?>("found", product is not null));
```

**Pułapka, którą warto znać:** samo utworzenie `ActivitySource`/`Meter` nic nie
eksportuje. OpenTelemetry SDK zbiera tylko źródła, które **jawnie zarejestrujesz**.
Zamiast dopisywać każde źródło osobno, przyjęliśmy konwencję nazw `Store.*` i
jedną linijkę w `ServiceDefaults`:

```csharp
.WithMetrics(m => m.AddMeter("Store.*") ...)
.WithTracing(t => t.AddSource("Store.*") ...)
```

Nowy serwis z `Meter("Store.Cokolwiek")` łapie się sam — tak wynika z dokumentacji
OpenTelemetry .NET (wildcard `*` w nazwie źródła), ale **nie zweryfikowaliśmy tego
eksportem do dashboardu** — patrz "Czego nie sprawdziliśmy".

`StoreApi` ma własny licznik `store.quotes` (z tagiem `outcome`) i histogram
`store.quote.value` (wartość brutto wyceny w PLN).

#### Propagacja trace'a — dowód w JSON-ie

Endpoint `catalog` zwraca `Activity.Current?.TraceId`, a `store` dokłada swój. Jeśli
W3C trace context idzie przez `HttpClient` (a idzie, dzięki instrumentacji z
`ServiceDefaults`), oba ID są identyczne:

```
{"sku":"KB-001","name":"Klawiatura mechaniczna","quantity":3,"net":1047.00,"gross":1287.81,
 "storeTraceId":"61318cb9b885520e32d51dd2f594940a","catalogTraceId":"61318cb9b885520e32d51dd2f594940a"}
```

W dashboardzie to jeden trace z spanami `store.quote` → HTTP klienta → serwer `catalog`
→ `catalog.lookup`. (Dashboard nie był dziś otwierany — patrz niżej.)

#### `MeterListener` — podgląd metryk bez dashboardu

Żeby zweryfikować własny licznik bez UI, `CatalogApi` ma dev-owy endpoint
`/debug/lookups`, który używa tego samego mechanizmu co OpenTelemetry SDK —
`System.Diagnostics.Metrics.MeterListener` — i sumuje pomiary per tag:

```
GET catalog /debug/lookups -> {"catalog.lookups{found=false}":1,"catalog.lookups{found=true}":1}
```

### Weryfikacja bez `curl`: AppHost jako biblioteka

Zamiast odpalać `dotnet run` i pytać z zewnątrz, projekt `Store.Verify` używa
`Aspire.Hosting.Testing`:

```csharp
var appHost = await DistributedApplicationTestingBuilder.CreateAsync<Projects.AppHost>(ct);
await using var app = await appHost.BuildAsync(ct);
await app.StartAsync(ct);

await app.ResourceNotifications.WaitForResourceHealthyAsync("catalog", ct);
await app.ResourceNotifications.WaitForResourceHealthyAsync("store", ct);

using var store = app.CreateHttpClient("store");   // HttpClient ze zwykłym adresem zasobu
var json = await store.GetStringAsync("/quote/KB-001?qty=3", ct);
```

To ten sam AppHost co produkcyjnie-deweloperski (te same zasoby, `WaitFor`, health
checki), tylko sterowany z kodu. Idealny fundament pod testy integracyjne
(w kolejnych wydaniach można je podpiąć pod TUnit — patrz rubryka TUnit). Jedno polecenie:

```bash
dotnet run --project days/2026-09-26/aspire/code/Store.Verify/Store.Verify.csproj
```

Prawdziwy wynik:

```
catalog healthy po 11.4s, store healthy po 11.4s
[PASS] catalog zdrowy dopiero po rozgrzewce (>= 3 s)
[PASS] catalog /health = 200 (body: Healthy)
[PASS] wycena: 3 x 349.00 netto = 1047.00
[PASS] wycena: brutto (VAT 23%) = 1287.81
[PASS] ten sam TraceId w store i catalog (61318cb9b885520e32d51dd2f594940a)
[PASS] nieznany SKU -> 404
[PASS] services:catalog:http:0 ustawione przez WithReference
[PASS] OTLP endpoint wstrzyknięty
[PASS] Meter: catalog.lookups{found=true} == 1
[PASS] Meter: catalog.lookups{found=false} == 1
WSZYSTKO OK
```

(11,4 s to nie 3 s rozgrzewki, tylko start dwóch procesów przez `dotnet run` + rozgrzewka
+ interwał odpytywania health checku.)

### Dlaczego to ważne w praktyce

1. **`WaitFor` + health check zabija wyścigi startowe.** Bez tego `store` startuje,
   pierwszy request leci do jeszcze nie gotowego `catalog` i dostajesz losowe 5xx —
   raz na ileś uruchomień, więc bug jest nie do złapania.
2. **Adresy jako konfiguracja = ten sam kod lokalnie i gdzie indziej.** `http://catalog`
   w kodzie nie zna portu, hosta ani środowiska.
3. **Własny `ActivitySource`/`Meter` to różnica między "widzę ruch HTTP" a "widzę, co
   biznesowo się dzieje"**, a konwencja `Store.*` w jednym miejscu zamyka temat
   "zapomniałem zarejestrować źródło".
4. **AppHost sterowany z kodu** to test integracyjny całego układu bez Dockera i bez curl-a.

### Czego dziś NIE sprawdziliśmy (uczciwie)

- **Dashboard i OTLP end-to-end.** Testowy AppHost startuje bez dashboardu, więc
  nie widzieliśmy trace'a ani metryk `store.quotes`/`catalog.lookups` w UI. Sprawdzone
  zostało to, że (a) zmienne OTLP są wstrzyknięte, (b) `TraceId` jest wspólny,
  (c) licznik liczy — nie że eksport OTLP dociera do dashboardu.
- **Efekt `AddSource("Store.*")`/`AddMeter("Store.*")`** — czy wildcard faktycznie rejestruje
  nasze źródła w SDK, nie było sprawdzane. `TraceId` w JSON-ie dowodzi propagacji
  między serwisami, nie eksportu spanów.
- **Zachowanie `AddStandardResilienceHandler` przy awarii** — widać tylko ścieżkę
  bez błędów (`Polly ... Standard-Retry ... Attempt: 0`), retry/circuit breaker nie były wywoływane.
- Tylko HTTP (bez HTTPS/dev-certów), tylko Linux, tylko Aspire 13.5.2.
- Dwa komunikaty `fail: ... HealthCheckService` w wyjściu to oczekiwane 503 z rozgrzewki
  widziane przez Aspire, nie błąd testu.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — komendy od zera i pełny wynik.

---

<div align="center">

[← wydanie #3 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
