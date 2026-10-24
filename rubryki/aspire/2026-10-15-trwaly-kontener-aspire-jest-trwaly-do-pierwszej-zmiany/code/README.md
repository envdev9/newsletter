# Kod do wydania #22 — .NET Aspire: zmiana konfiguracji trwałego kontenera i `WithDataVolume`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Wymagania

- **.NET 10 SDK** (sprawdzone na `10.0.400`), Aspire `13.5.2`.
- **Docker** (Docker Engine `29.1.3`), demon musi odpowiadać (`docker info`). Obrazy `redis:8.6`
  (domyślny tag `AddRedis`) i `redis:7-alpine` zostaną pobrane, jeśli ich nie ma.
- **Linux** (probe używa `ps` i `kill`). Nie sprawdzano na Windows/macOS.
- Jeśli `dotnet` nie jest w PATH: `export PATH="$HOME/.dotnet:$PATH"`.
- Zwykła aplikacja konsolowa (`dotnet run`), bez TUnit i bez `global.json`.

## Fragment prasówki, którego dotyczy ten kod

> Zmiana zmiennej środowiskowej albo tagu obrazu w AppHoście z `ContainerLifetime.Persistent`
> powoduje, że Aspire tworzy kontener od nowa (nowe ID i czas startu, ta sama nazwa), a dane znikają.
> `WithDataVolume` dla Redisa włącza `--save 60 1`, więc zapis trafia na wolumin dopiero po oknie
> snapshotu: po `docker rm -f` lub `docker stop` (10,4 s, kod 137) w ciągu minuty od zapisu dane
> przepadają mimo woluminu; po odczekaniu 75 s wracają do nowego kontenera.

## Struktura

```
code/
├── AppHost/          # AddRedis("cache") sterowany argumentami: Mark, RedisTag, VolumeName, Persistence, Persistent
├── CacheApi/         # PUT/GET /cache/{key}, /health
└── Reconfig.Probe/   # rodzic + potomek (Program.cs) - scenariusze C (zmiana konfiguracji) i D (usunięcie kontenera)
```

## Uruchomienie

Z dowolnego katalogu (ok. 9 minut):

```bash
dotnet run --project code/Reconfig.Probe/Reconfig.Probe.csproj
```

Probe na końcu sam usuwa swoje kontenery `cache-*`, ich woluminy (nazwane `reconfig-lab-*` i
anonimowe), sieć `aspire*` oraz procesy `dcp*`/`CacheApi`, które pojawiły się po jego starcie.
Trwały kontener Aspire nie znika sam, więc po przerwaniu przebiegu (Ctrl+C) posprzątaj ręcznie:
`docker ps -a`, `docker rm -f <cache-...>`, `docker volume ls` (uważaj na cudze zasoby).

Zmierzony wynik (Docker 29.1.3, Aspire 13.5.2, SDK 10.0.400; skrót, 3 przebiegi spójne):

```
C1 write v1, Mark=m1        cache-3297b9ab id=879894eb9016 LAB_MARK=m1 image=redis:8.6
C2 read,  Mark=m1           ten sam id; {"value":"v1-..."}
C3 read,  Mark=m2           id=ea751fc7631c (nowy), LAB_MARK=m2, ta sama nazwa; MISSING (404)
C4 read,  m2 + RedisTag     id=9a7d7b7df50f (nowy), image=redis:7-alpine, anonimowy wolumin; MISSING (404)
D1 WithDataVolume, docker stop (10.4 s, kod 137) + rm   -> MISSING (404)
D2 WithDataVolume, docker rm -f zaraz po zapisie        -> MISSING (404)
D4/D5 + WithPersistence()                               -> MISSING (404), opcje nadal "--save 60 1"
D6 WithDataVolume, zapis, 75 s, docker rm -f            -> {"value":"v6-..."}   (dane z woluminu)
D3 kontrola bez woluminu                                -> MISSING (404)
```

Argumenty AppHosta (przekazywane przez probe jako `Klucz=Wartość`): `Mark`, `RedisTag`,
`VolumeName`, `Persistence=true`, `Persistent=false`. Katalogi `bin/`, `obj/` wyklucza
`code/.gitignore`.
