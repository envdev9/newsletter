<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #12 — 5 października 2026

![.NET Aspire](https://img.shields.io/badge/.NET_Aspire-512BD4?style=for-the-badge)
![TUnit](https://img.shields.io/badge/TUnit-2EA44F?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)

## AppHost pod testem TUnit — jeden kontener, cztery testy na raz, zero kolizji

</div>

---

> _"`[After(Class)]` jest statyczny. Fixture, który dzierży żywy kontener Redis, jest
> instancyjny. Te dwa światy się nie widzą bezpośrednio — trzeba je ręcznie zeszyć."_

Dotychczas każde wydanie tej rubryki testowało AppHosta **gołym runnerem testowym**:
`Program.cs` typu top-level statements, własna pętla `Check(...)`, ręczny
`try`/`finally` wokół `StartAsync`/`StopAsync`. Działało, ale czytelnik znający już
TUnit (hooki `[Before]`/`[After]`, `[ClassDataSource<T>]`, `SharedType`, wiele
projektów testowych w jednym `dotnet test` — patrz dzisiejsze wydanie #12 tej rubryki)
musiał się zastanawiać: *a co, gdyby AppHosta testować tak, jak wszystko inne?*

Dziś: dokładnie to. `DistributedApplicationTestingBuilder` (znany z #3/#4/#5/#7) owinięty
w fixture TUnit (`IAsyncInitializer`/`IAsyncDisposable`, znane z TUnit #3) i wstrzykiwany
przez `[ClassDataSource<RedisAppHostFixture>(Shared = SharedType.PerClass)]` — **jeden
realny kontener Redis, start raz, cztery testy `[Test]` na nim, TUnitowa asercja
`await Assert.That(...)` na każdym**. Zweryfikowane dwukrotnie, realnym Dockerem:

```
Test run summary: Passed!
  total: 4
  failed: 0
  succeeded: 4
  skipped: 0
  duration: 27s 854ms
```

Identyczny wynik w obu przebiegach (28,4 s i 27,9 s). Docker Engine `29.1.3`,
Aspire `13.5.2`, TUnit `1.72.16` (ta sama wersja, co w dzisiejszym wydaniu TUnit),
.NET SDK `10.0.400`.

---

### 1. Fixture: Aspire + `IAsyncInitializer`, nie `Main` + `try`/`finally`

```csharp
public sealed class RedisAppHostFixture : IAsyncInitializer, IAsyncDisposable
{
    private DistributedApplication? _app;
    public int InitializeCount { get; private set; }

    public async Task InitializeAsync()
    {
        InitializeCount++;

        var appHost = await DistributedApplicationTestingBuilder.CreateAsync<Projects.AppHost>(
            ["Logging:LogLevel:Default=Warning"]);
        _app = await appHost.BuildAsync();
        await _app.StartAsync();

        await _app.ResourceNotifications.WaitForResourceHealthyAsync("cache-api");
    }

    public HttpClient CreateHttpClient() => _app!.CreateHttpClient("cache-api");

    public async ValueTask DisposeAsync()
    {
        if (_app is null) return;
        await _app.StopAsync();
        await _app.DisposeAsync();
    }
}
```

Nic z tego nie jest nowe pojedynczo — `DistributedApplicationTestingBuilder` znamy od
#3, `IAsyncInitializer`/`IAsyncDisposable` jako wzorzec fixture'a znamy z TUnit #3.
Nowe jest **połączenie**: ten sam interfejs, który do teraz owijał
`WebApplicationFactory` (TUnit #5/#7/#9), tu owija **cały rozproszony system Aspire**
— AppHost + kontener Docker + projekt `.csproj` pod nim. TUnit nie wie i nie musi
wiedzieć, że pod `IAsyncInitializer` stoi `docker run`, nie `TestServer` w pamięci.

### 2. Klasa testowa: `[ClassDataSource<T>]` dokładnie jak z `WebApplicationFactory`

```csharp
[ClassDataSource<RedisAppHostFixture>(Shared = SharedType.PerClass)]
public class CacheApiAppHostTests(RedisAppHostFixture fixture)
{
    [Test]
    public async Task Put_Then_Get_Roundtrips_Through_Real_Redis()
    {
        using var http = fixture.CreateHttpClient();
        var key = "tunit:" + Guid.NewGuid().ToString("N")[..8];
        var written = "wpis-" + Guid.NewGuid().ToString("N")[..8];

        var put = await http.PutAsync($"/cache/{key}", new StringContent(written));
        var getBody = await http.GetStringAsync($"/cache/{key}");
        var read = JsonDocument.Parse(getBody).RootElement.GetProperty("value").GetString();

        await Assert.That(read).IsEqualTo(written);
    }
    // + Health_Endpoint_Returns_Healthy, Connection_String_Has_Password_And_Ssl,
    //   Missing_Key_Returns_404 — ten sam fixture, ten sam kontener.
}
```

`Shared = SharedType.PerClass` (poznany w TUnit #3 na przykładzie `FakeDatabase`)
oznacza tu coś mocniejszego niż poprzednio: **jeden kontener Docker** współdzielony
przez wszystkie testy klasy, nie jeden obiekt w pamięci. Zmierzone:
`RedisAppHostFixture.InitializeCount == 1` po całym przebiegu — AppHost wystartował
dokładnie raz, nie cztery razy po jednym na test.

### 3. Haczyk zmierzony #1: TUnit odpala te testy RÓWNOLEGLE na JEDNYM kontenerze

TUnit domyślnie uruchamia testy równolegle (poznane w TUnit #2). Nic w kodzie wyżej
tego nie wyłącza — a `[ClassDataSource<...>(Shared = SharedType.PerClass)]` dał
**jeden, współdzielony** `DistributedApplication`. Zmierzyliśmy, czy te dwa fakty
razem to w ogóle bezpieczne, logując start/koniec każdego testu:

```
Connection_String_Has_Password_And_Ssl: 01:17:20.219 -> 01:17:21.856
Health_Endpoint_Returns_Healthy:        01:17:20.220 -> 01:17:21.145
Put_Then_Get_Roundtrips_Through_Real_Redis: 01:17:20.221 -> 01:17:21.863
Missing_Key_Returns_404:                01:17:20.225 -> 01:17:21.822
ZMIERZONE: 6 par testów nakładało się w czasie na TYM SAMYM kontenerze Redis
```

Wszystkie 4 testy wystartowały w oknie **6 milisekund** od siebie i nakładały się
czasowo wszystkimi możliwymi parami (4 testy = C(4,2) = 6 par — i dokładnie 6 par się
nałożyło). To nie teoria z dokumentacji, to zmierzone znacznikami czasu: TUnit
faktycznie wysyła równoległe żądania HTTP do jednego, realnego kontenera Redis przez
Aspire, i nic się nie wywraca — **pod warunkiem, że każdy test używa własnego,
unikalnego klucza** (`Guid.NewGuid()` w `Put_Then_Get_Roundtrips_Through_Real_Redis`).
Gdyby test asercjonował coś globalnego (np. "Redis ma teraz dokładnie N kluczy"),
byłby to ten sam rodzaj bomby zegarowej, co ostrzeżenie o `SharedType.PerClass` ze
stanem globalnym z TUnit #5 — tylko przeniesiony z pamięci procesu do realnej bazy.

### 4. Haczyk zmierzony #2: `[After(Class)]` jest statyczny, fixture jest instancyjny

Chcieliśmy w `[After(Class)]` (poznanym w TUnit #7/#9) wypisać
`RedisAppHostFixture.InitializeCount`, żeby mieć dowód "AppHost wystartował raz" w
samym logu testów, nie tylko w kodzie. Pierwsza próba się nie skompilowała —
`[After(Class)]` to `static void Method(ClassHookContext context)`, a
`RedisAppHostFixture fixture` to **parametr konstruktora instancji**, niewidoczny
z metody statycznej. `ClassHookContext` nie daje uchwytu do konkretnej, współdzielonej
instancji wstrzykiwanej przez `ClassDataSource`.

Obejście: statyczne pole ustawiane w `[Before(Test)]` (który JEST instancyjny i widzi
`fixture`), czytane później w statycznym `[After(Class)]`:

```csharp
[Before(Test)]
public void CaptureInitializeCount() => CapturedInitializeCount = fixture.InitializeCount;

[After(Class)]
public static void ReportTimelineAndInitializeCount(ClassHookContext context)
{
    Console.WriteLine($"=== RedisAppHostFixture.InitializeCount = {CapturedInitializeCount} ===");
    // ...
}

private static int CapturedInitializeCount;
```

Zmierzony wynik: `RedisAppHostFixture.InitializeCount = 1` — potwierdzone w logu, nie
tylko w założeniu. Haczyk dla każdego, kto łączy fixture'y Aspire/`WebApplicationFactory`
(instancyjne z natury — jeden żywy proces/kontener na instancję) z hookami klasowymi/
assembly TUnit (statyczne z natury — jeden na całą klasę/assembly, nie na instancję):
**te dwa poziomy się nie widzą wprost, trzeba je zeszyć ręcznie przez pole statyczne.**

### Drobna, nieprzebadana obserwacja

Oba przebiegi wypisały na `stderr`:

```
[TUnit] External span cap of 100 reached; subsequent spans will be dropped.
Set TUNIT_OTEL_MAX_EXTERNAL_SPANS to raise the limit.
```

Nie wpłynęło to na wynik (4/4 PASS oba razy) i nie badaliśmy przyczyny — prawdopodobnie
wewnętrzne śledzenie OpenTelemetry w TUnit zliczające też spany generowane przez samo
Aspire (które, jak wiemy z #3, ma wbudowane OTel) trafiło w domyślny limit. Zostawiamy
to jako **niewyjaśnioną, ale nieszkodliwą** obserwację — nie zgadujemy przyczyny.

### Dlaczego to ważne w praktyce

1. **Test AppHosta nie musi żyć w osobnym, gołym `Program.cs` z ręczną pętlą asercji.**
   Ten sam `[Test]`/`await Assert.That(...)`/`[ClassDataSource<T>]`, którym testujesz
   zwykłe API (TUnit #5/#7/#9), działa identycznie na AppHoście — fixture nie wie i
   nie musi wiedzieć, że pod spodem jest Docker, nie `TestServer`.
2. **Jeden kontener na klasę testową to realna, zmierzona redukcja kosztu.** Start
   AppHosta z realnym kontenerem Redis to rząd sekund — robienie tego raz na klasę
   (nie raz na test, jak dałby domyślny `SharedType.None`) jest różnicą między
   testami, które się da odpalać za każdym commitem, i testami, które się odpuszcza.
3. **Równoległość TUnit i współdzielony zasób Docker to kombinacja bezpieczna TYLKO
   przy izolacji danych per test.** To nie jest ostrzeżenie teoretyczne — zmierzyliśmy
   realne nakładanie się w czasie (6/6 możliwych par), nie zgadywaliśmy go.
4. **Fixture instancyjny + hook statyczny to złącze, które trzeba świadomie zaprojektować.**
   Każdy, kto chce połączyć Aspire (fixture instancyjny z natury) z `[AfterEvery]`/
   `[After(Class)]` TUnit (statyczne z natury), natrafi na tę samą granicę.

### Czego dziś NIE sprawdziliśmy (uczciwie)

- **Dashboard Aspire** — po raz kolejny nieobejrzany wizualnie; `DistributedApplicationTestingBuilder`
  w ogóle nie wystawia dashboardu w trybie testowym, więc ten wątek z poprzednich
  wydań pozostaje otwarty tylko dla `dotnet run`, nie dla testów.
- **`SharedType.PerTestSession`/`Keyed` z Aspire** — użyliśmy tylko `PerClass`; czy
  dwie klasy testowe z `PerTestSession` faktycznie współdzielą JEDEN kontener między
  sobą (analogicznie do TUnit #7 z `WebApplicationFactory`) — niezbadane dziś.
  Potencjalnie ryzykowne: dwa AppHosty w `PerTestSession` próbujące tego samego
  `builder.AddRedis("cache")` to potencjalnie dwa kontenery o tej samej logicznej
  nazwie zasobu — niesprawdzone, czy Aspire by to obsłużyło bezkolizyjnie.
  Użyliśmy Redis (lekki, obraz już w cache z wydania #5), nie Postgres z
  `WithDataVolume()` — kombinacja "TUnit + trwały wolumin" to wciąż osobny,
  niezbadany temat.
- **Przyczyna `External span cap of 100 reached`** — zaobserwowana, nieszkodliwa,
  nieprzebadana (patrz wyżej).
- **Zachowanie przy porażce testu w trakcie** — wszystkie 4 testy przeszły w obu
  przebiegach; nie sprawdziliśmy, czy `DisposeAsync` fixture'a (i sprzątanie
  kontenera przez Aspire) odpala się poprawnie, gdy jeden z testów we wspólnej
  klasie faktycznie się wywali.
- Tylko Linux, Docker Engine `29.1.3`, Aspire `13.5.2`, TUnit `1.72.16`, .NET SDK `10.0.400`.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Wymaga działającego Dockera.

---

<div align="center">

[← wydanie #12 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
