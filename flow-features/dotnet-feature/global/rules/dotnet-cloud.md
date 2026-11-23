---
paths:
  - "**/Program.cs"
  - "**/Controllers/**/*.cs"
  - "**/Endpoints/**/*.cs"
  - "**/*AppHost*/**"
  - "**/*ServiceDefaults*/**"
  - "**/Dockerfile"
  - "**/appsettings*.json"
  - "**/charts/**"
  - "**/.teamcity/**"
---

# Zasady .NET: API i chmura (ASP.NET Core, Kubernetes, Aspire, TeamCity)

Uzupełnienie `~/.claude/rules/dotnet.md`. Czytaj, gdy zadanie dotyczy API, hostingu, deployu, Aspire lub CI.
Nie dotyczy aplikacji konsolowych bez API i bez deployu na Kubernetesa.

## API (ASP.NET Core)

- Poprawne kody HTTP i metody (idempotentne PUT/DELETE, 201 z `Location`, 404 vs 400 vs 409).
- Autoryzacja jawna na endpointach; nie polegaj na tym, że klient nie zna identyfikatora. Sprawdzaj własność zasobu.
- Brak logiki biznesowej w kontrolerach/endpointach; delegacja do serwisów.

## Cloud-ready (Kubernetes)

Aplikacja ma działać w kontenerze pod Kubernetesem. Pisząc kod, zakładaj wiele replik, restarty w dowolnej chwili i brak trwałego dysku.

- **Bezstanowość:** żadnego stanu w pamięci procesu, od którego zależy poprawność (sesje, cache jako źródło prawdy, blokady w pamięci). Stan w Postgresie lub zewnętrznym cache. Zadania w tle muszą działać poprawnie przy N replikach (blokada w bazie, np. `pg_advisory_lock`, albo idempotencja).
- **Konfiguracja przez środowisko (12-factor):** wszystko z env i `IOptions<T>` (zagnieżdżone klucze jako `Section__Key`). Sekrety (connection string, klucze) z Secret/zmiennych środowiskowych, nigdy w obrazie ani repo. Brak ścieżek i adresów zaszytych na sztywno.
- **Health checks:** osobne endpointy `/health/live` (proces żyje, bez sprawdzania zależności) i `/health/ready` (m.in. połączenie z Postgresem) przez `AddHealthChecks()`. Pod probe'y liveness, readiness i startup. W projekcie z Aspire robi to `ServiceDefaults` (sekcja .NET Aspire).
- **Graceful shutdown:** obsługuj SIGTERM (host .NET robi to domyślnie). Przestań przyjmować ruch, dokończ żądania w ramach `HostOptions.ShutdownTimeout` krótszego niż `terminationGracePeriodSeconds`. Długie operacje respektują `CancellationToken` ze `StoppingToken`.
- **Logi na stdout:** strukturalne (JSON lub Serilog), bez zapisu do plików. Żadnych danych wrażliwych.
- **Odporność na zależności:** przy starcie baza może być jeszcze niedostępna, więc retry z backoffem zamiast crasha lub nieskończonego czekania. Timeouty na wywołaniach HTTP i zapytaniach (`commandTimeout`), polityki retry/circuit breaker (Polly / `Microsoft.Extensions.Http.Resilience`) tam, gdzie wołasz zewnętrzne usługi. `HttpClient` przez `IHttpClientFactory`.
- **Pula połączeń:** `liczba replik × Maximum Pool Size` nie może przekroczyć `max_connections` w Postgresie. Ustaw rozsądny `Maximum Pool Size`.
- **Migracje a wiele replik:** schemat zmieniaj tak, by stara i nowa wersja działały równolegle podczas rolling update (najpierw dodaj, później usuń). Migracje jako osobny krok (Job / init container), nie przez wszystkie repliki naraz w `Main`.
- **Obraz:** wieloetapowy Dockerfile (SDK do builda, runtime `aspnet` do uruchomienia), użytkownik nie-root, nasłuch na porcie z env (`ASPNETCORE_URLS`), `.dockerignore`. Zasoby (requests/limits) w chartcie, nie w kodzie.
- **Obserwowalność:** metryki i logi zgodnie z konwencją repo (skille `observability` i `helm-deploy`). Jeśli zadanie obejmuje chart lub deploy, zgłoś to jako osobny krok, nie zgaduj.

## .NET Aspire

Dotyczy tylko repo z Aspire. Przed pierwszą zmianą sprawdź układ: projekt `AppHost` (orkiestracja) i `ServiceDefaults` (wspólna konfiguracja), oraz wersję Aspire.

- **Serwis:** wywołuj `builder.AddServiceDefaults()` i `app.MapDefaultEndpoints()` z `ServiceDefaults`. Nie dubluj konfiguracji OpenTelemetry, health checków, service discovery ani resilience, które już są w `ServiceDefaults`. Wspólne zmiany rób tam, nie w pojedynczym serwisie.
- **Health checks:** domyślnie `MapDefaultEndpoints()` wystawia `/health` i `/alive` tylko w środowisku Development. Pod Kubernetesem endpointy muszą być dostępne także w produkcji (zmiana w `ServiceDefaults`, najlepiej z zabezpieczeniem przed wystawieniem na zewnątrz). Zgłoś, jeśli trzeba zmienić `ServiceDefaults`.
- **Postgres:** zależność od bazy deklaruj w `AppHost` (`AddPostgres(...).AddDatabase("db")`, w serwisie `WithReference(db)`). W serwisie używaj integracji klienta (`builder.AddNpgsqlDataSource("db")`), która rejestruje `NpgsqlDataSource` z health checkiem i telemetrią. Dapper pracuje na połączeniach z tego `NpgsqlDataSource`. Nie buduj connection stringów ręcznie.
- **Konfiguracja:** nazwa zasobu w AppHost (`"db"`) to klucz `ConnectionStrings:db` (w kontenerze `ConnectionStrings__db`). Nie zaszywaj adresów, korzystaj z `WithReference` i service discovery.
- **Skąd serwis bierze connection string:** serwis zna tylko klucz `ConnectionStrings:db` i nie wie, kto go ustawił.

  | Środowisko | Kto ustawia `ConnectionStrings:db` | Skąd baza |
  |---|---|---|
  | Lokalnie przez AppHost | Aspire (env `ConnectionStrings__db`) | kontener Postgres z Aspire |
  | Kubernetes | Secret → env `ConnectionStrings__db` w chartcie | baza zewnętrzna lub w klastrze |
  | Testy integracyjne | fixture (`UseSetting("ConnectionStrings:db", ...)` w `WebApplicationFactory`) | baza testowa, własny schemat |

  Na Kubernetesie AppHost nie działa i nic nie wstrzykuje zmiennej, więc nazwa klucza w chartcie musi być identyczna jak w kodzie (`db`); inaczej `AddNpgsqlDataSource("db")` wywali się przy starcie. W testach aplikacja nadal woła `AddNpgsqlDataSource("db")`, a fixture podmienia klucz na connection string bazy testowej (izolacja np. przez `Search Path=test_<sufiks>`); testy nie uruchamiają AppHost. W AppHost rozdzielaj tryby: w run mode kontener Postgresa, w publish mode zewnętrzna baza (`AddConnectionString("db")` lub parametr), zgodnie z wersją Aspire w repo.
- **Wiele replik i migracje:** migracje uruchamiaj SqlDeployerem jako osobny zasób/Job (w AppHost np. kontener lub proces z `WaitFor` bazy), a serwisy czekają na niego (`WaitForCompletion`), zamiast migrować w `Main` każdej repliki.
- **Deploy do Kubernetesa:** Aspire nie zastępuje chartów. Sposób generowania manifestów/chartów sprawdź w repo i skillu `helm-deploy`; nie zgaduj. Zmiany deploymentu zgłaszaj jako osobny krok.

## CI/CD (TeamCity)

Domyślny CI to TeamCity. Pisząc kod i testy, zadbaj, by:
- build i testy działały z CLI bez IDE: `dotnet build` i `dotnet test` na czystym checkoutcie, bez lokalnych zależności ani ręcznych kroków,
- testy integracyjne brały connection string z parametru środowiskowego (w TeamCity z parametru/sekretu), a agent TeamCity miał sieciowy dostęp do bazy testowej; brak konfiguracji ma dawać czytelny błąd,
- wersje obrazów, pakietów i SDK były przypięte (`global.json`, brak `latest`),
- sekrety nie trafiały do repo; w pipeline pochodzą z parametrów/sekretów TeamCity.

Konfigurację pipeline (Kotlin DSL / UI) zmieniaj tylko, gdy zadanie tego wprost wymaga; w przeciwnym razie zgłoś potrzebną zmianę.
