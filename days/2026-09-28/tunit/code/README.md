# Kod do wydania #5 — TUnit + `WebApplicationFactory<Program>`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`). Podstawy TUnit: wydania #1–#4
(w szczególności #3: `[ClassDataSource<T>]` + `SharedType`, `IAsyncInitializer`).

## Fragment prasówki, którego dotyczy ten kod

> xUnit ma dedykowany interfejs `IClassFixture<T>`. TUnit reużywa mechanizmu poznanego
> w wydaniu #3 (`[ClassDataSource<T>]` + `SharedType`) — tu zastosowanego do czegoś
> realnego: hostowania API. `SharedType.PerClass` tworzy `WebApplicationFactory<Program>`
> raz na klasę testową; `IAsyncInitializer.InitializeAsync` i (nadpisany) `DisposeAsync`
> TUnit woła sam, bez ręcznego zarządzania. Pułapka: współdzielony host = współdzielony
> stan aplikacji (singleton `ITodoStore`) — testy nie mogą asercjować o globalnym stanie
> serwera ("lista ma dokładnie N elementów"), tylko o zasobie, który same utworzyły.

## Struktura projektu

```
TunitWebApi/                       # minimalne API pod testem
├── TunitWebApi.csproj             # net10.0, Microsoft.NET.Sdk.Web
├── Program.cs                     # endpointy /todos (GET/POST/DELETE) + InMemoryTodoStore
└── .gitignore                     # bin/, obj/

TunitWebApi.Tests/                 # testy integracyjne w TUnit
├── TunitWebApi.Tests.csproj       # TUnit 1.70.1, Microsoft.AspNetCore.Mvc.Testing 10.0.12
├── global.json                    # wymagany na .NET 10 SDK (Microsoft.Testing.Platform)
├── TodoApiFixture.cs              # WebApplicationFactory<Program> + IAsyncInitializer
├── TodoApiTests.cs                # [ClassDataSource<TodoApiFixture>(Shared = SharedType.PerClass)]
└── .gitignore                     # TestResults/, bin/, obj/
```

## Jak odpalić od zera

```bash
cd TunitWebApi.Tests
dotnet test --output Detailed --results-directory /tmp/tunit-results
```

Uruchamiaj z folderu `TunitWebApi.Tests` — SDK szuka `global.json` od bieżącego katalogu.
Projekt testów ma `<ProjectReference>` do `../TunitWebApi/TunitWebApi.csproj`, więc `dotnet
test` sam zbuduje API przed testami. `--results-directory` trzyma raport HTML poza repo.

## Prawdziwy output (5/5, przebieg z tej maszyny)

```
Running tests from .../TunitWebApi.Tests.dll (net10.0|x64)
passed Get_NieistniejacyId_Zwraca404 (368ms)
passed Get_PoUtworzeniu_ZwracaToSamoZadanie (410ms)
passed Delete_UsuwaWlasnyRekord_PotemGet404 (367ms)
passed Post_PustyTytul_Zwraca400 (431ms)
passed Post_TworzyTodo_ZwracaCreatedZLokalizacja (429ms)
  Standard output
    [Fixture] InitializeAsync: startuje WebApplicationFactory<Program>
    info: Microsoft.Hosting.Lifetime[0]
          Application started. Press Ctrl+C to shut down.
    info: Microsoft.Hosting.Lifetime[0]
          Hosting environment: Development
    info: Microsoft.Hosting.Lifetime[0]
          Content root path: .../TunitWebApi

    [Fixture] DisposeAsync: zamykam TestServer

Test run summary: Passed!
  total: 5
  failed: 0
  succeeded: 5
  skipped: 0
  duration: 4s 315ms
```

`[Fixture] InitializeAsync` pojawia się raz (przy pierwszym teście klasy), `[Fixture]
DisposeAsync` — raz (po ostatnim) — dowód, że `SharedType.PerClass` faktycznie tworzy
i sprząta `WebApplicationFactory<Program>` dokładnie raz na całą klasę testową, tak jak
xUnitowe `IClassFixture<T>`.

## Zmierzone: `partial class Program` już niekonieczny na tym SDK

Usunięcie linii `public partial class Program { }` z `TunitWebApi/Program.cs` i
uruchomienie `dotnet build --no-incremental` + `dotnet test` w `TunitWebApi.Tests` dało
**taki sam wynik: 5/5, bez błędów kompilacji**. Tymczasowy test z refleksją:

```csharp
var t = typeof(Program);
Console.WriteLine($"IsPublic={t.IsPublic} IsNotPublic={t.IsNotPublic}");
```

dał realny output `IsPublic=True IsNotPublic=False` — na `net10.0` / SDK `10.0.400`
niejawna klasa `Program` z top-level statements jest już domyślnie `public`. Kod w tym
repo i tak zawiera `public partial class Program {}` jako defensywne zabezpieczenie
(starsze SDK, inne ustawienia) — patrz komentarz w `Program.cs`.

## Zmierzone: pułapka współdzielonego stanu (`[DependsOn]` jako deterministyczny pomiar)

Tymczasowy test (nieobecny w repo, usunięty po zmierzeniu — analogicznie do wydania #4):

```csharp
[Test]
[DependsOn(nameof(Post_TworzyTodo_ZwracaCreatedZLokalizacja))]
[DependsOn(nameof(Get_PoUtworzeniu_ZwracaToSamoZadanie))]
[DependsOn(nameof(Get_NieistniejacyId_Zwraca404))]
[DependsOn(nameof(Post_PustyTytul_Zwraca400))]
[DependsOn(nameof(Delete_UsuwaWlasnyRekord_PotemGet404))]
public async Task NAIVE_Get_WszystkieZadania_MaDokladnieJedenElement()
{
    var todos = await fixture.Client.GetFromJsonAsync<List<Todo>>("/todos");
    await Assert.That(todos!.Count).IsEqualTo(1);
}
```

`[DependsOn]` na wszystkich pozostałych testach klasy wymusza, że ten test biegnie
**na pewno ostatni** — bez zgadywania kolejności. Realny output tego przebiegu:

```
failed NAIVE_Get_WszystkieZadania_MaDokladnieJedenElement (46ms)
  [Test Failure] AssertionException: Expected to be 1
  but found 2

  at Assert.That(todos!.Count).IsEqualTo(1)

Test run summary: Failed!
  total: 6
  failed: 1
  succeeded: 5
```

`2`, bo dwa wcześniejsze testy utworzyły własne, nigdy nieusunięte rekordy w tym samym
współdzielonym `InMemoryTodoStore`. Wniosek zastosowany w prawdziwych testach: asercjuj
o zasobie, który sam utworzyłeś (po `Id`), nie o globalnym stanie serwera.

## Nie zweryfikowano

`SharedType.PerTestSession` z `WebApplicationFactory` (współdzielenie jednego hosta
między wieloma klasami testów), `[AfterEvery(Class)]`/`[AfterEvery(Assembly)]`, Aspire +
TUnit, autoryzacja/JWT w `WebApplicationFactory`, realna baza danych za API, oraz czy
`partial class Program` bywał wymagany na starszych SDK (8/9) — nie testowane
retroaktywnie na tej maszynie.
