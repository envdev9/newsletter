# Kod do wydania #1 — .NET Aspire: AppHost i pierwszy zasób

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`, sprawdzone na `10.0.400`) +
szablony Aspire (`dotnet new list aspire` powinno pokazać m.in. `aspire-apphost`; jeśli
nie ma, doinstaluj: `dotnet new install Aspire.ProjectTemplates`).

Uwaga na PATH: jeśli `dotnet` nie jest w systemowym PATH, dodaj:

```bash
export PATH="$HOME/.dotnet:$PATH"
```

## Fragment prasówki, którego dotyczy ten kod

> `AppHost` to zwykły, uruchamialny projekt .NET, tylko ze specjalnym SDK
> (`Aspire.AppHost.Sdk`), które dokłada orkiestrację. `DistributedApplication.CreateBuilder(args)`
> buduje model całego środowiska, `builder.AddProject<Projects.DemoApi>("api")`
> rejestruje nasze API jako zasób o logicznej nazwie `"api"`. `Projects.DemoApi` to
> source-generated typ, który powstaje automatycznie z `ProjectReference` w
> `AppHost.csproj` — nie ma literałów ze ścieżkami.
>
> Bez ani jednej linijki dodatkowej konfiguracji dostajemy: dashboard (webowy UI z
> listą zasobów, stanem, logami na żywo), gotowy endpoint OTLP (OpenTelemetry) i
> mechanizm service discovery po logicznych nazwach zasobów (przyda się od kolejnego
> zasobu wzwyż).

## Struktura projektu

```
code/
├── AppHost/          # projekt orkiestrujący - to go odpalamy
│   └── AppHost.cs    # cały kod orkiestracji (3 linijki)
└── DemoApi/           # zwykłe ASP.NET Core Web API (dotnet new webapi),
                        # zero wiedzy o tym, że jest orkiestrowane przez Aspire
```

`AppHost/AppHost.csproj` ma jeden istotny wpis - referencję do API, dzięki której
Aspire generuje `Projects.DemoApi`:

```xml
<ItemGroup>
  <ProjectReference Include="..\DemoApi\DemoApi.csproj" />
</ItemGroup>
```

## Jak uruchomić od zera

```bash
cd AppHost
dotnet run
```

(albo z katalogu `code/`: `dotnet run --project AppHost`)

Przy pierwszym starcie Aspire może poprosić o zaufanie certyfikatowi deweloperskiemu
(`dotnet dev-certs https --trust`) - jeśli terminal jest nieinteraktywny, może się to nie
udać w 100%, ale sam AppHost i tak wstaje (patrz log niżej, gdzie widać ostrzeżenie o
częściowym zaufaniu certyfikatu, a proces mimo to normalnie startuje).

Po starcie w konsoli pojawia się link do dashboardu - otwórz go w przeglądarce, zobaczysz
zasób `api`, jego status, logi na żywo i (po kliknięciu w zasób) jego rzeczywisty adres.

Zatrzymanie: `Ctrl+C` w terminalu, w którym działa `dotnet run` (Aspire sam sprząta
podprocesy).

## Dowód, że to naprawdę wstaje: prawdziwy log uruchomienia

Uruchomione lokalnie: `timeout 60 dotnet run --project AppHost --launch-profile http`
(limit czasu tylko po to, żeby proces nie wisiał wiecznie w automatycznej weryfikacji -
bez `timeout` proces po prostu działa, dopóki nie naciśniesz `Ctrl+C`).

Fragment konsoli (dosłowny, nieedytowany poza wycięciem pustych linii):

```
Using launch settings from AppHost/Properties/launchSettings.json...
Building...
🔐 Trusting certificates...
⚠️ Developer certificates may not be fully trusted (trust exit code was: PartiallyFailedToTrustTheCertificate).
Connecting to AppHost...
Starting dashboard...

     AppHost:  AppHost.csproj

   Dashboard:  https://localhost:17064/login?t=491be412226860fc2032ad5423feeaf4

        Logs:  /home/mag/.aspire/logs/cli_20260924T220726_8cb9281b.log

               Press CTRL+C to stop the AppHost and exit.
```

Odpowiadający fragment ze szczegółowego logu CLI (`~/.aspire/logs/cli_*.log`),
pokazujący realną sekwencję stanów zasobu `api` i moment gotowości dashboardu:

```
[22:07:50.679] [INFO] [AppHost] Resource api/api-xzayzndt changed state: Starting
[22:07:51.073] [INFO] [AppHost] Resource api/api-xzayzndt changed state: Running
[22:07:51.104] [INFO] [AppHost] Resource 'api' is ready.
[22:07:51.129] [INFO] [AppHost] Resource 'aspire-dashboard' is ready.
[22:07:51.148] [INFO] [AppHost] Now listening on: https://localhost:17064
```

Oraz konfiguracja endpointów dashboardu (dowód, że OTLP wstaje bez żadnej ręcznej
konfiguracji w naszym kodzie):

```
Dashboard endpoint 'https' configured: https://localhost:17064
Dashboard endpoint 'http' configured: http://localhost:15125
Dashboard endpoint 'otlp-grpc' configured: https://localhost:21261
```

Weryfikacja `dotnet build` (osobno, bez uruchamiania):

```
$ dotnet build AppHost/AppHost.csproj
  DemoApi -> .../DemoApi/bin/Debug/net10.0/DemoApi.dll
  AppHost -> .../AppHost/bin/Debug/net10.0/AppHost.dll
Build succeeded.
    0 Warning(s)
    0 Error(s)
```

Po zakończonym teście (`timeout` sam ubił proces po 60s) sprawdzone, że nie zostały
żadne wiszące procesy (`ps aux | grep -iE "apphost|DemoApi|aspire"` → pusto).

Wersje użyte przy weryfikacji: `.NET SDK 10.0.400`, `Aspire.AppHost.Sdk 13.5.2`
(widoczne w `AppHost.csproj`: `<Project Sdk="Aspire.AppHost.Sdk/13.5.2">`).

## Co NIE zostało dziś użyte (celowo)

Zgodnie z założeniem pierwszego wydania tej rubryki: **żadnych zewnętrznych
kontenerów** (Postgres/Redis/RabbitMQ), żadnego Dockera. Jeden zasób — projekt API —
wystarczy, żeby pokazać, co Aspire robi "za kulisami" (dashboard, OTLP, model zasobów).
Integracje z bazami i kolejkami, oraz `ServiceDefaults` (pakiet dający
`AddServiceDefaults()`/health checks/resilience z automatu) — w kolejnych wydaniach tej
rubryki.
