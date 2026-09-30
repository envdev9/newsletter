<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #7 — 30 września 2026

![TUnit](https://img.shields.io/badge/TUnit-2EA44F?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-ekspert-8250DF?style=for-the-badge)

## TUnit: jeden host, dwie klasy testowe — `SharedType.PerTestSession` + `[AfterEvery(Assembly)]`

</div>

---

> _"`PerClass` odpowiada na pytanie »ile to kosztuje w obrębie jednej klasy«.
> `PerTestSession` odpowiada na inne pytanie: »ile to kosztuje w całym przebiegu«."_

W wydaniu #5 (28.09) `[ClassDataSource<TodoApiFixture>(Shared = SharedType.PerClass)]`
dawał **jeden `WebApplicationFactory<Program>` na klasę testową** — xUnitowy
`IClassFixture<T>`. Dziś idziemy o oczko dalej: **jeden host na CAŁY przebieg testów**,
współdzielony przez **dwie zupełnie niezależne klasy testowe** — oraz hook, który widzi
koniec całego zestawu, nie tylko końca jednej klasy. Sprawdzone na `.NET SDK 10.0.400`,
`TUnit 1.72.4` (nowsza niż 1.70.1 z wydania #5 — zweryfikowane na NuGet) i
`Microsoft.AspNetCore.Mvc.Testing 10.0.12` — **11/11 testów przechodzi**, a kluczowa teza
("to naprawdę jeden host, nie dwa") jest zmierzona po stronie serwera, nie zgadywana z logów.

| 🧩 Temat | 🏷️ API | 💡 W jednym zdaniu |
|---|---|---|
| Host współdzielony między klasami | `[ClassDataSource<T>(Shared = SharedType.PerTestSession)]` | jeden `WebApplicationFactory` dla wielu klas testowych naraz |
| Dowód, nie zgadywanie | `GET /instance-id` (`Guid` wygenerowany raz przy starcie hosta) | serwer sam mówi, czy dwie klasy trafiły w ten sam proces |
| Hook na koniec CAŁEGO zestawu | `[AfterEvery(Assembly)]` (`AssemblyHookContext`) | raport zbiorczy po wszystkich klasach, nie po jednej |
| Zmierzona kolejność teardownu | `DisposeAsync` fixture'a **przed** `[AfterEvery(Assembly)]` | hook widzi już zamknięty host — przydatne przy raportowaniu |

---

## 1. 🏗️ Dwa zasoby, jeden host

Todo-API z wydania #5 dostało sąsiada: `/notes` (`INoteStore`, ten sam wzorzec co
`ITodoStore` — singleton, lista w pamięci, `lock`). Dwie niezależne rodziny zasobów w
**jednym** API, każda testowana przez osobną klasę testową. Cały kod:
[`code/TunitWebApi/Program.cs`](code/TunitWebApi/Program.cs).

Dorzucony jeden endpoint bez odpowiednika w wydaniu #5:

```csharp
var instanceId = Guid.NewGuid();
app.MapGet("/instance-id", () => Results.Ok(instanceId));
```

`Guid.NewGuid()` w top-level statements wykonuje się **raz**, gdy proces hosta startuje.
To nie jest ozdobnik — to jedyny sposób, żeby **po stronie serwera**, a nie w logach
fixture'a, zmierzyć, czy dwie klasy testowe faktycznie rozmawiają z tym samym procesem.

> 🎯 **Dlaczego to ważne:** dotychczasowe wydania dowodziły współdzielenia instancji przez
> logi (`Console.WriteLine` w `InitializeAsync`/`DisposeAsync`). To wystarczało dla jednej
> klasy. Gdy w grę wchodzą dwie klasy i pytanie "czy to na pewno ten sam TestServer, czy
> tylko przypadkiem podobny log", potrzebny jest dowód niezależny od samego mechanizmu,
> który testujemy — stąd endpoint zwracający identyfikator procesu.

## 2. 🔗 `SharedType.PerTestSession`: jeden fixture, dwie klasy

`TodoApiFixture` (ten sam typ co w wydaniu #5, dodane tylko statyczne liczniki do pomiaru)
jest teraz wskazywany z **dwóch** klas testowych:

```csharp
// TodoApiTests.cs
[ClassDataSource<TodoApiFixture>(Shared = SharedType.PerTestSession)]
public class TodoApiTests(TodoApiFixture fixture) { /* testy /todos */ }

// NotesApiTests.cs — inna klasa, ten sam typ fixture'a, ten sam SharedType
[ClassDataSource<TodoApiFixture>(Shared = SharedType.PerTestSession)]
public class NotesApiTests(TodoApiFixture fixture) { /* testy /notes */ }
```

W wydaniu #3 poznaliśmy `SharedType.PerTestSession` teoretycznie (jako jedną z czterech
wartości enuma, obok `PerClass`/`Keyed`/`None`) i zostawiliśmy niezweryfikowane w
połączeniu z `WebApplicationFactory`. Dziś to zmierzone: obie klasy dostają **dokładnie
ten sam** obiekt `TodoApiFixture` — TUnit tworzy go raz na cały przebieg (`Assembly`/
`TestSession`), nie raz na klasę.

**Dowód, nie deklaracja.** `TodoApiFixture.InitializeCount`/`DisposeCount` (statyczne,
`Interlocked`) plus test w każdej klasie odpytujący `/instance-id` i zapisujący wynik do
wspólnego słownika (`InstanceIdObservations`):

```csharp
[Test]
public async Task ZglaszaInstanceIdHosta_DoWspolnegoRaportu()
{
    var response = await fixture.Client.GetAsync("/instance-id");
    var instanceId = await response.Content.ReadFromJsonAsync<Guid>();
    InstanceIdObservations.Record(nameof(TodoApiTests), instanceId);
    await Assert.That(instanceId).IsNotEqualTo(Guid.Empty);
}
```

Realny output z `[AfterEvery(Assembly)]` (pełen kontekst w sekcji 3):

```
TodoApiFixture.InitializeCount = 1
TodoApiFixture.DisposeCount    = 1
  instance-id widziany przez NotesApiTests: 7c9c6df6-4148-42e9-bdeb-28dc0ce6c0c3
  instance-id widziany przez TodoApiTests: 7c9c6df6-4148-42e9-bdeb-28dc0ce6c0c3
Liczba roznych instance-id: 1 (oczekiwane: 1 -- jeden wspolny host PerTestSession)
```

Żeby to nie było gołosłowne, zrobiłem kontrolę: zamieniłem tymczasowo `PerTestSession` na
`PerClass` w obu klasach i uruchomiłem ten sam zestaw ponownie. Realny wynik kontrolny:

```
TodoApiFixture.InitializeCount = 2
TodoApiFixture.DisposeCount    = 2
  instance-id widziany przez NotesApiTests: 6e3d6206-4d6d-4267-a0d1-834b0d18c527
  instance-id widziany przez TodoApiTests: da65b3eb-525b-4cfc-bc61-a04a5ae3839b
Liczba roznych instance-id: 2 (oczekiwane: 1 -- jeden wspolny host PerTestSession)
```

Dwa różne `Guid`, dwa wywołania `InitializeAsync`/`DisposeAsync` — dokładnie to, czego
oczekujemy po `PerClass` (wydanie #5). Kontrast potwierdza, że `PerTestSession` naprawdę
robi coś innego, a nie że licznik przypadkiem zawsze wychodzi na 1.

> 🎯 **Dlaczego to ważne:** stawianie prawdziwego `TestServer` (DI, routing, middleware)
> kosztuje. `PerClass` płaci ten koszt raz na klasę; `PerTestSession` płaci go **raz w
> całym przebiegu** — jeśli masz dziesięć klas integracyjnych bijących w to samo API,
> różnica to dziesięć uruchomień hosta kontra jedno. To dokładnie xUnitowy wzorzec
> `ICollectionFixture<T>` + `[CollectionDefinition]` (jedna instancja dla całej "kolekcji"
> klas) — tylko że w TUnit to ten sam atrybut i ten sam enum, którego już znasz z #3 i #5,
> nie osobne API do nauczenia się.

## 3. 📋 `[AfterEvery(Assembly)]`: raport po całym zestawie, nie po jednej klasie

`[AfterEvery(Test)]` (wydanie #4) i `[After(TestSession)]` (wydanie #3) już poznaliśmy.
`[AfterEvery(Assembly)]` to trzeci poziom granularności — `static` metoda wołana raz, gdy
**wszystkie** testy w assembly (czyli tu: `TodoApiTests` + `NotesApiTests` razem) się
skończą:

```csharp
public static class AssemblyHooks
{
    [AfterEvery(Assembly)]
    public static void Report(AssemblyHookContext context)
    {
        var ids = InstanceIdObservations.SeenByClass;
        Console.WriteLine("=== RAPORT [AfterEvery(Assembly)] ===");
        Console.WriteLine($"TodoApiFixture.InitializeCount = {TodoApiFixture.InitializeCount}");
        Console.WriteLine($"TodoApiFixture.DisposeCount    = {TodoApiFixture.DisposeCount}");
        foreach (var (className, id) in ids.OrderBy(kv => kv.Key))
            Console.WriteLine($"  instance-id widziany przez {className}: {id}");
        Console.WriteLine($"Liczba roznych instance-id: {ids.Values.Distinct().Count()}");
    }
}
```

Sygnatura (`static void Method(AssemblyHookContext context)`) zadziałała za pierwszym
razem, bez żadnego eksperymentowania z kompilatorem — spójna z wzorcem, który znasz z
`[BeforeEvery(Test)]` (`TestContext context`, wydanie #3): każdy poziom granularności
(`Test`/`Class`/`Assembly`/`TestSession`) ma swój typ kontekstu o analogicznym kształcie.

**Zmierzona, zaskakująca kolejność.** W realnym przebiegu (`--output Detailed`) log
wygląda tak:

```
[Fixture] DisposeAsync wywolanie #1
=== RAPORT [AfterEvery(Assembly)] ===
TodoApiFixture.InitializeCount = 1
TodoApiFixture.DisposeCount    = 1
```

`DisposeAsync` fixture'a (`PerTestSession`, więc wołany raz, po ostatnim teście
korzystającym z niego w całym przebiegu) kończy się **przed** `[AfterEvery(Assembly)]`.
To ma sens dopiero, gdy się to zobaczy: `PerTestSession` jest technicznie związany z
zakresem sesji testowej, a `[AfterEvery(Assembly)]` odpala się po zamknięciu wszystkich
testów assembly — fixture zdążył się już posprzątać, zanim hook zdąży go zaraportować.
Konsekwencja praktyczna: **jeśli w `[AfterEvery(Assembly)]` chcesz jeszcze użyć fixture'a
(np. odpytać API), może być już zamknięty** — raportuj tylko dane zebrane wcześniej
(liczniki, słowniki), nie zakładaj żywego połączenia.

> 🎯 **Dlaczego to ważne:** `[After(TestSession)]` (wydanie #3) i `[AfterEvery(Assembly)]`
> brzmią jak synonimy, ale mają różne przeznaczenie. `TestSession` to najszerszy zakres
> TUnit (cały przebieg `dotnet test`, może obejmować wiele assembly w jednym runie).
> `AfterEvery(Assembly)` jest zakresem assembly — przy jednym projekcie testowym w
> praktyce zobaczysz go raz, tak jak tutaj, ale w rozwiązaniu z wieloma projektami testów
> odpali się **raz na każde assembly**, nie raz total. Wybierasz poziom w zależności od
> tego, czy raport ma być "na projekt" czy "na cały `dotnet test`".

## 4. ⚠️ Pułapka: dwie klasy na jednym hoście to nadal jeden stan aplikacji

Wydanie #5 uczyło: fixture współdzielony `PerClass` → nie asercjuj o globalnym stanie
serwera, tylko o zasobie, który sam utworzyłeś. `PerTestSession` zaostrza tę zasadę:
teraz **dwie różne klasy testowe** biją w ten sam singleton DI. Świadomie rozdzieliłem
odpowiedzialność — `TodoApiTests` dotyka wyłącznie `/todos`, `NotesApiTests` wyłącznie
`/notes` — żeby separacja była czytelna od pierwszego wejrzenia w kod, a nie tylko
"bezpieczna przez przypadek", bo asercje i tak są po `Id`.

Gdyby obie klasy testowały ten sam zasób (`/todos`), zasada z wydania #5 nadal by
wystarczyła (asercja po własnym `Id`), ale rozdzielenie na `/todos` i `/notes` pokazuje
wprost: **`PerTestSession` współdzieli proces aplikacji między dowolną liczbą klas testowych,
nie tylko między testami jednej klasy** — im więcej klas dzieli fixture, tym łatwiej o
przypadkowe sprzężenie, jeśli ktoś kiedyś doda test asercjonujący o `store.GetAll().Count`.

> 🎯 **Dlaczego to ważne:** to ten sam motyw co w wydaniu #5, ale skala rośnie z liczbą
> klas współdzielących fixture. Przy `PerClass` "sąsiadami" w stanie są testy jednej
> klasy; przy `PerTestSession` sąsiadami są **wszystkie klasy w projekcie testowym**. Im
> szerszy zakres współdzielenia (motyw wydajnościowy), tym silniejsza dyscyplina asercji
> potrzebna (motyw poprawności) — to naturalny kompromis tego mechanizmu, nie jego wada.

---

## ✅ Co zweryfikowano, a co nie

- ✔️ `dotnet test`: **11/11 przeszło** (TUnit 1.72.4, `Microsoft.AspNetCore.Mvc.Testing`
  10.0.12, .NET SDK 10.0.400, net10.0), powtórzone dwukrotnie bez flakowania. Pełny output
  w [`code/README.md`](code/README.md).
- ✔️ TUnit 1.72.4 to aktualna wersja na NuGet w chwili pisania (`dotnet add package TUnit
  --version "*"`) — nowsza niż 1.70.1 z wydania #5.
- ✔️ `SharedType.PerTestSession` z `WebApplicationFactory` między **dwiema różnymi
  klasami testowymi**: zmierzone wprost (`InitializeCount = 1`, `DisposeCount = 1`, jeden
  wspólny `instance-id`), nie wywnioskowane z dokumentacji.
- ✔️ Kontrola kontrastowa: te same testy z `SharedType.PerClass` dały `InitializeCount = 2`
  i dwa różne `instance-id` — potwierdza, że różnica jest realna, nie przypadkowa.
- ✔️ `[AfterEvery(Assembly)]` (`static void Method(AssemblyHookContext context)`) —
  zadziałał za pierwszym razem, bez iteracji z kompilatorem.
- ✔️ Zmierzona kolejność: `DisposeAsync` fixture'a `PerTestSession` kończy się **przed**
  `[AfterEvery(Assembly)]` — zaobserwowane w realnym logu, nie założone.
- ⚠️ Nie testowałem: `[AfterEvery(Class)]` (zostaje na kolejne wydanie), zachowanie
  `[AfterEvery(Assembly)]` przy **wielu projektach testowych w jednym `dotnet test`**
  (mam tu tylko jeden projekt, więc różnica "raz na assembly" vs "raz na cały przebieg"
  jest w tym repo niewidoczna — opisana teoretycznie w sekcji 3, nie zmierzona), Aspire +
  TUnit (`DistributedApplicationTestingBuilder`), autoryzacja/JWT w `WebApplicationFactory`.

**Pełny, uruchamialny przykład:** [`code/TunitWebApi/`](code/TunitWebApi/) (API) +
[`code/TunitWebApi.Tests/`](code/TunitWebApi.Tests/) (testy).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — komendy + prawdziwy output `dotnet test`.

---

<div align="center">

[← wróć do wydania #7 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
