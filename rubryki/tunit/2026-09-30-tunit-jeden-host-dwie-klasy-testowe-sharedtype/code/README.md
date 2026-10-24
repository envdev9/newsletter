# Kod do wydania #7 — TUnit + `SharedType.PerTestSession` + `[AfterEvery(Assembly)]`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`). Podstawy TUnit: wydania #1–#5
(w szczególności #3: `[ClassDataSource<T>]` + `SharedType`, `IAsyncInitializer`; #5:
`WebApplicationFactory<Program>` + `SharedType.PerClass`).

## Fragment prasówki, którego dotyczy ten kod

> `TodoApiFixture` (ten sam typ co w wydaniu #5, dodane tylko statyczne liczniki do
> pomiaru) jest teraz wskazywany z **dwóch** klas testowych: `TodoApiTests` (`/todos`) i
> `NotesApiTests` (`/notes`), obie z `[ClassDataSource<TodoApiFixture>(Shared =
> SharedType.PerTestSession)]`. TUnit tworzy fixture RAZ na cały przebieg, nie raz na
> klasę — zmierzone przez endpoint `GET /instance-id` (`Guid` wygenerowany raz przy
> starcie hosta) i statyczne liczniki `InitializeCount`/`DisposeCount`. `[AfterEvery
> (Assembly)]` to hook wołany raz, po tym jak WSZYSTKIE testy w całym assembly (obie
> klasy) się skończą — użyty tu do raportu zbiorczego.

## Struktura projektu

```
TunitWebApi/                       # minimalne API pod testem
├── TunitWebApi.csproj             # net10.0, Microsoft.NET.Sdk.Web
├── Program.cs                     # /todos, /notes, /instance-id + dwa in-memory store'y
└── .gitignore                     # bin/, obj/

TunitWebApi.Tests/                 # testy integracyjne w TUnit
├── TunitWebApi.Tests.csproj       # TUnit 1.72.4, Microsoft.AspNetCore.Mvc.Testing 10.0.12
├── global.json                    # wymagany na .NET 10 SDK (Microsoft.Testing.Platform)
├── TodoApiFixture.cs              # WebApplicationFactory<Program> + IAsyncInitializer + liczniki
├── InstanceIdObservations.cs      # wspólny słownik class -> instance-id, do pomiaru
├── TodoApiTests.cs                # [ClassDataSource<TodoApiFixture>(Shared = SharedType.PerTestSession)]
├── NotesApiTests.cs               # ten sam Shared, INNA klasa testowa — dowód współdzielenia
├── AssemblyHooks.cs               # [AfterEvery(Assembly)] — raport zbiorczy
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

## Prawdziwy output (11/11, przebieg z tej maszyny)

```
Running tests from .../TunitWebApi.Tests.dll (net10.0|x64)
passed Get_NieistniejacyId_Zwraca404 (474ms)
  Standard output
    [Fixture] InitializeAsync wywolanie #1
    info: Microsoft.Hosting.Lifetime[0]
          Application started. Press Ctrl+C to shut down.
    info: Microsoft.Hosting.Lifetime[0]
          Hosting environment: Development
    info: Microsoft.Hosting.Lifetime[0]
          Content root path: .../TunitWebApi
passed Get_NieistniejacyId_Zwraca404 (385ms)
passed Post_PustyTytul_Zwraca400 (61ms)
passed Get_PoUtworzeniu_ZwracaToSamoZadanie (487ms)
passed Delete_UsuwaWlasnyRekord_PotemGet404 (57ms)
passed Get_PoUtworzeniu_ZwracaToSamaNotatke (583ms)
passed Post_TworzyNotatke_ZwracaCreatedZLokalizacja (436ms)
passed Post_PustaTresc_Zwraca400 (443ms)
passed Post_TworzyTodo_ZwracaCreatedZLokalizacja (483ms)
passed ZglaszaInstanceIdHosta_DoWspolnegoRaportu (36ms)
passed ZglaszaInstanceIdHosta_DoWspolnegoRaportu (474ms)
  Standard output
    [Fixture] DisposeAsync wywolanie #1
    === RAPORT [AfterEvery(Assembly)] ===
    TodoApiFixture.InitializeCount = 1
    TodoApiFixture.DisposeCount    = 1
      instance-id widziany przez NotesApiTests: 7c9c6df6-4148-42e9-bdeb-28dc0ce6c0c3
      instance-id widziany przez TodoApiTests: 7c9c6df6-4148-42e9-bdeb-28dc0ce6c0c3
    Liczba roznych instance-id: 1 (oczekiwane: 1 -- jeden wspolny host PerTestSession)

Test run summary: Passed!
  total: 11
  failed: 0
  succeeded: 11
  skipped: 0
  duration: 2s 795ms
```

`InitializeCount = 1` i `DisposeCount = 1` mimo DWÓCH niezależnych klas testowych
(`TodoApiTests`, `NotesApiTests`) korzystających z `TodoApiFixture` — dowód, że
`SharedType.PerTestSession` tworzy jeden `WebApplicationFactory<Program>` na cały
przebieg. Oba `instance-id` (odczytane przez `GET /instance-id` z osobnych testów w
osobnych klasach) są identyczne — drugi, niezależny dowód tego samego faktu, tym razem
zmierzony po stronie serwera, nie po stronie fixture'a.

Powtórzone dwukrotnie (`dotnet test` uruchomiony osobno) — za każdym razem 11/11, bez
flakowania.

## Kontrola kontrastowa: `SharedType.PerClass` dla porównania

Żeby odróżnić "PerTestSession naprawdę robi coś innego" od "licznik akurat wyszedł na 1",
zamieniłem tymczasowo `Shared = SharedType.PerTestSession` na `Shared =
SharedType.PerClass` w obu klasach (`TodoApiTests.cs`, `NotesApiTests.cs`) i uruchomiłem
ten sam zestaw testów ponownie. Realny wynik (zmiana nieobecna w repo — przywrócona po
pomiarze):

```
=== RAPORT [AfterEvery(Assembly)] ===
TodoApiFixture.InitializeCount = 2
TodoApiFixture.DisposeCount    = 2
  instance-id widziany przez NotesApiTests: 6e3d6206-4d6d-4267-a0d1-834b0d18c527
  instance-id widziany przez TodoApiTests: da65b3eb-525b-4cfc-bc61-a04a5ae3839b
Liczba roznych instance-id: 2 (oczekiwane: 1 -- jeden wspolny host PerTestSession)

Test run summary: Passed!
  total: 11
  failed: 0
  succeeded: 11
```

Dwa wywołania `InitializeAsync`, dwa różne `instance-id` — `PerClass` faktycznie tworzy
osobny host dla każdej klasy, tak jak w wydaniu #5. Kod w repo używa `PerTestSession`
(zobacz `TodoApiTests.cs`/`NotesApiTests.cs`) — powyższy wynik to tylko pomiar kontrolny,
nie stan docelowy.

## Zmierzona kolejność teardownu: fixture przed hookiem

`[Fixture] DisposeAsync wywolanie #1` pojawia się w logu **przed** `=== RAPORT
[AfterEvery(Assembly)] ===` — `WebApplicationFactory` zdążył się zamknąć, zanim hook
zdążył zaraportować. Wniosek zastosowany w `AssemblyHooks.cs`: hook czyta tylko dane
zebrane wcześniej (statyczne liczniki, słownik `InstanceIdObservations`), nie odpytuje
już `fixture.Client` — może być nieważny.

## Nie zweryfikowano

`[AfterEvery(Class)]`, zachowanie `[AfterEvery(Assembly)]` przy wielu projektach testowych
w jednym uruchomieniu `dotnet test` (tu jest tylko jeden projekt testowy, więc różnica
"raz na assembly" vs "raz na cały przebieg" pozostaje teoretyczna), Aspire + TUnit
(`DistributedApplicationTestingBuilder`), autoryzacja/JWT w `WebApplicationFactory`.
