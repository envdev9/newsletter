# Kod do wydania #12 — .NET Aspire: test AppHosta w TUnit

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Wymagania

- **.NET 10 SDK** (sprawdzone na `10.0.400`), pakiety Aspire `13.5.2` z nuget.org.
- **TUnit `1.72.16`** (ta sama wersja, co w dzisiejszym wydaniu rubryki TUnit).
- **Docker** (sprawdzone na Docker Engine `29.1.3`) — demon musi odpowiadać
  (`docker info`). Ten kod **realnie uruchamia kontener Redis** przez Docker, nie atrapę.
- Obraz Redisa (domyślny tag `AddRedis` w Aspire `13.5.2`, zmierzony w wydaniu #5 jako
  `redis:8.6`, ~205 MB) — jeśli nie jest jeszcze w lokalnym cache Dockera, `dotnet test`
  go pobierze przy pierwszym uruchomieniu.
- Jeśli `dotnet` nie jest w PATH: `export PATH="$HOME/.dotnet:$PATH"`.

## Fragment prasówki, którego dotyczy ten kod

> `DistributedApplicationTestingBuilder` (znany z poprzednich wydań) owinięty w
> fixture TUnit (`IAsyncInitializer`/`IAsyncDisposable`) i wstrzykiwany przez
> `[ClassDataSource<RedisAppHostFixture>(Shared = SharedType.PerClass)]` — jeden
> realny kontener Redis, start raz na całą klasę testową, cztery testy `[Test]`
> odpalone na nim, asercje `await Assert.That(...)`. TUnit domyślnie uruchamia te
> testy równolegle — zmierzone znacznikami czasu: wszystkie 4 testy nakładają się
> czasowo (6 z 6 możliwych par), bezpiecznie, bo każdy test używa własnego,
> unikalnego klucza Redis. `[After(Class)]` jest statyczny, a fixture instancyjny —
> żeby w hooku klasowym odczytać stan fixture'a (`InitializeCount`), trzeba go
> przemycić przez statyczne pole ustawiane w `[Before(Test)]`.

## Struktura

```
code/
├── global.json              # "test": { "runner": "Microsoft.Testing.Platform" }
├── AppHost/                  # AddRedis("cache") + AddProject<Projects.CacheApi>, WithReference/WaitFor
├── CacheApi/                  # PUT/GET /cache/{key} przez StackExchange.Redis, /cache-info, /health
└── Cache.AppHostTests/         # projekt TUnit: RedisAppHostFixture + CacheApiAppHostTests
    ├── RedisAppHostFixture.cs  # IAsyncInitializer/IAsyncDisposable owijające DistributedApplicationTestingBuilder
    └── CacheApiAppHostTests.cs # [ClassDataSource<RedisAppHostFixture>(Shared = SharedType.PerClass)], 4 testy
```

## Uruchomienie

Wymaga działającego Dockera (`docker info` musi się powieść). Z katalogu `code/`:

```bash
dotnet test Cache.AppHostTests/Cache.AppHostTests.csproj --output Detailed
```

Kod wyjścia 0 = sukces. Prawdziwy wynik (SDK `10.0.400`, Aspire `13.5.2`,
TUnit `1.72.16`, Docker `29.1.3`, Linux), zmierzony w tym repo — **dwa niezależne
przebiegi, identyczny wzorzec w obu**:

```
passed Health_Endpoint_Returns_Healthy (991ms)
passed Missing_Key_Returns_404 (1s 655ms)
passed Put_Then_Get_Roundtrips_Through_Real_Redis (1s 677ms)
passed Connection_String_Has_Password_And_Ssl (1s 682ms)
  Standard output
    === RedisAppHostFixture.InitializeCount = 1 ===
    === Linia czasu testów na WSPÓLNYM kontenerze Redis ===
    Connection_String_Has_Password_And_Ssl: 01:17:20.219 -> 01:17:21.856
    Health_Endpoint_Returns_Healthy:        01:17:20.220 -> 01:17:21.145
    Put_Then_Get_Roundtrips_Through_Real_Redis: 01:17:20.221 -> 01:17:21.863
    Missing_Key_Returns_404:                01:17:20.225 -> 01:17:21.822
    ZMIERZONE: 6 par testów nakładało się w czasie na TYM SAMYM kontenerze Redis (...)

Test run summary: Passed!
  total: 4
  failed: 0
  succeeded: 4
  skipped: 0
  duration: 27s 854ms
```

Oba przebiegi wypisały też na `stderr` nieszkodliwy, niewyjaśniony komunikat:
`[TUnit] External span cap of 100 reached; subsequent spans will be dropped.` —
zobacz artykuł, sekcja "Drobna, nieprzebadana obserwacja".

## Porządek po teście

**Nic do ręcznego sprzątania.** W odróżnieniu od wydania #7 (Postgres +
`WithDataVolume()`), ten kod **nie** używa trwałego woluminu — `AddRedis("cache")`
bez `WithDataVolume()` to efemeryczny kontener, który Aspire usuwa automatycznie przy
`app.StopAsync()` (wołanym w `RedisAppHostFixture.DisposeAsync()`, czyli po ostatnim
teście klasy). Zweryfikowane: `docker ps -a` i `docker volume ls` pokazują identyczny
stan przed i po obu przebiegach testu — zero nowych kontenerów, zero nowych woluminów.
Obraz Redisa zostaje w lokalnym cache Dockera (nie w repo, nie pobierany ponownie przy
kolejnych przebiegach) — w tym repo był już w cache z wydania #5 (2026-09-28), więc
dzisiejsza weryfikacja nie pobierała nic z sieci.

Katalogi `bin/`, `obj/`, `TestResults/` są w `.gitignore` repo.
