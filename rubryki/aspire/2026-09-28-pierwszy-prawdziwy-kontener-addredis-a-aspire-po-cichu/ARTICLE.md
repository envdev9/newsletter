<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #5 — 28 września 2026

![.NET Aspire](https://img.shields.io/badge/.NET_Aspire-512BD4?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-średnio_zaawansowany-orange?style=for-the-badge)

## Pierwszy prawdziwy kontener: `AddRedis`, a Aspire po cichu dorzuca hasło i TLS

</div>

---

> _"Nie skonfigurowałem ani hasła, ani TLS-a. Redis mimo to wymagał jednego i drugiego —
> i klient dostał obie rzeczy za darmo, przez connection string, o którym nic nie wiedziałem."_

W wydaniu #4 zabrakło Dockera z gotowymi obrazami, więc rubryka stała bez kontenerów.
Dziś to sprawdziliśmy realnie, zanim cokolwiek obiecaliśmy: `docker version`/`docker info`
odpowiadają (Docker Engine 29.1.3, 34 obrazy już w cache), a `df -h /` pokazuje **43 GB
wolnego** na 89 GB dysku. Bezpiecznie, więc dla ostrożności pociągnęliśmy najpierw lekki
`redis:7-alpine` (57,8 MB) — poszło bez problemu. Zielone światło na `AddRedis`.

Kod: [`code/`](code/). Zweryfikowane realnym `dotnet run` uruchamiającym **prawdziwy
kontener Docker** (nie atrapę) — trzy niezależne przebiegi, każdy `WSZYSTKO OK`,
kontener za każdym razem posprzątany automatycznie.

---

### 1. `AddRedis` — jedna linijka, prawdziwy kontener

```csharp
var builder = DistributedApplication.CreateBuilder(args);

var cache = builder.AddRedis("cache");

var api = builder.AddProject<Projects.CacheApi>("cache-api")
    .WithReference(cache)   // wstrzykuje ConnectionStrings:cache do cache-api
    .WaitFor(cache)         // cache-api nie startuje, dopóki kontener nie jest gotowy
    .WithHttpHealthCheck("/health");

builder.Build().Run();
```

To ten sam wzorzec `WithReference` + `WaitFor`, co w wydaniu #3 między dwoma projektami
.NET — różnica jest po drugiej stronie: `cache` to teraz **kontener Docker**, którym
Aspire zarządza całym cyklem życia (start przy `StartAsync`, `docker rm` przy zatrzymaniu).

### 2. Zaskoczenie #1: jaki obraz naprawdę startuje

Nie zgadywaliśmy — podejrzeliśmy działający kontener w trakcie testu:

```
$ docker ps --format "{{.Names}} {{.Image}}"
cache-mxnfztex redis:8.6
```

`Aspire.Hosting.Redis` 13.5.2 domyślnie używa **`redis:8.6`**, nie `7-alpine`, którego
ostrożnościowo pobraliśmy wcześniej ręcznie. Na szczęście `redis:8.6` już siedział w
lokalnym cache obrazów (nie musieliśmy go ściągać) — inaczej pierwszy `dotnet run`
zająłby dodatkowe ~200 MB i chwilę czasu na pobranie. **Wniosek praktyczny:** jeśli
chcesz kontrolować, jaki obraz/tag faktycznie wystartuje, nie polegaj na domyślnym —
sprawdź (`docker ps` w trakcie działania) albo ustaw jawnie (Aspire pozwala nadpisać tag
obrazu na zasobie kontenerowym).

### 3. Zaskoczenie #2: hasło i TLS, o które nikt nie prosił

Podejrzeliśmy też komendę startową kontenera:

```
$ docker inspect cache-mxnfztex --format "{{.Config.Cmd}}"
[-c redis-server --requirepass $REDIS_PASSWORD --tls-port 6379 --port 6380
    --tls-ca-cert-file /usr/lib/ssl/aspire/cert.pem
    --tls-cert-file /usr/lib/ssl/aspire/private/....crt
    --tls-key-file /usr/lib/ssl/aspire/private/....key
    --tls-auth-clients no]

$ docker inspect cache-mxnfztex --format "{{.Config.Env}}"
[REDIS_PASSWORD=HAs9dNaQ0q0aXCVffAvUUq SSL_CERT_DIR=... REDIS_VERSION=8.6.6]
```

Nie napisaliśmy ani jednej linijki o haśle czy TLS-ie w `AppHost.cs`. `AddRedis("cache")`
samo wygenerowało losowe hasło (`REDIS_PASSWORD`) i certyfikat TLS, wystawiło oba porty
(6379 z TLS, 6380 bez) i **wstrzyknęło gotowy connection string** do `cache-api` przez
`WithReference`. Po stronie serwisu:

```csharp
builder.AddRedisClient(connectionName: "cache");  // to wszystko - hasło i TLS już w środku
```

Zmierzone w teście (nie zgadywane) — kształt wstrzykniętego connection stringa:

```
connectionHasPassword: true
connectionHasSsl: true
```

### 4. `CacheApi` — dowód, że to naprawdę Redis, nie atrapa w pamięci

```csharp
app.MapPut("/cache/{key}", async (string key, HttpRequest req, IConnectionMultiplexer mux) =>
{
    var value = await new StreamReader(req.Body).ReadToEndAsync();
    await mux.GetDatabase().StringSetAsync(key, value);
    return Results.Ok(new { key, written = value.Length });
});

app.MapGet("/cache/{key}", async (string key, IConnectionMultiplexer mux) =>
{
    var value = await mux.GetDatabase().StringGetAsync(key);
    return value.IsNull ? Results.NotFound() : Results.Ok(new { key, value = (string)value! });
});
```

`/cache-info` dodatkowo pyta serwer Redis wprost (`GetServer(endpoint)`, `IsConnected`,
`IsReplica`) — to nie mockowany magazyn w pamięci procesu, tylko realne połączenie sieciowe
do kontenera.

### 5. `Cache.Verify` — test AppHosta, który realnie odpala Docker

Jak `Config.Verify`/`Store.Verify` z poprzednich wydań, ale tym razem
`DistributedApplicationTestingBuilder` faktycznie uruchamia kontener przez Docker (nie
udaje go):

```csharp
var appHost = await DistributedApplicationTestingBuilder.CreateAsync<Projects.AppHost>(ct);
await using var app = await appHost.BuildAsync(ct);
await app.StartAsync(ct);

await app.ResourceNotifications.WaitForResourceHealthyAsync("cache-api", ct);
// WaitFor(cache) w AppHost gwarantuje: skoro cache-api jest Healthy, Redis pod spodem żyje.

using var http = app.CreateHttpClient("cache-api");
await http.PutAsync($"/cache/{key}", new StringContent(value));
var readBack = await http.GetStringAsync($"/cache/{key}");
```

Prawdziwy wynik (trzy niezależne przebiegi, ten sam rezultat za każdym razem):

```
=== Start AppHost (kontener Redis przez Docker) ===
cache-api = Healthy (czyli kontener redis 'cache' też musiał wystartować)
GET /cache-info -> {"endpoint":"Unspecified/localhost:34133","isConnected":true,"role":"master","connectionHasPassword":true,"connectionHasSsl":true}
[PASS] klient StackExchange.Redis jest połączony (IsConnected)
[PASS] endpoint wygląda jak host:port kontenera (nie localhost:6379 na sztywno)
[PASS] Aspire wstrzyknął connection string z hasłem (bez podawania go w kodzie)
[PASS] Aspire wstrzyknął connection string z TLS (ssl=true)
[PASS] PUT /cache/{key} -> 200 (OK)
[PASS] odczytana wartość == zapisana wartość (round-trip przez realny Redis)
[PASS] brakujący klucz -> 404 (NotFound)
=== Zatrzymywanie AppHost (Aspire zdejmuje kontener Redis) ===
WSZYSTKO OK
```

Po każdym przebiegu `docker ps -a` nie pokazuje żadnego kontenera `cache-*` — Aspire
sprzątnął go w `StopAsync`, dysk (`df -h /`) wrócił do stanu sprzed testu.

### Dlaczego to ważne w praktyce

1. **Domyślne ustawienia kontenerów bywają bezpieczniejsze niż się spodziewasz** — hasło
   i TLS "za darmo" to dobra wiadomość dla dev-środowiska, ale też pułapka: jeśli Twój
   kod gdzieś zakłada `ssl=false` albo łączy się z gołym `redis:6379` bez auth, `AddRedis`
   może Cię zaskoczyć.
2. **Nie ufaj domyślnemu tagowi obrazu bez sprawdzenia** — `redis:8.6` zamiast
   spodziewanego `7-alpine` to różnica w rozmiarze pobrania i (potencjalnie) w
   zachowaniu. `docker ps` w trakcie działania to tania weryfikacja.
3. **`WaitFor(cache)` na kontenerze działa identycznie jak na projekcie** — ten sam
   mechanizm co w wydaniu #3, teraz gwarantuje, że Redis naprawdę odpowiada, zanim
   serwis dostanie ruch.
4. **Test AppHosta ujawnia zachowanie kontenera bez ręcznego `docker exec`** — całą
   powyższą wiedzę (obraz, hasło, TLS) wydobyliśmy z samego uruchomienia testu i podglądu
   Dockera obok, nie z dokumentacji.

### Czego dziś NIE sprawdziliśmy (uczciwie)

- **Dashboard Aspire** — nie otwieraliśmy go, nie widzieliśmy tam wizualnie stanu
  zasobu `cache` ani metryk Redis.
- **Trwałość danych** (`WithDataVolume`/`WithPersistence`) — używamy Redisa bez
  woluminu, dane giną z kontenerem. Nie testowaliśmy trwałości między restartami.
- **Dokładny mechanizm mapowania portów** — `docker ps` pokazywał inny port hosta
  (`32770`) niż ten, którego użył klient w procesie testu (`34133` w wypisanym
  `/cache-info`) — oba działały, ale nie zbadaliśmy, dlaczego się różnią (prawdopodobnie
  DCP/Aspire tuneluje połączenie inną drogą niż standardowy port hosta widoczny w
  `docker ps`).
- **`redis-cli`** — nie łączyliśmy się z kontenerem ręcznie z zewnątrz (i tak wymagałoby
  to podania wygenerowanego hasła i `--tls`).
- **`user-secrets`** — nadal nie ruszony wątek z wydania #4 (na kolejne wydanie).
- Tylko Linux, Docker Engine 29.1.3, Aspire 13.5.2, .NET SDK 10.0.400.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Wymaga działającego Dockera.

---

<div align="center">

[← wydanie #5 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
