# Kod do wydania #5 — .NET Aspire: `AddRedis`, prawdziwy kontener Docker

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Wymagania

- **.NET 10 SDK** (sprawdzone na `10.0.400`), pakiety Aspire `13.5.2` z nuget.org.
- **Docker** (sprawdzone na Docker Engine `29.1.3`) — demon musi odpowiadać (`docker info`).
  Ten kod **realnie uruchamia kontener Redis** przez Docker, nie atrapę.
- Jeśli `dotnet` nie jest w PATH: `export PATH="$HOME/.dotnet:$PATH"`.
- Potrzebne miejsce na dysku: obraz `redis:8.6` to ok. 200 MB (jeśli nie masz go w cache
  Dockera, pierwszy `dotnet run` go pobierze).

## Fragment prasówki, którego dotyczy ten kod

> `AddRedis("cache")` odpala prawdziwy kontener Redis i zarządza jego cyklem życia.
> Domyślnie (Aspire 13.5.2) to obraz `redis:8.6` — **nie** `7-alpine` — z automatycznie
> wygenerowanym hasłem (`--requirepass`) i włączonym TLS (`--tls-port`/`--tls-cert-file`),
> mimo że w kodzie AppHosta nie ma o tym ani słowa. `WithReference(cache)` wstrzykuje
> gotowy connection string (z hasłem i `ssl=true`) do `cache-api`, a `builder.AddRedisClient
> ("cache")` po stronie serwisu od razu z niego korzysta — żadnej ręcznej konfiguracji
> auth/TLS po stronie klienta.

## Struktura

```
code/
├── AppHost/        # AddRedis("cache"), WithReference + WaitFor na kontenerze
├── CacheApi/       # PUT/GET /cache/{key} przez StackExchange.Redis, /cache-info (dowód realnego połączenia)
└── Cache.Verify/   # test AppHosta: realnie odpala kontener, sprawdza round-trip przez HTTP
```

## Uruchomienie

Wymaga działającego Dockera (`docker info` musi się powieść). Z katalogu `code/`:

```bash
dotnet run --project Cache.Verify/Cache.Verify.csproj
```

Kod wyjścia 0 = sukces (Aspire sam odpala i sprząta kontener Redis). Prawdziwy wynik
(SDK `10.0.400`, Aspire `13.5.2`, Docker `29.1.3`, Linux) — zmierzony w trzech
niezależnych przebiegach, za każdym razem identyczny:

```
=== Start AppHost (kontener Redis przez Docker) ===
cache-api = Healthy (czyli kontener redis 'cache' też musiał wystartować)
GET /cache-info -> {"endpoint":"Unspecified/localhost:34133","isConnected":true,"role":"master","connectionHasPassword":true,"connectionHasSsl":true}
[PASS] klient StackExchange.Redis jest połączony (IsConnected)
[PASS] endpoint wygląda jak host:port kontenera (nie localhost:6379 na sztywno) (Unspecified/localhost:34133)
[PASS] Aspire wstrzyknął connection string z hasłem (bez podawania go w kodzie)
[PASS] Aspire wstrzyknął connection string z TLS (ssl=true)
[PASS] PUT /cache/{key} -> 200 (OK)
GET /cache/prasowka:test:f0c0539e -> {"key":"prasowka:test:f0c0539e","value":"wpis z Cache.Verify 2026-09-28T01:25:05.9538690+00:00"}
[PASS] odczytana wartość == zapisana wartość (round-trip przez realny Redis)
[PASS] brakujący klucz -> 404 (NotFound)
=== Zatrzymywanie AppHost (Aspire zdejmuje kontener Redis) ===
WSZYSTKO OK
```

Po zakończeniu `docker ps -a` nie pokazuje żadnego kontenera `cache-*` — sprzątnięty
automatycznie przez Aspire (`StopAsync`).

## Jak podejrzeć, co naprawdę robi kontener (opcjonalnie, ręcznie)

Test trwa kilka-kilkanaście sekund, więc żeby złapać kontener w locie, uruchom
`dotnet run` w tle i w drugim terminalu:

```bash
docker ps --format "{{.Names}} {{.Image}}"
docker inspect <nazwa-kontenera> --format "{{.Config.Cmd}}"
docker inspect <nazwa-kontenera> --format "{{.Config.Env}}"
```

Tak właśnie potwierdzono w artykule obraz `redis:8.6`, `--requirepass $REDIS_PASSWORD`
i flagi TLS — nie z dokumentacji, tylko z żywego kontenera.

## Ręcznie (niezweryfikowane)

```bash
dotnet run --project AppHost --launch-profile http
```

Otwiera dashboard Aspire (adres w output) — **nie sprawdzaliśmy** tego trybu w tym
wydaniu (patrz "Czego dziś NIE sprawdziliśmy" w artykule): dashboard, trwałość danych
(`WithDataVolume`), `redis-cli` z zewnątrz.

## Porządek

Test sam zatrzymuje AppHost i usuwa kontener Redis. Katalogi `bin/`, `obj/` są
w `.gitignore` repo. Obraz Dockera (`redis:8.6`, pobrany wcześniej dla innych celów
na tej maszynie, oraz ręcznie pobrany na próbę `redis:7-alpine`, ~58 MB) **zostaje w
lokalnym cache Dockera** — to nie jest artefakt tego kodu, tylko obraz, z którego
korzysta `dotnet run`; nie jest częścią repo ani nie wpływa na `git status`.
