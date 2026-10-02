<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #9 — 2 października 2026

![TUnit](https://img.shields.io/badge/TUnit-2EA44F?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-ekspert-8250DF?style=for-the-badge)

## TUnit: `[AfterEvery(Class)]` oraz JWT w testach `WebApplicationFactory`

</div>

---

> _"401 mówi »nie wiem, kim jesteś«. 403 mówi »wiem dokładnie, kim jesteś — i to nie
> wystarczy«. Pomylenie tych dwóch w teście to pomylenie diagnozy."_

Dwa wątki z listy "następny poziom" w jednym wydaniu. Pierwszy domyka rodzinę hooków
`[AfterEvery]`: `Test` (wydanie #4) i `Assembly` (wydanie #7) już znamy — dziś brakujący
środek, `[AfterEvery(Class)]`. Drugi to naturalne pogłębienie testów API z wydań #5/#7:
realny token JWT i `[Authorize]` w `WebApplicationFactory<Program>`, ze zmierzoną (nie
zgadywaną) pułapką konfiguracji, która POTRAFI sprawić, że autoryzacja milcząco się
wyłączy. Sprawdzone na `.NET SDK 10.0.400`, `TUnit 1.72.10` (nowsza niż 1.72.4 z #7 —
zweryfikowane na NuGet), `Microsoft.AspNetCore.Authentication.JwtBearer`/
`Microsoft.AspNetCore.Mvc.Testing 10.0.12` — **8/8 testów przechodzi**, powtórzone
dwukrotnie bez flakowania.

| 🧩 Temat | 🏷️ API | 💡 W jednym zdaniu |
|---|---|---|
| Hook po każdej klasie | `[AfterEvery(HookType.Class)]` + `ClassHookContext` | raport odpalany RAZ NA KLASĘ, nie raz na assembly |
| Wyniki testów w hooku | `context.Tests` (`IReadOnlyList<TestContext>`) + `t.Execution.Result?.State` | liczysz passed/failed bez własnego licznika w każdym teście |
| Token JWT w teście | `JsonWebTokenHandler.CreateToken(SecurityTokenDescriptor)` | testy mintują token TYM SAMYM kluczem co aplikacja, nie zgadują formatu |
| Zmierzona pułapka | `MapInboundClaims` + `RoleClaimType` muszą się zgadzać | źle ustawione dają CISZĄ porażkę autoryzacji (403 zamiast 200), nie wyjątek |

---

## 1. 🏗️ Co jest pod testem

Minimalne API z dwoma chronionymi endpointami (pełny kod:
[`code/TunitWebApi/Program.cs`](code/TunitWebApi/Program.cs)):

```csharp
app.MapGet("/public/ping", () => Results.Ok(new { message = "pong", wymaga_tokenu = false }));

app.MapGet("/secure/profile", (ClaimsPrincipal user) => Results.Ok(new
{
    sub = user.FindFirstValue(JwtRegisteredClaimNames.Sub),
    name = user.Identity?.Name,
    role = user.FindAll("role").Select(c => c.Value).ToArray()
})).RequireAuthorization();

app.MapGet("/secure/admin-report", () => Results.Ok(new { raport = "tylko dla administratorow: 42 tajne liczby" }))
    .RequireAuthorization("AdminOnly");
```

`/secure/profile` wymaga TYLKO poprawnego uwierzytelnienia (dowolny ważny token).
`/secure/admin-report` ma politykę `AdminOnly` (`RequireRole("admin")`) — trzeba być nie
tylko zalogowanym, ale mieć konkretną rolę.

> ⚠️ **Klucz podpisujący JWT w tym repo jest WYŁĄCZNIE demonstracyjny**
> ([`code/TunitWebApi/JwtDemoSettings.cs`](code/TunitWebApi/JwtDemoSettings.cs)), jawny w
> publicznym repozytorium i celowo trywialny. To pokazuje MECHANIZM walidacji JWT, nie
> sposób przechowywania sekretu — prawdziwy klucz produkcyjny należy do menedżera
> sekretów (Key Vault, `user-secrets`, zmienna środowiskowa wstrzyknięta przez
> orkiestrator), nigdy do kodu w repo.

## 2. 🔑 Testy mintują token TYM SAMYM kluczem co aplikacja

Zamiast zgadywać format tokenu albo kopiować klucz do osobnej stałej w projekcie testów,
`TokenFactory` ([`code/TunitWebApi.Tests/TokenFactory.cs`](code/TunitWebApi.Tests/TokenFactory.cs))
odwołuje się przez `ProjectReference` wprost do `TunitWebApi.JwtDemoSettings` — dokładnie
tych samych stałych `Issuer`/`Audience`/`SigningKey`, których używa startup API:

```csharp
var descriptor = new SecurityTokenDescriptor
{
    Issuer = JwtDemoSettings.Issuer,
    Audience = JwtDemoSettings.Audience,
    Claims = claims,
    Expires = DateTime.UtcNow.Add(lifetime ?? TimeSpan.FromMinutes(5)),
    SigningCredentials = new SigningCredentials(
        signingKeyOverride ?? JwtDemoSettings.SigningKey, SecurityAlgorithms.HmacSha256)
};
return Handler.CreateToken(descriptor); // Microsoft.IdentityModel.JsonWebTokens.JsonWebTokenHandler
```

Testy w `AuthenticatedUserTests` sprawdzają brzegi, nie tylko ścieżkę szczęśliwą — brak
tokenu, poprawny token, token wygasły, token podpisany złym kluczem:

```csharp
[Test]
public async Task Profil_ZTokenemPodpisanymZlymKluczem_Zwraca401()
{
    var zlyKlucz = new SymmetricSecurityKey(Encoding.UTF8.GetBytes("zupelnie-inny-klucz-tez-min-32-bajty!!"));
    var token = TokenFactory.CreateToken(subject: "user-1", name: "X", signingKeyOverride: zlyKlucz);

    var response = await fixture.Client.SendAsync(TestRequests.Get("/secure/profile", token));

    await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.Unauthorized);
}
```

Realny output z tych czterech testów (pełen log w [`code/README.md`](code/README.md)):
wszystkie cztery przechodzą — brak tokenu i token z błędnym podpisem/wygasły dają
`401 Unauthorized`, poprawny token zwraca `200 OK` z poprawnymi `sub`/`name`.

> 🎯 **Dlaczego to ważne:** gdyby `TokenFactory` miał własną, zduplikowaną kopię klucza
> (zamiast odwołania do `JwtDemoSettings` aplikacji), test mógłby się "zgadzać"
> przypadkiem — a prawdziwy regres (np. ktoś zmienia klucz w API, zapomina zaktualizować
> testy) przeszedłby niezauważony, bo testy i tak podpisują TYM SAMYM (już nieaktualnym)
> kluczem co kiedyś. Jedno źródło prawdy wyklucza tę klasę błędu.

## 3. ⚠️ Pułapka zmierzona: `MapInboundClaims` + `RoleClaimType` muszą się zgadzać

To jest clou tego wydania — nie opis z dokumentacji, tylko wynik **trzech kontrolowanych
przebiegów** tego samego zestawu testów z różną konfiguracją `JwtBearerOptions`.

**Przebieg bazowy (kod w repo):** `MapInboundClaims = false` + `RoleClaimType = "role"`.
Token niesie krótki claim `"role"` (nie tłumaczony na długie URI
`ClaimTypes.Role`), a `RoleClaimType` wskazuje dokładnie na `"role"` — zgodność. Wynik:
**8/8 PASS**, w tym token admina daje `200 OK`, token zwykłego użytkownika `403 Forbidden`.

**Przebieg kontrolny #1:** usunąłem samą linię `RoleClaimType = "role"`, zostawiając
`MapInboundClaims = false`. Teraz `ClaimsIdentity` szuka roli pod DOMYŚLNYM
`RoleClaimType` (długie URI `ClaimTypes.Role`), ale token wciąż niesie krótki `"role"` —
niezgodność. Realny wynik:

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

Token admina — poprawnie podpisany, poprawnie wystawiony, z rolą `"admin"` w środku —
dostaje `403 Forbidden`. Żadnego wyjątku, żadnego logu błędu konfiguracji. Zespół
uwierzytelniania mówi "OK, to naprawdę Ty", a autoryzacja mówi "nie widzę żadnej roli" —
**cicha porażka**, dokładnie taka, jaką łatwo przegapić na produkcji, jeśli pokrywają ją
tylko testy "czy się loguje", nie testy "czy dostaje dostęp do konkretnego zasobu".

**Przebieg kontrolny #2:** przywróciłem `RoleClaimType = "role"`, ale zakomentowałem
`MapInboundClaims = false` (czyli wracam do wartości domyślnej). Tu ujawnia się DRUGA,
symetryczna strona tej samej pułapki — domyślne mapowanie ASP.NET Core tłumaczy
krótkie nazwy claimów (`sub`, `role`) na długie URI `ClaimTypes.*` AUTOMATYCZNIE. Efekt:

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

Tym razem padają TRZY testy, nie dwa — bo domyślne mapowanie przetłumaczyło też krótki
claim `sub` na inne URI (`user.FindFirstValue(JwtRegisteredClaimNames.Sub)` w
`Program.cs` szuka krótkiej nazwy i dostaje pusty string), a `RoleClaimType = "role"`
(krótkie) nie pasuje już do faktycznego (przetłumaczonego, długiego) typu claimu roli w
`ClaimsIdentity`. Dwa niezależne ustawienia, dwa kierunki tej samej niezgodności.

> 🎯 **Dlaczego to ważne:** `MapInboundClaims` i `RoleClaimType`/`NameClaimType` to PARA,
> nie dwa niezależne przełączniki. Zmieniając jedno bez drugiego, dostajesz nie błąd
> kompilacji ani wyjątek w runtime, tylko cichą, pozornie losową niezgodność uprawnień —
> w tym konkretnym przykładzie zawsze w stronę "mniej dostępu niż powinien być" (403
> zamiast 200) albo "puste dane tam, gdzie powinny być" (`sub` = `""`). Test integracyjny
> z PRAWDZIWYM tokenem i PRAWDZIWYM `[Authorize]` (nie mock `ClaimsPrincipal` wstrzyknięty
> ręcznie) to jedyny sposób, żeby złapać to przed produkcją — testy jednostkowe
> middleware'a autoryzacji by tego nie wykryły, bo problem leży dokładnie na styku
> konfiguracji JWT a konfiguracji ról.

## 4. 🔁 `[AfterEvery(Class)]`: raport po każdej klasie, nie po całym assembly

Rodzina `[AfterEvery]` ma trzy poziomy ziarnistości: `Test` (wydanie #4) → `Class` (dziś)
→ `Assembly` (wydanie #7). Sygnatura jest spójna z resztą rodziny — `static void Method
(ClassHookContext context)` zadziałała od razu, bez żadnej iteracji z kompilatorem, tak
samo jak `AssemblyHookContext` w #7:

```csharp
public static class ClassHooks
{
    private static int _invocationCount;

    [AfterEvery(Class)]
    public static void Report(ClassHookContext context)
    {
        var n = Interlocked.Increment(ref _invocationCount);

        var passed = context.Tests.Count(t => t.Execution.Result?.State == TestState.Passed);
        var failed = context.Tests.Count(t => t.Execution.Result?.State == TestState.Failed);

        Console.WriteLine($"=== [AfterEvery(Class)] wywolanie #{n}: klasa {context.ClassType.Name} ===");
        Console.WriteLine($"  Testow w klasie: {context.TestCount} (passed={passed}, failed={failed})");
    }
}
```

`ClassHookContext.ClassType` identyfikuje, która klasa właśnie się skończyła.
`ClassHookContext.Tests` (`IReadOnlyList<TestContext>`) daje dostęp do WSZYSTKICH testów
tej klasy — `t.Execution.Result?.State` (ten sam `TestState` co w `[AfterEvery(Test)]` z
#4) pozwala policzyć passed/failed bez własnego licznika rozsianego po każdym teście.

**Dowód, nie deklaracja.** Dwie niezależne klasy testowe (`AuthenticatedUserTests`,
`AdminAuthorizationTests`), każda z własnym `[ClassDataSource<ApiFixture>(Shared =
SharedType.PerClass)]` (wzorzec z #5). Realny output z przebiegu bazowego:

```
=== [AfterEvery(Class)] wywolanie #1: klasa AdminAuthorizationTests ===
  Testow w klasie: 4 (passed=4, failed=0, inne=0)
  ApiFixture.InitializeCount (globalnie, po tej klasie) = 2
=== [AfterEvery(Class)] wywolanie #2: klasa AuthenticatedUserTests ===
  Testow w klasie: 4 (passed=4, failed=0, inne=0)
  ApiFixture.InitializeCount (globalnie, po tej klasie) = 2
```

Hook odpalił się **dwa razy**, raz na klasę — kontrast z `[AfterEvery(Assembly)]` z #7,
który na tym samym kształcie projektu (dwie klasy, jeden projekt testowy) odpalił się
**raz** dla całego zestawu. `ApiFixture.InitializeCount = 2` (nie 1) potwierdza niezależnie
to samo z innej strony: `SharedType.PerClass` naprawdę tworzy osobny host na każdą klasę,
a `[AfterEvery(Class)]` naprawdę synchronizuje się z granicą klasy, nie assembly. W
przebiegu kontrolnym #1 (sekcja 3, z dwoma failami w `AdminAuthorizationTests`) hook
poprawnie zaraportował `passed=2, failed=2` — `context.Tests`/`Execution.Result` widzą
PRAWDZIWY wynik testu, nie tylko fakt, że się wykonał.

> 🎯 **Dlaczego to ważne:** `[AfterEvery(Assembly)]` (#7) nadaje się do raportu
> zbiorczego "jak poszło całe `dotnet test`". `[AfterEvery(Class)]` nadaje się do czegoś
> innego — np. publikowania metryk per-moduł/per-kontroler API w CI, albo sprzątania
> zasobu, który ma sens dopiero po zamknięciu WSZYSTKICH testów jednej klasy (gdy fixture
> jest `PerClass`, a nie `PerTest`/`PerTestSession`). Wybór między `Class` a `Assembly` to
> pytanie "na jakim poziomie agregacji ta informacja ma sens", nie kwestia gustu.

---

## ✅ Co zweryfikowano, a co nie

- ✔️ `dotnet test`: **8/8 przeszło** (TUnit 1.72.10, `Microsoft.AspNetCore.Authentication.JwtBearer`/
  `Microsoft.AspNetCore.Mvc.Testing` 10.0.12, .NET SDK 10.0.400, net10.0), powtórzone
  dwukrotnie bez flakowania. Pełny output w [`code/README.md`](code/README.md).
- ✔️ TUnit 1.72.10 to aktualna wersja na NuGet w chwili pisania (`dotnet add package TUnit
  --version "*"`) — nowsza niż 1.72.4 z wydania #7.
- ✔️ `[AfterEvery(HookType.Class)]` + `ClassHookContext` (`ClassType`, `Tests`,
  `TestCount`): sygnatura zadziałała od razu, zweryfikowana realnym dwukrotnym
  wywołaniem (po jednym na klasę), skontrastowana z jednorazowym `[AfterEvery(Assembly)]`
  z #7 na identycznym kształcie projektu (dwie klasy, jeden projekt testowy).
- ✔️ JWT + `[Authorize]`/`[Authorize(Policy=...)]` w `WebApplicationFactory<Program>`:
  brak tokenu → 401, zły podpis → 401, token wygasły → 401, brak wymaganej roli → 403,
  poprawny token z rolą → 200 — wszystkie ścieżki zmierzone realnym `dotnet test`, nie
  założone.
- ✔️ Pułapka `MapInboundClaims`/`RoleClaimType`: zmierzona TRZEMA kontrolowanymi
  przebiegami (bazowy 8/8, kontrolny #1 ze zdjętym `RoleClaimType` → 2 faile, kontrolny #2
  ze zdjętym `MapInboundClaims = false` → 3 faile), nie wywnioskowana z dokumentacji.
  Oba kontrolne przebiegi NIE weszły do repo — kod w `code/` to wyłącznie wariant
  bazowy (8/8).
- ⚠️ Nie testowałem: `[AfterEvery(Class)]` z wieloma projektami testowymi w jednym
  `dotnet test` (analogiczne pytanie zostawione otwarte dla `[AfterEvery(Assembly)]` w
  #7 — nadal mam tylko jeden projekt testowy w repo), odświeżanie tokenu
  (`refresh_token`)/`RS256`+klucz asymetryczny (użyłem HMAC/`HS256`, najprostszy
  symetryczny wariant), Aspire + TUnit (`DistributedApplicationTestingBuilder` — temat
  świadomie pominięty, zajmuje się nim dziś osobne wydanie rubryki Aspire).

**Pełny, uruchamialny przykład:** [`code/TunitWebApi/`](code/TunitWebApi/) (API z JWT) +
[`code/TunitWebApi.Tests/`](code/TunitWebApi.Tests/) (testy).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — komendy + prawdziwy output `dotnet test`.

---

<div align="center">

[← wróć do wydania #9 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
