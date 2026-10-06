# Kod do wydania #13 — .NET Aspire: ile AppHostów żyje w sesji TUnit

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Wymagania

- **.NET 10 SDK** (sprawdzone na `10.0.400`), Aspire `13.5.2`, **TUnit `1.72.16`**.
- **Docker** (Docker Engine `29.1.3`) — demon musi odpowiadać (`docker info`). Kod realnie
  uruchamia kontenery Redis. Obraz `redis` (domyślny tag `AddRedis`) zostanie pobrany przy
  pierwszym uruchomieniu, jeśli go nie ma.
- Jeśli `dotnet` nie jest w PATH: `export PATH="$HOME/.dotnet:$PATH"`.

## Fragment prasówki, którego dotyczy ten kod

> Fixture TUnit owijający `DistributedApplicationTestingBuilder` dostał własne `Id`
> i liczniki `Starts`/`Disposes`. Dwie różne klasy z
> `[ClassDataSource<RedisAppHostFixture>(Shared = SharedType.PerTestSession)]` dostały
> TĘ SAMĄ instancję (jeden AppHost, jeden Redis); klasa z `SharedType.PerClass` dostała
> osobną, więc w `docker ps` żyły naraz 2 kontenery `cache-*` (Aspire dokleja losowy
> sufiks, więc ta sama nazwa zasobu `cache` nie koliduje). Sprzątanie jednego AppHosta
> trwa ok. 14 s i generuje szum `Unobserved task exception` (klient `k8s` w DCP).
> Test celowo wywalony (`[Explicit]`, filtr po kategorii) nie omija `DisposeAsync` —
> kontener znika.

## Struktura

```
code/
├── global.json                 # "test": { "runner": "Microsoft.Testing.Platform" }
├── AppHost/                    # AddRedis("cache") + CacheApi
├── CacheApi/                   # PUT/GET /cache/{key}, /cache-info, /health
└── Cache.AppHostTests/
    ├── RedisAppHostFixture.cs  # fixture + Id, liczniki, log cyklu życia, docker ps
    ├── SessionTests.cs         # 2x PerTestSession, 1x PerClass, [After(TestSession)] z podsumowaniem
    └── SabotageTests.cs        # [Explicit] test, który celowo się wywala
```

## Uruchomienie

Z katalogu `code/` (tu leży `global.json` wymagany przez `dotnet test` na SDK 10):

```bash
dotnet test --project Cache.AppHostTests/Cache.AppHostTests.csproj --output Detailed
```

> Uwaga: w środowisku, w którym powstało wydanie, nie dało się wejść do `code/`, więc
> powyższej komendy NIE odpalono. Zweryfikowano równoważne (ten sam runner MTP):
>
> ```bash
> dotnet run --project Cache.AppHostTests/Cache.AppHostTests.csproj -- --output Detailed
> ```

Zmierzony wynik (dwa przebiegi, identyczny wzorzec, ~30 s każdy):

```
=== Fixture.Starts = 2 (Disposes dotąd: 2) ===
fixture 35fffb: używany przez SessionInfoTests, SessionWriteTests
fixture 0114bc: używany przez OwnFixtureTests
=== Maks. liczba kontenerów 'cache-*' widzianych naraz w docker ps: 2 ===
Test run summary: Passed!
  total: 3 / failed: 0 / succeeded: 3   (duration: 29s 459ms)
```

Test sabotażowy (wywala się celowo, kod wyjścia 2; potem sprawdź `docker ps -a`):

```bash
dotnet run --project Cache.AppHostTests/Cache.AppHostTests.csproj -- --output Detailed --treenode-filter "/*/*/*/*[Category=Sabotage]"
```

Log cyklu życia fixture'a: `Cache.AppHostTests/bin/Debug/net10.0/fixture-lifecycle.log`
(dopisywany przy każdym przebiegu).

## Porządek po teście

Kontenery Redis usuwa Aspire (`StopAsync` w `DisposeAsync`) — także po teście, który się
wywalił. Weryfikacja: `docker ps -a` po przebiegach pokazywał tylko kontenery sprzed testu.
Katalogi `bin/`, `obj/`, `TestResults/` wyklucza `code/.gitignore`.
