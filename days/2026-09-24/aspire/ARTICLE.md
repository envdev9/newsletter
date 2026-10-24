<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #1 — 24 września 2026

![.NET Aspire](https://img.shields.io/badge/.NET_Aspire-512BD4?style=for-the-badge)

## AppHost — jeden plik C#, który uruchamia i pilnuje całego środowiska

</div>

---

> _"Aspire nie jest frameworkiem do pisania aplikacji. Jest frameworkiem do **odpalania
> i obserwowania** aplikacji, które już umiesz napisać."_

Dziś zupełne podstawy **.NET Aspire**: czym jest `AppHost`, co dokładnie dzieje się, gdy
odpalasz `dotnet run` na takim projekcie, i dlaczego dostajesz dashboard, service
discovery i OpenTelemetry, mimo że w kodzie poniżej nie ma ani jednej linijki
konfigurującej te trzy rzeczy. Sprawdzone lokalnie na `.NET SDK 10.0.400` +
`Aspire.AppHost.Sdk 13.5.2` — kod w [`code/`](code/) faktycznie startuje, log w
[`code/README.md`](code/README.md) to prawdziwy fragment konsoli, nie wymyślony przykład.

---

### Problem, który Aspire rozwiązuje

Weź dowolny system, który ma więcej niż jeden proces do odpalenia lokalnie: API +
frontend, albo API + baza, albo trzy mikroserwisy. Do tej pory żeby to uruchomić na
swoim laptopie, robiłeś jedno z dwojga:

- **Ręcznie** — kilka terminali, w każdym `dotnet run` w innym folderze, ręcznie
  pilnujesz, żeby porty się nie gryzły, ręcznie kopiujesz URL-e między
  `appsettings.json`, żeby serwis A wiedział, gdzie żyje serwis B.
- **`docker-compose`** — działa, ale to osobny język (YAML), osobny etap budowania
  (obrazy), i zupełnie inny cykl debugowania niż zwykłe "F5" w IDE.

Żadna z tych opcji nie daje ci jednego miejsca, w którym widzisz: które procesy żyją,
jakie mają logi, jakie metryki, jakie zapytania HTTP między sobą wysyłają. Aspire
atakuje dokładnie ten problem — **orkiestrację lokalnego środowiska**, w czystym C#,
bez Dockera (chociaż Docker też potrafi obsłużyć, jak zasób — o tym w kolejnych
wydaniach).

### Co to jest AppHost

`AppHost` to zwykły, uruchamialny projekt .NET — ale specjalnego typu SDK
(`Aspire.AppHost.Sdk`), które dokłada mechanizm orkiestracji. Cały kod, jaki napisaliśmy
w tym wydaniu, to dosłownie to:

```csharp
// AppHost/AppHost.cs
var builder = DistributedApplication.CreateBuilder(args);

// Jeden zasób: nasze API. Aspire samo wie, jak je zbudować i odpalić,
// bo AppHost ma ProjectReference do DemoApi.csproj - stąd source-generated
// typ Projects.DemoApi.
builder.AddProject<Projects.DemoApi>("api");

builder.Build().Run();
```

Trzy rzeczy, które warto rozszyfrować:

1. **`DistributedApplication.CreateBuilder(args)`** — to jest odpowiednik
   `WebApplication.CreateBuilder(args)`, tylko zamiast budować jeden serwer HTTP, buduje
   **model całego środowiska** (jeden proces albo dziesięć).
2. **`Projects.DemoApi`** — to nie istnieje nigdzie w naszym kodzie jako klasa. Aspire
   ma source generator, który **w czasie kompilacji** skanuje `ProjectReference`
   w pliku `AppHost.csproj` i dla każdego referencjonowanego projektu tworzy statycznie
   typowany uchwyt (`Projects.DemoApi`, `Projects.CośInnego`...). Dzięki temu nie ma
   literałów ze ścieżkami do `.csproj` — kompilator sprawdzi, że projekt istnieje.
3. **`.AddProject<T>("api")`** — rejestruje ten projekt jako **zasób** o logicznej
   nazwie `"api"`. To ta nazwa (nie port, nie URL) będzie używana wszędzie indziej
   w Aspire — w dashboardzie, w logach, a w przyszłych wydaniach też w service
   discovery między zasobami.

`AppHost.csproj` ma tylko jeden dodatek względem szkieletu wygenerowanego przez
szablon — referencję do naszego API:

```xml
<ItemGroup>
  <ProjectReference Include="..\DemoApi\DemoApi.csproj" />
</ItemGroup>
```

`DemoApi` sam w sobie to zwykły `dotnet new webapi` — żadnego pakietu Aspire, żadnej
specjalnej konfiguracji. Aspire nie wymaga, żeby zasób "wiedział", że jest orkiestrowany
(chociaż w kolejnych wydaniach dodamy integrację, która to wykorzysta — `AddServiceDefaults()`).

### Co się dzieje pod maską, gdy odpalasz `dotnet run --project AppHost`

To jest sedno tego wydania — Aspire robi w tle kilka rzeczy, których nigdzie nie
skonfigurowaliśmy:

**1. Startuje dashboard.** Osobny proces (`aspire-dashboard`), webowy UI, na który
dostajesz link w konsoli już przy starcie:

```
   Dashboard:  https://localhost:17064/login?t=<token>
```

Wchodzisz tam i widzisz listę zasobów (u nas jeden: `api`), jego stan (`Starting` →
`Running`), logi na żywo, i (gdy dodamy więcej zasobów w kolejnych wydaniach) metryki
i trace'y requestów między nimi.

**2. Włącza się OpenTelemetry — bez ani jednej linijki konfiguracji w naszym kodzie.**
W logu startowym widać gotowy endpoint OTLP:

```
- OTLP/gRPC:  https://localhost:21261
```

To adres, pod który dashboard nasłuchuje danych telemetrycznych (logi, metryki,
trace'y) w standardowym protokole OpenTelemetry. Projekty dodane do `AppHost`
z pakietem `ServiceDefaults` (pokażemy w kolejnym wydaniu Aspire) automatycznie
wysyłają tam dane — dziś istotne jest, żeby zapamiętać: **ten endpoint istnieje od razu**,
zanim ktokolwiek napisał choćby jedną linijkę kodu telemetrii.

**3. Service discovery — fundament pod przyszłe wydania.** Zasób ma logiczną nazwę
(`"api"`), nie port. Gdy w kolejnym wydaniu dodamy drugi zasób, który woła to API,
nie będzie w jego kodzie `http://localhost:5231` — będzie `http://api`, a Aspire w
czasie działania podmieni to na prawdziwy, aktualny adres (port bywa inny za każdym
razem, bo Aspire przydziela go dynamicznie). Dziś mamy jeden zasób, więc tego efektu
jeszcze nie widać na własne oczy — ale mechanizm już działa pod spodem, dashboard już
zna adres `api` i pokaże go w szczegółach zasobu.

**4. Zarządza cyklem życia procesu.** Aspire buduje `DemoApi`, odpala go jako
podproces, pilnuje jego stanu (`Starting` → `Running` → health check → `Ready`) i gdy
zabijesz `AppHost` (`Ctrl+C`), sprząta po sobie — zamyka wszystkie zasoby, nie zostawia
sierot.

Realny log z uruchomienia (pełny fragment w [`code/README.md`](code/README.md))
pokazuje dokładnie tę sekwencję:

```
Resource api/api-xzayzndt changed state: Starting
Resource api/api-xzayzndt changed state: Running
Resource 'api' is ready.
Now listening on: https://localhost:17064
```

### Dlaczego to ważne w praktyce

Bez Aspire, żeby dostać dashboard z logami+metrykami+trace'ami wszystkich serwisów
naraz, musiałbyś ręcznie postawić Grafanę/Prometheusa/Jaegera (albo ich odpowiedniki) i
ręcznie wpiąć w każdy projekt eksportery OpenTelemetry. Tu dostajesz to od pierwszej
sekundy, lokalnie, jednym `dotnet run`, zero Dockera, zero YAML-a. To nie zastępuje
prawdziwego stosu observability na produkcji (do tego nadal poleci Prometheus/Grafana —
patrz rubryka Observability) — to jest narzędzie **deweloperskie**: masz jeden pulpit,
z którego widzisz całe swoje środowisko, zanim jeszcze cokolwiek wdrożysz.

**Pełny, uruchomiony i zweryfikowany kod:** [`code/`](code/).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — dokładne komendy i prawdziwy log startowy.

---

<div align="center">

[← wróć do wydania #1 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
