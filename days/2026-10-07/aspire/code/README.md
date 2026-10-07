# Kod do wydania #14 — .NET Aspire: co zostaje po `kill -9` hosta

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Wymagania

- **.NET 10 SDK** (sprawdzone na `10.0.400`), Aspire `13.5.2`.
- **Docker** (Docker Engine `29.1.3`) — demon musi odpowiadać (`docker info`). Obraz `redis`
  (domyślny tag `AddRedis`) zostanie pobrany przy pierwszym uruchomieniu, jeśli go nie ma.
- **Linux** (probe używa `ps` i `kill`). Nie sprawdzano na Windows/macOS.
- Jeśli `dotnet` nie jest w PATH: `export PATH="$HOME/.dotnet:$PATH"`.
- Nie ma tu testów TUnit ani `global.json` — to zwykła aplikacja konsolowa (`dotnet run`).

## Fragment prasówki, którego dotyczy ten kod

> Proces-potomek stawia prawdziwego AppHosta (Redis w Dockerze + `CacheApi`), melduje `READY`
> i umiera na siedem sposobów: `clean`, `exit`, `crash` (SIGABRT), `sigterm`, `sigint`,
> `sigkill` i `sigkill-all` (SIGKILL hosta oraz procesów `dcp*` jednocześnie). Rodzic mierzy,
> co jeszcze żyje. Po `kill -9` samego hosta kontener Redis znika po ok. 12 s, a procesy
> `dcp`/`CacheApi` po ok. 15 s — tak samo jak przy czystym `DisposeAsync`: sprząta DCP, nie
> Twój kod. Po zabiciu także `dcp*` kontener, sieć i `CacheApi` zostają (sieroty), a następny
> AppHost sprząta kontener i sieć, lecz nie procesy `CacheApi`/`dotnet`.

## Struktura

```
code/
├── AppHost/            # AddRedis("cache") + CacheApi (jak w #12/#13)
├── CacheApi/           # PUT/GET /cache/{key}, /health
└── Orphan.Probe/       # rodzic + potomek (Program.cs) - pomiar sierot
```

## Uruchomienie

Z dowolnego katalogu (pełny przebieg ok. 6 min, bo `sigterm`, `sigint` i `sigkill-all`
czekają po 90 s):

```bash
dotnet run --project code/Orphan.Probe/Orphan.Probe.csproj -- parent clean exit crash sigterm sigint sigkill sigkill-all
```

Można podać podzbiór trybów, np. tylko `... -- parent sigkill`. Tabela idzie na stdout,
diagnostyka (nazwy kontenerów, pidy, etykiety) na stderr.

Zmierzony wynik (Docker 29.1.3, Aspire 13.5.2, .NET SDK 10.0.400, Linux):

```
| tryb        | kod wyjścia | potomek kończy się po | kontener Redis znika po | procesy DCP/CacheApi znikają po |
| clean       | 0           | 13.9 s                | 11.8 s                  | 14.9 s                          |
| exit        | 0           | 0.0 s                 | 12.7 s                  | 15.3 s                          |
| crash       | 134         | 0.0 s                 | 12.1 s                  | 15.2 s                          |
| sigterm     | (żyje)      | NIE (90 s)            | 12.4 s                  | 15.5 s                          |
| sigint      | (żyje)      | NIE (90 s)            | 12.2 s                  | 15.3 s                          |
| sigkill     | 137         | 0.7 s                 | 12.0 s                  | 15.1 s                          |
| sigkill-all | 137         | 0.6 s                 | NIE (90 s)              | NIE (90 s)   (sieć i CacheApi zostają) |
| (po sigkill-all) następny AppHost clean: kontener i sieć znikają, procesy CacheApi/dotnet zostają |
```

## Porządek po przebiegu

Probe sprząta sam i wyłącznie to, co pojawiło się po starcie potomka (kontenery, sieci
Dockera, woluminy, pidy). Mimo to po przerwanym przebiegu (Ctrl+C na rodzicu) sprawdź ręcznie
`docker ps -a`, `docker network ls` i `pgrep -a "dcp|CacheApi"` — rodzic nie obsługuje własnego
przerwania. Uwaga: probe porównuje migawki *przed* i *po*, więc na maszynie, na której
równolegle ktoś inny tworzy zasoby Dockera/procesy, mogą się one znaleźć w "swoich" pozostałościach.
Katalogi `bin/`, `obj/` wyklucza `code/.gitignore`.
