<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #5 — 28 września 2026

![TUnit](https://img.shields.io/badge/TUnit-2EA44F?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-ekspert-8250DF?style=for-the-badge)

## TUnit: prawdziwe API pod testem — `WebApplicationFactory<Program>` + `[ClassDataSource]`

</div>

---

> _"Fixture, który hostuje serwer, to nie jest szczegół infrastruktury testu — to część
> kontraktu, który test sprawdza."_

Cztery wydania uczyły asercji, hooków, danych i retry na przykładach syntetycznych. Dziś
łączymy je w jeden realny scenariusz: **prawdziwe minimalne API ASP.NET Core** hostowane
w pamięci przez `WebApplicationFactory<Program>`, testowane przez TUnit zamiast xUnit.
Sprawdzone na `.NET SDK 10.0.400`, `TUnit 1.70.1` (nowsza niż 1.69.0 z poprzednich wydań —
zweryfikowane na NuGet) i `Microsoft.AspNetCore.Mvc.Testing 10.0.12` — **5/5 testów
przechodzi**, a jedna klasyczna rada z internetu okazała się już nieaktualna (patrz niżej).

| 🧩 Temat | 🏷️ API | 💡 W jednym zdaniu |
|---|---|---|
| Wejście do API | `public partial class Program {}` | zabezpieczenie widoczności — zmierzone jako już niepotrzebne na tym SDK |
| Odpowiednik `IClassFixture<T>` | `[ClassDataSource<T>(Shared = SharedType.PerClass)]` | jeden host/`HttpClient` na całą klasę testową |
| Cykl życia fixture'a | `IAsyncInitializer` + `WebApplicationFactory.DisposeAsync` | TUnit sam woła start i koniec, bez ręcznego zarządzania |
| Pułapka współdzielonego stanu | domyślna równoległość + singleton store | test nie może zakładać, że jest sam na serwerze |

---

## 1. 🏗️ Minimalne API pod testem

Todo-API na `MapGet`/`MapPost`/`MapDelete`, stan trzymany w singletonie `ITodoStore`
(lista w pamięci, pod `lock`). Nic odkrywczego — to tylko poligon. Cały kod:
[`code/TunitWebApi/Program.cs`](code/TunitWebApi/Program.cs).

> 🎯 **Dlaczego to ważne:** `WebApplicationFactory` uruchamia **prawdziwy pipeline**
> (routing, model binding, middleware, DI) w procesie testowym, przez `TestServer` —
> to co innego niż wywołanie handlera bezpośrednio jako metody C#. Test HTTP-em łapie
> błędy, których unit test na handlerze nigdy nie zobaczy (zła trasa, zły content-type,
> DI nieskonfigurowane w `Program.cs`).

## 2. 🚪 `partial class Program` — rada, która już nie zawsze obowiązuje

Klasyczna porada dla minimal API: top-level statements generują niejawną klasę `Program`,
która bywała `internal`, więc `WebApplicationFactory<Program>` z osobnego projektu testów
rzucał `CS0122: 'Program' is inaccessible due to its protection level`. Rozwiązanie:
dopisać na końcu `Program.cs`:

```csharp
public partial class Program { }
```

**Zmierzyłem to empirycznie**, zamiast przepisywać radę z pamięci: usunąłem tę linię z
`TunitWebApi/Program.cs`, zbudowałem projekt testów od zera (`dotnet build --no-incremental`)
i odpaliłem `dotnet test` — **przeszło bez zmian, 5/5**. Dorzuciłem tymczasowy test
odbijający się o refleksję:

```csharp
var t = typeof(Program);
Console.WriteLine($"IsPublic={t.IsPublic} IsNotPublic={t.IsNotPublic}");
```

Output (prawdziwy, z przebiegu): `IsPublic=True IsNotPublic=False`. Na `TunitWebApi.csproj`
(`Sdk="Microsoft.NET.Sdk.Web"`, `net10.0`, SDK `10.0.400`) niejawna klasa `Program` jest
już **domyślnie `public`** — bez żadnego `InternalsVisibleTo`, bez sztuczek. Mimo to
zostawiłem `partial class Program` w kodzie repo jako **defensywne zabezpieczenie**
(gdyby ktoś kompilował na starszym SDK albo ta pierwotna reguła compiler powróciła) —
ale rada "zawsze musisz to dopisać" jest, przynajmniej tutaj, nieaktualna.

> 🎯 **Dlaczego to ważne:** to dokładnie przykład z misji tej rubryki — nie przepisujemy
> starej wiedzy z bloga, tylko mierzymy, co jest prawdą *teraz*, na *tym* SDK. Jeśli u
> Ciebie `CS0122` faktycznie wyskoczy (starszy SDK, inny langversion), `partial class
> Program` to nadal poprawne, znane obejście.

## 3. 🧷 TUnit-owy `IClassFixture<T>`: `[ClassDataSource<T>(Shared = SharedType.PerClass)]`

xUnit ma dedykowany interfejs `IClassFixture<T>`. TUnit reużywa mechanizmu poznanego w
wydaniu #3 (`[ClassDataSource<T>]` + `SharedType`) — tu zastosowanego do czegoś
realnego: hostowania API.

```csharp
public class TodoApiFixture : WebApplicationFactory<Program>, IAsyncInitializer
{
    public HttpClient Client { get; private set; } = null!;

    public Task InitializeAsync()
    {
        Client = CreateClient();
        return Task.CompletedTask;
    }

    public override async ValueTask DisposeAsync()
    {
        Console.WriteLine("[Fixture] DisposeAsync: zamykam TestServer");
        await base.DisposeAsync();
    }
}

[ClassDataSource<TodoApiFixture>(Shared = SharedType.PerClass)]
public class TodoApiTests(TodoApiFixture fixture)
{
    [Test]
    public async Task Post_TworzyTodo_ZwracaCreatedZLokalizacja()
    {
        var response = await fixture.Client.PostAsJsonAsync("/todos", new CreateTodoRequest("Kupic mleko"));
        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.Created);
        await Assert.That(response.Headers.Location).IsNotNull();
    }
    // ...
}
```

Zaobserwowane w realnym przebiegu (`--output Detailed`): `[Fixture] InitializeAsync`
loguje się raz, przy pierwszym teście klasy; `[Fixture] DisposeAsync` — raz, po ostatnim.
**TUnit sam woła obie metody** (`IAsyncInitializer.InitializeAsync` na starcie zakresu
`PerClass`, `DisposeAsync` na jego końcu) — nie trzeba nic sprzątać ręcznie, tak jak w
wydaniu #3 z fixture'ami danych. Różnica względem xUnitowego `IClassFixture<T>`: `Shared`
to jeden parametr o kilku wartościach (`PerClass`, `PerTestSession`, `Keyed`, `None` —
poznane w #3), więc **ten sam mechanizm** obsługuje i "jedna instancja na klasę"
(xUnitowe `IClassFixture`), i "jedna instancja na całe uruchomienie" (xUnitowe
`ICollectionFixture` + `[CollectionDefinition]`) — bez osobnego API na to drugie.

> 🎯 **Dlaczego to ważne:** postawienie prawdziwego `TestServer` kosztuje (setup DI,
> hostowanie, routing). `SharedType.PerClass` płaci ten koszt raz na klasę, nie raz na
> test — identyczny motyw wydajnościowy co xUnitowe `IClassFixture`, ale bez oddzielnego
> interfejsu do nauczenia się.

## 4. ⚠️ Pułapka: współdzielony host + domyślna równoległość

TUnit domyślnie **zrównolegla testy w obrębie klasy** (wydanie #2). Z `SharedType.PerClass`
wszystkie testy w `TodoApiTests` uderzają w **ten sam** `InMemoryTodoStore` — jeden
singleton, jeden `List<Todo>`. To rodzi pokusę napisania testu w stylu:

```csharp
// NAIWNIE — nie ma tego w repo, bo celowo się wywala
var todos = await fixture.Client.GetFromJsonAsync<List<Todo>>("/todos");
await Assert.That(todos!.Count).IsEqualTo(1);
```

Żeby **zmierzyć**, a nie zgadywać, dodałem taki test tymczasowo z pięcioma `[DependsOn]`
(poznane w #2) wymuszającymi wykonanie go **po** wszystkich pozostałych testach klasy —
to gwarantuje deterministyczny moment pomiaru, zamiast liczyć na przypadkową kolejność.
Realny output:

```
failed NAIVE_Get_WszystkieZadania_MaDokladnieJedenElement (46ms)
  [Test Failure] AssertionException: Expected to be 1
  but found 2

  at Assert.That(todos!.Count).IsEqualTo(1)
```

`2`, nie `1` — dwa wcześniejsze testy w tej samej klasie utworzyły własne rekordy i
nigdy ich nie usunęły, więc trafiły do tego samego globalnego stanu. **To nie jest
efekt równoległości per se** (kolejność tu i tak była wymuszona przez `[DependsOn]`) —
to efekt tego, że fixture współdzielony `PerClass` oznacza współdzielony *stan aplikacji*,
kropka. `[NotInParallel]` (wydanie #2) by tego **nie naprawił** — ustawia tylko
deterministyczną kolejność, a stan i tak by się kumulował.

Właściwy wzorzec widać w [`TodoApiTests.cs`](code/TunitWebApi.Tests/TodoApiTests.cs):
każdy test asercjuje **wyłącznie o zasobie, który sam utworzył** (po zwróconym `Id`),
nigdy o globalnym stanie serwera. Dzięki temu 5 testów bezpiecznie współdzieli jeden
host i jest bezpiecznych pod domyślną równoległością TUnit — bez potrzeby serializacji.

> 🎯 **Dlaczego to ważne:** to najczęstsza pułapka przy przenoszeniu testów integracyjnych
> z xUnit (gdzie `IClassFixture` bywa używany equally nieostrożnie) do frameworka, który
> **domyślnie** zrównolegla testy. Zasada: fixture współdzielony → testy piszesz tak, jakby
> działały w tym samym pokoju co inne testy w tej klasie, jednocześnie. Asercja o globalnym
> stanie ("lista ma dokładnie N elementów") jest bombą zegarową; asercja o własnym zasobie
> ("mój rekord istnieje i ma taką treść") jest bezpieczna.

---

## ✅ Co zweryfikowano, a co nie

- ✔️ `dotnet test`: **5/5 przeszło** (TUnit 1.70.1, `Microsoft.AspNetCore.Mvc.Testing` 10.0.12,
  .NET SDK 10.0.400, net10.0). Pełny output w [`code/README.md`](code/README.md).
- ✔️ TUnit 1.70.1 to aktualna wersja na NuGet w chwili pisania (sprawdzone `dotnet add
  package TUnit --version "*"`) — nowsza niż 1.69.0 używana w wydaniach #1–#4.
- ✔️ `partial class Program` **empirycznie zbędny** na tym SDK (`typeof(Program).IsPublic
  == true` bez niego) — zmierzone, nie przepisane z dokumentacji. Zostawiony w kodzie
  defensywnie.
- ✔️ `[Fixture] InitializeAsync`/`DisposeAsync` wywołane realnie raz na klasę (log w
  `--output Detailed`), co potwierdza że `SharedType.PerClass` + `IAsyncInitializer` +
  override `DisposeAsync` na `WebApplicationFactory` faktycznie działa jak xUnitowe
  `IClassFixture<T>`.
- ✔️ Pułapka współdzielonego stanu: potwierdzona realnym, deterministycznym (dzięki
  `[DependsOn]`) przebiegiem — `Expected to be 1 but found 2` — nie zmyślony output.
- ⚠️ Nie testowałem: `SharedType.PerTestSession` z `WebApplicationFactory` (współdzielenie
  jednego hosta między **wieloma klasami** testów), `[AfterEvery(Class)]`/`[AfterEvery(Assembly)]`
  (zostają na kolejne wydanie), Aspire (`DistributedApplicationTestingBuilder`) w połączeniu
  z TUnit, autoryzacji/JWT w `WebApplicationFactory` (`WithWebHostBuilder` + podmiana
  `IAuthenticationSchemeProvider`), realnej bazy danych za API (tu: czysty singleton
  in-memory, żadnego EF Core/`WebApplicationFactory.WithWebHostBuilder` do podmiany
  connection stringa).
- ⚠️ Czy `public partial class Program {}` bywał wymagany na `.NET 8`/`9` SDK — nie
  sprawdzałem retroaktywnie (mam tylko 10.0.400 na tej maszynie); opieram się na
  powszechnie znanej historii tej porady, nie na własnym pomiarze dla starszych SDK.

**Pełny, uruchamialny przykład:** [`code/TunitWebApi/`](code/TunitWebApi/) (API) +
[`code/TunitWebApi.Tests/`](code/TunitWebApi.Tests/) (testy).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — komendy + prawdziwy output `dotnet test`.

---

<div align="center">

[← wróć do wydania #5 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
