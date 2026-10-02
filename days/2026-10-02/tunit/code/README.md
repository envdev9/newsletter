# Kod do wydania #9 — TUnit + `[AfterEvery(Class)]` + JWT w `WebApplicationFactory`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`). Podstawy TUnit: wydania #1–#5,
#7 (w szczególności #4: `[AfterEvery(Test)]`; #5: `WebApplicationFactory<Program>` +
`SharedType.PerClass`; #7: `[AfterEvery(Assembly)]`).

## Fragment prasówki, którego dotyczy ten kod

> Rodzina `[AfterEvery]` ma trzy poziomy ziarnistości: `Test` (wydanie #4) → `Class`
> (dziś) → `Assembly` (wydanie #7). Sygnatura jest spójna z resztą rodziny — `static void
> Method(ClassHookContext context)` zadziałała od razu. `ClassHookContext.ClassType`
> identyfikuje, która klasa właśnie się skończyła. `ClassHookContext.Tests`
> (`IReadOnlyList<TestContext>`) daje dostęp do WSZYSTKICH testów tej klasy —
> `t.Execution.Result?.State` pozwala policzyć passed/failed bez własnego licznika
> rozsianego po każdym teście.
>
> Druga połowa wydania: testy integracyjne z PRAWDZIWYM tokenem JWT i PRAWDZIWYM
> `[Authorize]`/`[Authorize(Policy = "AdminOnly")]` w `WebApplicationFactory<Program>`.
> `TokenFactory` mintuje token TYM SAMYM kluczem co aplikacja (przez `ProjectReference`
> do `TunitWebApi.JwtDemoSettings`), nie zgaduje formatu. Zmierzona pułapka:
> `MapInboundClaims` i `RoleClaimType`/`NameClaimType` muszą się zgadzać — źle ustawione
> dają CISZĄ porażkę autoryzacji (403 zamiast 200, albo puste dane tam, gdzie powinny być
> claimy), nie wyjątek.

## ⚠️ Uwaga o kluczu JWT w tym kodzie

`TunitWebApi/JwtDemoSettings.cs` zawiera klucz podpisujący JWT **wyłącznie
demonstracyjny**, jawny w tym publicznym repozytorium. Pokazuje MECHANIZM (jak skonfigurować
`JwtBearer`, jak zmintować token zgodny z tą konfiguracją), nie sposób bezpiecznego
przechowywania sekretu. **Nigdy nie używać tego wzorca (klucz jako stała w kodzie) w
prawdziwym projekcie** — prawdziwy klucz podpisujący należy do menedżera sekretów (Key
Vault, `dotnet user-secrets` — patrz rubryka Aspire, wydanie #7 — albo zmienna
środowiskowa wstrzyknięta przez orkiestrator).

## Struktura projektu

```
TunitWebApi/                       # minimalne API pod testem
├── TunitWebApi.csproj             # net10.0, Microsoft.NET.Sdk.Web, Microsoft.AspNetCore.Authentication.JwtBearer 10.0.12
├── Program.cs                     # /public/ping, /secure/profile ([Authorize]), /secure/admin-report ([Authorize(Policy="AdminOnly")])
├── JwtDemoSettings.cs             # Issuer/Audience/SigningKey DEMO -- nigdy produkcyjnie
└── .gitignore                     # bin/, obj/

TunitWebApi.Tests/                 # testy integracyjne w TUnit
├── TunitWebApi.Tests.csproj       # TUnit 1.72.10, Microsoft.AspNetCore.Mvc.Testing 10.0.12
├── global.json                    # wymagany na .NET 10 SDK (Microsoft.Testing.Platform)
├── ApiFixture.cs                  # WebApplicationFactory<Program> + IAsyncInitializer, SharedType.PerClass
├── TokenFactory.cs                # mintuje JWT tym samym kluczem co API (ProjectReference)
├── TestRequests.cs                # HttpRequestMessage + opcjonalny Bearer (bez mutowania DefaultRequestHeaders)
├── AuthenticatedUserTests.cs      # /secure/profile: brak/wazny/wygasly/zle-podpisany token
├── AdminAuthorizationTests.cs     # /secure/admin-report: brak roli -> 403, rola admin -> 200
├── ClassHooks.cs                  # [AfterEvery(Class)] -- raport po KAZDEJ klasie
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

## Prawdziwy output (8/8, przebieg z tej maszyny)

```
Running tests from .../TunitWebApi.Tests.dll (net10.0|x64)
passed Profil_BezTokenu_Zwraca401 (296ms)
  Standard output
    [ApiFixture] InitializeAsync wywolanie #2
    info: Microsoft.Hosting.Lifetime[0]
          Application started. Press Ctrl+C to shut down.
passed AdminRaport_BezTokenu_Zwraca401 (296ms)
  Standard output
    [ApiFixture] InitializeAsync wywolanie #1
    info: Microsoft.Hosting.Lifetime[0]
          Application started. Press Ctrl+C to shut down.
passed Profil_ZTokenemPodpisanymZlymKluczem_Zwraca401 (242ms)
passed Profil_ZWygaslymTokenem_Zwraca401 (274ms)
passed AdminRaport_ZTokenemZwyklegoUzytkownika_Zwraca403 (297ms)
passed AdminRaport_ZTokenemZWieluRolami_DajeDostep (361ms)
passed AdminRaport_ZTokenemAdmina_Zwraca200 (437ms)
  Standard output
    === [AfterEvery(Class)] wywolanie #1: klasa AdminAuthorizationTests ===
      Testow w klasie: 4 (passed=4, failed=0, inne=0)
      ApiFixture.InitializeCount (globalnie, po tej klasie) = 2
passed Profil_ZWaznymTokenem_ZwracaDaneUzytkownika (357ms)
  Standard output
    === [AfterEvery(Class)] wywolanie #2: klasa AuthenticatedUserTests ===
      Testow w klasie: 4 (passed=4, failed=0, inne=0)
      ApiFixture.InitializeCount (globalnie, po tej klasie) = 2

Test run summary: Passed!
  total: 8
  failed: 0
  succeeded: 8
  skipped: 0
  duration: 2s 547ms
```

`[AfterEvery(Class)]` odpalił się **dwa razy** — raz po `AdminAuthorizationTests`, raz po
`AuthenticatedUserTests` — w przeciwieństwie do `[AfterEvery(Assembly)]` z wydania #7,
który na analogicznym kształcie (dwie klasy testowe) odpalił się **raz**.
`ApiFixture.InitializeCount = 2` (bo `SharedType.PerClass`, jeden host na klasę)
potwierdza niezależnie to samo z innej strony.

Powtórzone dwukrotnie (`dotnet test` uruchomiony osobno) — za każdym razem 8/8, bez
flakowania.

## Zmierzona pułapka: `MapInboundClaims` + `RoleClaimType` muszą się zgadzać

Kod w repo (`Program.cs`) używa `MapInboundClaims = false` + `RoleClaimType = "role"` —
to jest wariant, który daje 8/8 powyżej. Żeby udowodnić, że to nie przypadek, zrobiłem
dwa kontrolowane przebiegi (zmiany NIE weszły do repo — tylko tymczasowe, przywrócone po
pomiarze):

**Kontrolny #1** — usunięta linia `RoleClaimType = "role"` (zostaje domyślne, długie URI
`ClaimTypes.Role`), `MapInboundClaims = false` zostaje:

```
failed AdminRaport_ZTokenemAdmina_Zwraca200
  [Test Failure] AssertionException: Expected to be equal to OK
  but received Forbidden

failed AdminRaport_ZTokenemZWieluRolami_DajeDostep
  [Test Failure] AssertionException: Expected to be equal to OK
  but received Forbidden

Test run summary: Failed!
  total: 4
  failed: 2
  succeeded: 2
```

**Kontrolny #2** — przywrócone `RoleClaimType = "role"`, ale zakomentowane
`MapInboundClaims = false` (czyli domyślne mapowanie wraca):

```
failed Profil_ZWaznymTokenem_ZwracaDaneUzytkownika
  [Test Failure] AssertionException: Expected to be equal to "user-42"
  but received ""

failed AdminRaport_ZTokenemAdmina_Zwraca200
  [Test Failure] AssertionException: Expected to be equal to OK
  but received Forbidden

failed AdminRaport_ZTokenemZWieluRolami_DajeDostep
  [Test Failure] AssertionException: Expected to be equal to OK
  but received Forbidden

Test run summary: Failed!
  total: 8
  failed: 3
  succeeded: 5
```

Szczegółowe wyjaśnienie dlaczego w obu przypadkach pęka inaczej (i dlaczego akurat te
testy) — sekcja 3 [`../ARTICLE.md`](../ARTICLE.md).

## Dlaczego `TestRequests.Get(...)`, a nie `fixture.Client.DefaultRequestHeaders`

TUnit domyślnie odpala testy równolegle (wydanie #2). `ApiFixture` jest współdzielony
(`SharedType.PerClass`) między wszystkimi testami jednej klasy — gdyby testy mutowały
`fixture.Client.DefaultRequestHeaders.Authorization`, dwa równolegle działające testy tej
samej klasy mogłyby nadpisać sobie nawzajem token. `TestRequests.Get(url, token)` buduje
osobny `HttpRequestMessage` z własnym nagłówkiem `Authorization` na każde wywołanie —
zero współdzielonego mutowalnego stanu, zero potrzeby `[NotInParallel]`.

## Nie zweryfikowano

`[AfterEvery(Class)]` z wieloma projektami testowymi w jednym `dotnet test` (tylko jeden
projekt testowy w tym repo), odświeżanie tokenu (`refresh_token`), `RS256`/klucz
asymetryczny (użyty tu `HS256`/klucz symetryczny — najprostszy wariant), Aspire + TUnit
(`DistributedApplicationTestingBuilder` — osobne wydanie rubryki Aspire dzisiaj).
