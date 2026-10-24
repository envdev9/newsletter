<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #13 — 6 października 2026

![.NET Aspire](https://img.shields.io/badge/.NET_Aspire-512BD4?style=for-the-badge)
![TUnit](https://img.shields.io/badge/TUnit-2EA44F?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)

## Ile AppHostów naprawdę żyje w Twojej sesji testowej? Zmierzyliśmy `docker ps`

</div>

---

> _"`SharedType.PerClass` i `SharedType.PerTestSession` różnią się o jeden kontener Docker.
> Tym razem nie wierzymy dokumentacji — liczymy kontenery."_

Wczoraj (wydanie #12) zbudowaliśmy fixture TUnit owijający `DistributedApplicationTestingBuilder`
i dali go jednej klasie przez `SharedType.PerClass`. Zostały dwa pytania, które sami zapisaliśmy
jako "niezbadane":

1. Czy dwie **różne klasy** z `SharedType.PerTestSession` faktycznie dzielą **jeden** kontener?
2. Co się stanie, gdy dwa AppHosty z **tą samą nazwą zasobu** (`AddRedis("cache")`) żyją naraz?
3. (bonus) Czy kontener znika, gdy test **się wywala**?

Odpowiedzi poniżej są zmierzone — `docker ps` z wnętrza testu, plik logu cyklu życia fixture'a
i `docker ps -a` po przebiegu. Środowisko: Docker Engine `29.1.3`, Aspire `13.5.2`,
TUnit `1.72.16`, .NET SDK `10.0.400`, Linux.

---

### 1. Jedna instancja fixture'a, trzy klasy — instrumentacja zamiast wiary

Fixture z #12 dostał dwie rzeczy: własne `Id` (6 znaków z GUID-a) i statyczne liczniki
`Starts`/`Disposes`. Do tego pomocnik, który pyta Dockera, ile kontenerów `cache-*` żyje
w tej chwili (`docker ps --filter name=cache-`).

```csharp
[ClassDataSource<RedisAppHostFixture>(Shared = SharedType.PerTestSession)]
public class SessionWriteTests(RedisAppHostFixture fixture) { /* ... */ }

[ClassDataSource<RedisAppHostFixture>(Shared = SharedType.PerTestSession)]
public class SessionInfoTests(RedisAppHostFixture fixture) { /* ... */ }

// ten sam typ, ale inny zakres:
[ClassDataSource<RedisAppHostFixture>(Shared = SharedType.PerClass)]
public class OwnFixtureTests(RedisAppHostFixture fixture) { /* ... */ }
```

Hak `[After(TestSession)]` wypisuje podsumowanie. Prawdziwy wynik (przebieg #2 z dwóch):

```
=== Fixture.Starts = 2 (Disposes dotąd: 2) ===
fixture 35fffb: używany przez SessionInfoTests, SessionWriteTests
fixture 0114bc: używany przez OwnFixtureTests
=== Maks. liczba kontenerów 'cache-*' widzianych naraz w docker ps: 2 ===
Health_On_Own_AppHost: 2 kontener(y): cache-vnesvmup, cache-tqhemjeq
Put_Then_Get_Roundtrips: 2 kontener(y): cache-vnesvmup, cache-tqhemjeq
Redis_Is_Connected_Master: 2 kontener(y): cache-vnesvmup, cache-tqhemjeq

Test run summary: Passed!
  total: 3 / failed: 0 / succeeded: 3
  duration: 29s 459ms
```

Co z tego wynika:

- **`PerTestSession` = jedna instancja na dwie klasy.** Obie klasy zobaczyły to samo `Id`
  (`35fffb`). To dowód, że TUnit wstrzyknął ten sam obiekt, a więc jeden AppHost i jeden Redis.
- **`PerClass` na tym samym typie = osobna instancja**, czyli kolejny AppHost. Razem
  `Starts == 2`, nie 3 (przy `SharedType.None` spodziewałbym się 3, po jednym na test — tego wariantu nie mierzyłem).
- **Dwa AppHosty z identyczną nazwą zasobu `cache` żyją naraz bez kolizji.** Odpowiedź na
  pytanie 2 z wczoraj: Aspire dokleja losowy sufiks do nazwy kontenera (`cache-vnesvmup`
  vs `cache-tqhemjeq`), więc logiczna nazwa w kodzie nie jest nazwą w Dockerze. Porty też
  się nie pobiły (oba AppHosty działały, wszystkie 3 testy zielone). Powtórzone dwukrotnie:
  oba przebiegi 3/3, `Starts == 2`, max 2 kontenery.

**Dlaczego to ważne:** zakres fixture'a to w Aspire decyzja finansowa — każda dodatkowa
instancja to kolejny kontener, kolejny proces `CacheApi` i kolejne kilkanaście sekund
(patrz niżej). W dużej suicie przypadkowe `PerClass` zamiast `PerTestSession` mnoży koszt
przez liczbę klas.

### 2. Haczyk zmierzony #1: sprzątanie jest wolne — ok. 14 s na AppHosta

Plik `fixture-lifecycle.log` (pisany z `InitializeAsync`/`DisposeAsync`) z pierwszego
przebiegu:

```
00:51:27.805 InitializeAsync fixture=5551f1
00:51:27.805 InitializeAsync fixture=2abb74
00:51:45.049 DisposeAsync START fixture=5551f1
00:51:46.077 DisposeAsync START fixture=2abb74
00:51:58.850 DisposeAsync END fixture=5551f1
00:51:59.625 DisposeAsync END fixture=2abb74
```

Oba AppHosty wystartowały w tej samej milisekundzie (TUnit inicjalizuje fixture'y
równolegle), a każde `StopAsync` + `DisposeAsync` trwało około 13,8 s. Całość testu to ~30 s,
z czego same testy zajmują 1-3 s. **Większość czasu suity z Aspire to cykl życia, nie testy**
— to kolejny argument za jedną instancją na sesję.

### 3. Haczyk zmierzony #2: szum `Unobserved task exception` przy każdym Dispose

Przy zatrzymaniu AppHosta na stderr pojawia się seria takich komunikatów (kilka do
kilkunastu; liczby nie zliczałem dokładnie, a w obu przebiegach wyglądały inaczej):

```
Unobserved task exception: System.AggregateException: ... (The request was aborted.)
 ---> System.IO.IOException: The request was aborted.
   at System.Net.Http.Http2Connection.ThrowRequestAborted(...)
   at k8s.LineSeparatedHttpContent.CancelableStream.ReadAsync(...)
```

Stos wskazuje na klienta `k8s` (Aspire gada z DCP — własnym orkiestratorem — po HTTP/2
w stylu API Kubernetesa), którego otwarte strumienie "watch" są przerywane przy zamykaniu.
Testy przechodzą, kod wyjścia jest 0, ale **nie filtruj logów CI po słowie "exception"**
— dostaniesz fałszywy alarm (ta sama lekcja co `ERROR: database already exists` z #7).
To wnioskowanie ze stosu wywołań, nie zbadana przyczyna po stronie Aspire; poza tym
komunikat `External span cap of 100 reached` z wczoraj wrócił bez zmian.

### 4. Haczyk zmierzony #3: test, który się wywala, nie zostawia kontenera

Klasa `SabotageTests` z `[Explicit]` i `[Category("Sabotage")]` startuje AppHosta, sprawdza
`/health`, a potem rzuca wyjątek **przy żywym kontenerze**. Zwykłe uruchomienie ją pomija
(stąd `total: 3` wyżej — `[Explicit]` działa). Uruchomiona filtrem
`--treenode-filter "/*/*/*/*[Category=Sabotage]"`:

```
Kontenery w trakcie testu: cache-vdtvskub
failed Fails_On_Purpose_With_Running_Container (105ms)
  TUnit.Engine.Exceptions.TestFailedException: [Test Failure] InvalidOperationException:
  Celowa porażka testu przy żywym kontenerze Redis.
=== Fixture.Starts = 1 (Disposes dotąd: 1) ===
Test run summary: Failed!
  total: 1 / failed: 1 / succeeded: 0   (exit code 2)
```

Po przebiegu `docker ps -a` pokazał **wyłącznie kontenery, które istniały przed testem**
(cudze, nie ruszane) — `cache-vdtvskub` zniknął. `fixture-lifecycle.log` ma parę
`InitializeAsync` / `DisposeAsync START` / `END` dla tej instancji. Czyli: porażka testu
nie omija `DisposeAsync` fixture'a. Zwróć uwagę na kolejność w logu: `Disposes dotąd: 1`
wypisało się z hooka `[After(TestSession)]` — **fixture sesyjny jest zdisposowany, zanim
odpali się hook końca sesji**. Jeśli w tym hooku będziesz chciał dotknąć AppHosta, jest już
martwy.

**Dlaczego to ważne:** obawa "wywalony test zostawi śmieci w Dockerze" jest dla tego wzorca
(fixture z `IAsyncDisposable`) bezpodstawna. Nie dotyczy to twardego zabicia procesu
testowego (Ctrl+C w złym momencie, OOM) — tego nie testowaliśmy.

---

### Co dziś zostało na maszynie

Test używał kontenerów Redis wyłącznie tworzonych przez własny przebieg i Aspire usuwał je
sam; `docker ps -a` po wszystkich przebiegach pokazuje tylko dwa cudze kontenery sprzed
testu. Żadnych obrazów nie pobierano ani nie usuwano (`redis` był w cache z wydania #5),
niczego cudzego nie kasowano. Uwaga: **nie zrobiłem migawki `docker volume ls` przed
testem**, więc nie udowodnię, że obraz Redisa nie zostawił anonimowych woluminów
(obraz deklaruje `VOLUME /data`); nie ruszałem żadnych woluminów.

### Czego dziś NIE sprawdziliśmy (uczciwie)

- **`dotnet test` w tym wydaniu.** Środowisko, w którym pracowałem, nie pozwala zrobić `cd`
  do `code/`, a `global.json` z `"runner": "Microsoft.Testing.Platform"` jest brany z
  bieżącego katalogu — z korzenia repo `dotnet test` kończy się błędem VSTest/MTP,
  a `dotnet test --project` bez tego pliku daje `MSB1001`. Wszystkie wyniki wyżej pochodzą
  z `dotnet run --project ...Cache.AppHostTests.csproj -- --output Detailed` (projekt MTP
  jest zwykłym exe) — to ten sam runner. Komenda `dotnet test` z `code/` w README jest
  identyczna jak w wydaniu #12, ale tym razem jej nie odpalałem.
- **`SharedType.Keyed`** — tylko `PerTestSession` i `PerClass`.
- **Dashboard Aspire** — nadal nieobejrzany (testy go nie wystawiają).
- **`WithDataVolume` + migracje EF Core, user-secrets z prawdziwym menedżerem sekretów.**
- Twarde zabicie procesu testowego a osierocone kontenery.
- Tylko Linux i jedna wersja każdego pakietu.

### Następny krok

`SharedType.Keyed` (kilka AppHostów o różnych konfiguracjach w jednej sesji), dashboard
przy `dotnet run` (wizualna inspekcja), `WithDataVolume` + EF Core migracje.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Wymaga działającego Dockera.

---

<div align="center">

[← wydanie #13 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
