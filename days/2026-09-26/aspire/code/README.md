# Kod do wydania #3 — .NET Aspire: dwa serwisy, service discovery, ServiceDefaults, własna telemetria

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

## Wymagania

- **.NET 10 SDK** (sprawdzone na `10.0.400`). Pakiet SDK `Aspire.AppHost.Sdk/13.5.2` i
  pakiety NuGet zostaną pobrane przy pierwszym buildzie (potrzebny dostęp do nuget.org).
- Docker **nie jest potrzebny** — zero kontenerów.
- Jeśli `dotnet` nie jest w PATH: `export PATH="$HOME/.dotnet:$PATH"`.

## Fragment prasówki, którego dotyczy ten kod

> `WithReference(catalog)` wstrzykuje do procesu `store` konfigurację
> `services__catalog__http__0`; `http://catalog` w `HttpClient` rozwiązuje handler service
> discovery z `AddServiceDefaults()`. `WaitFor(catalog)` razem z `WithHttpHealthCheck("/health")`
> czeka, aż katalog jest **zdrowy**, nie tylko uruchomiony — dlatego `CatalogApi` ma
> 3-sekundową "rozgrzewkę" (`Unhealthy("warming up")`), która to uwidacznia.
> `ServiceDefaults` dokłada service discovery, resilience, health checks (`/health`, `/alive`)
> i OpenTelemetry; własne `ActivitySource`/`Meter` o nazwach `Store.*` są rejestrowane
> jednym wildcardem. Weryfikacja bez `curl`: `Store.Verify` podnosi cały AppHost w procesie
> przez `DistributedApplicationTestingBuilder` i woła API `HttpClient`em.

## Struktura

```
code/
├── AppHost/               # orkiestracja: catalog + store, WithReference/WaitFor
├── Store.ServiceDefaults/ # AddServiceDefaults(), MapDefaultEndpoints(), OTel, health checks
├── CatalogApi/            # GET /products/{sku}, /debug/lookups, własny ActivitySource/Meter
├── StoreApi/              # GET /quote/{sku}?qty=, /discovery, woła http://catalog
└── Store.Verify/          # konsolowa weryfikacja end-to-end (Aspire.Hosting.Testing)
```

## Jak uruchomić od zera

### A) Weryfikacja automatyczna (jedno polecenie, bez curl)

Z katalogu `code/`:

```bash
dotnet run --project Store.Verify/Store.Verify.csproj
```

Proces zwraca kod wyjścia 0 przy sukcesie. Prawdziwy wynik z uruchomienia
(`.NET SDK 10.0.400`, `Aspire 13.5.2`, Linux):

```
fail: Microsoft.Extensions.Diagnostics.HealthChecks.DefaultHealthCheckService[103]
      Health check catalog_http_/health_200_check with status Unhealthy completed after 4652.8462ms with message 'Request to http://localhost:46155/health returned 503 ServiceUnavailable'
fail: Microsoft.Extensions.Diagnostics.HealthChecks.DefaultHealthCheckService[103]
      Health check catalog_http_/health_200_check with status Unhealthy completed after 8.1624ms with message 'Request to http://localhost:46155/health returned 503 ServiceUnavailable'
catalog healthy po 11.4s, store healthy po 11.4s
[PASS] catalog zdrowy dopiero po rozgrzewce (>= 3 s)
[PASS] catalog /health = 200 (body: Healthy)
GET store /quote/KB-001?qty=3 -> {"sku":"KB-001","name":"Klawiatura mechaniczna","quantity":3,"net":1047.00,"gross":1287.81,"storeTraceId":"61318cb9b885520e32d51dd2f594940a","catalogTraceId":"61318cb9b885520e32d51dd2f594940a"}
[PASS] wycena: 3 x 349.00 netto = 1047.00
[PASS] wycena: brutto (VAT 23%) = 1287.81
[PASS] ten sam TraceId w store i catalog (61318cb9b885520e32d51dd2f594940a)
[PASS] nieznany SKU -> 404
GET store /discovery -> {"catalogHttp":"http://localhost:46155","catalogHttps":null,"otlpEndpoint":true,"serviceName":"store"}
[PASS] services:catalog:http:0 ustawione przez WithReference
[PASS] OTLP endpoint wstrzyknięty
GET catalog /debug/lookups -> {"catalog.lookups{found=false}":1,"catalog.lookups{found=true}":1}
[PASS] Meter: catalog.lookups{found=true} == 1
[PASS] Meter: catalog.lookups{found=false} == 1
WSZYSTKO OK
```

Dwa `fail:` na górze to oczekiwane odpowiedzi 503 z rozgrzewającego się katalogu, widziane
przez health check Aspire — nie błąd testu. Porty są losowe przy każdym uruchomieniu.
Pierwsze uruchomienie trwa dłużej (restore + build).

### B) Ręcznie, z dashboardem (niezweryfikowane w tym wydaniu)

```bash
dotnet run --project AppHost --launch-profile http
```

W konsoli pojawi się link do dashboardu (zasoby `catalog` i `store`, logi, trace'y,
metryki). Ta ścieżka (dashboard + eksport OTLP) **nie była dziś przez nas sprawdzana** —
w wydaniu #1 samo uruchomienie AppHost z dashboardem działało, ale nie z tymi dwoma serwisami.
Porty serwisów zobaczysz w dashboardzie (są dynamiczne).

## Porządek po sobie

Test sam zatrzymuje wszystkie procesy przy wyjściu (`await using var app`). Katalogi `bin/` i
`obj/` można usunąć po zabawie.

## Czego nie zweryfikowano

- Dashboard i faktyczny eksport OTLP (trace'y, metryki `store.quotes`, `catalog.lookups`).
- Że wildcard `Store.*` w `AddSource`/`AddMeter` rejestruje nasze źródła w SDK.
- Retry/circuit breaker `AddStandardResilienceHandler` przy awarii (tylko ścieżka bez błędów).
- HTTPS, macOS/Windows, inne wersje Aspire niż 13.5.2.
