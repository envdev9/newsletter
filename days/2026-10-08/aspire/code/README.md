# Kod do wydania #15 — .NET Aspire: `ContainerLifetime.Persistent`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Wymagania

- **.NET 10 SDK** (sprawdzone na `10.0.400`), Aspire `13.5.2`.
- **Docker** (Docker Engine `29.1.3`) — demon musi odpowiadać (`docker info`). Obraz `redis`
  (domyślny tag `AddRedis`) zostanie pobrany przy pierwszym uruchomieniu, jeśli go nie ma.
- **Linux** (probe używa `ps` i `kill`). Nie sprawdzano na Windows/macOS.
- Jeśli `dotnet` nie jest w PATH: `export PATH="$HOME/.dotnet:$PATH"`.
- To zwykła aplikacja konsolowa (`dotnet run`), bez TUnit i bez `global.json`.

## Fragment prasówki, którego dotyczy ten kod

> Jedna zmiana w AppHoście: `builder.AddRedis("cache").WithLifetime(ContainerLifetime.Persistent)`.
> `Persist.Probe` uruchamia kolejne procesy potomne z prawdziwym AppHostem: zapis klucza przez
> `CacheApi`, zamknięcie hosta (`StopAsync`+`DisposeAsync`), odczyt z NOWEGO AppHosta, zapis i
> `kill -9` hosta, kolejny odczyt. Wynik: kontener `cache-<hash>` ma to samo ID i ten sam czas
> startu we wszystkich krokach, dane przeżywają zarówno czyste zamknięcie, jak i `kill -9`,
> a `dcp`/`CacheApi` znikają. Kontrola z domyślnym `Session`: kontener znika, odczyt
> z następnego AppHosta zwraca 404. Trwały kontener sprzątasz sam (`docker rm -f`).

## Struktura

```
code/
├── AppHost/         # AddRedis("cache") [+ WithLifetime(Persistent)] + CacheApi
├── CacheApi/        # PUT/GET /cache/{key}, /health
└── Persist.Probe/   # rodzic + potomek (Program.cs) - scenariusze A (Persistent) i B (Session)
```

Argument konfiguracyjny `Persistent=false` (przekazywany przez probe do AppHosta) wyłącza
`WithLifetime(Persistent)`; domyślnie jest włączone.

## Uruchomienie

Z dowolnego katalogu (ok. 5 minut, bo po każdym kroku jest 25 s przerwy na ustabilizowanie):

```bash
dotnet run --project code/Persist.Probe/Persist.Probe.csproj
```

Probe na końcu sam usuwa kontenery, sieci, woluminy i procesy `dcp*`/`CacheApi`, które pojawiły
się po jego starcie (migawka przed/po). **Trwały kontener Aspire nie zniknie sam**, więc jeśli
przerwiesz przebieg Ctrl+C, posprzątaj ręcznie kontener `cache-*` swojego przebiegu
(`docker ps -a`, potem `docker rm -f <nazwa>`) — uważaj, by nie usunąć cudzych.

Zmierzony wynik (Docker 29.1.3, Aspire 13.5.2, .NET SDK 10.0.400, Linux; skrót, 2 przebiegi
identyczne co do wniosków):

```
A1 write         -> kontener cache-4ab92b86 id=b3850491fd92 running; po 25 s od śmierci hosta (exit 0): ten sam id, running
A2 read          -> {"key":"persist-key","value":"v1-..."}   (nowy AppHost, ten sam kontener, ten sam startedAt)
A3 write + kill -9 hosta -> po 25 s: ten sam id, running
A4 read          -> {"key":"persist-key","value":"v2-..."}   (dane sprzed kill -9)
B1 write (Session)  -> po 25 s: kontener (brak)
B2 read  (Session)  -> MISSING (404), nowy kontener o innej nazwie
```

Uwaga: w kolumnie "procesy, które żyją" widać też procesy kontenera widoczne z hosta
(`redis-server`, `containerd-shim`, `docker-proxy`) oraz szum z innych procesów maszyny
(`qmgr`, `pickup`, `bash`, `flock`) — probe porównuje migawki procesów, nie filtruje po właścicielu.
Katalogi `bin/`, `obj/` wyklucza `code/.gitignore`.
