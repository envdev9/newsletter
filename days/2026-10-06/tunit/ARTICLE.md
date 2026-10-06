<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #13 — 6 października 2026

![TUnit](https://img.shields.io/badge/TUnit-2EA44F?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-ekspert-8250DF?style=for-the-badge)
![JWT](https://img.shields.io/badge/JWT-RS256-D63384?style=for-the-badge)

## TUnit: testy JWT RS256 z rotacją refresh tokenu, sterowanym zegarem i wspólnym `TestKit` między projektami

</div>

---

> _"Test, który nie potrafi oblać, niczego nie dowodzi. Dlatego dziś oblewamy własny kod — celowo."_

W wydaniu #9 testowaliśmy JWT podpisany **symetrycznie** (HS256: ten sam sekret podpisuje
i weryfikuje) i zostawiliśmy otwarte trzy pytania: klucze asymetryczne, odświeżanie tokenu i
wspólny kod między projektami testowymi. Dziś wszystkie trzy w jednym wydaniu — i dowód, że
testy bezpieczeństwa **naprawdę łapią błędy**, a nie tylko świecą się na zielono.

Sprawdzone: `.NET SDK 10.0.400`, **`TUnit 1.72.16`** (najnowsza na NuGet w chwili pisania —
`dotnet add package TUnit` bez numeru wersji dociągnął właśnie ją),
`Microsoft.AspNetCore.Mvc.Testing 10.0.12`, `Microsoft.Extensions.TimeProvider.Testing 10.10.0`.
`dotnet test` na solution: **15/15 testów**, powtórzone trzykrotnie (w tym raz z pełnym logiem),
za każdym razem zielono.

| 🧩 Pytanie | 🏷️ Jak zmierzone | 💡 Wynik |
|---|---|---|
| Czy atakujący z kluczem publicznym (z JWKS!) sfałszuje token? | 8 wariantów ataku w jednym teście parametryzowanym | wszystkie 8 → `401`, a test kontrolny (legalny token) → `200` |
| Która linia konfiguracji realnie chroni przed `alg: none`? | mutacja: `RequireSignedTokens = false` | **dokładnie 1 test padł** — `alg-none` dostał `200 OK` |
| Czy biała lista algorytmów (`ValidAlgorithms`) jest konieczna? | mutacja: usunięcie linii | **nie padł żaden test** (obrona w głąb, nie jedyna zapora) |
| Czy fixture z biblioteki wspólnej jest jedna na wszystkie projekty testowe? | licznik statyczny + PID w obu projektach | nie — dwa procesy, dwa liczniki |
| Czy `--treenode-filter` bez dopasowań w jednym z projektów jest OK? | filtr `Category=security` na solution z 2 projektami | **nie**: kod wyjścia 8, run oznaczony jako `Failed!` |

---

## 1. 🔑 Dlaczego RS256, a nie HS256

W HS256 **każdy, kto potrafi zweryfikować token, potrafi go też podpisać** (ten sam sekret).
Dla jednego monolitu to akceptowalne; dla kilku serwisów weryfikujących tokeny z jednego
wystawcy — każdy serwis staje się potencjalnym fałszerzem. W RS256 wystawca trzyma klucz
**prywatny**, a reszta świata dostaje tylko **publiczny** (zwykle jako JWKS pod
`/.well-known/jwks.json`). Weryfikować może każdy, podpisać — nikt poza wystawcą.

W kodzie z tego wydania rozdziela to jedna mała klasa `KeyMaterial`: ma `SigningKey` (z
częścią prywatną — używany tylko do wystawiania tokenów) i `ValidationKey` (zbudowany z
`ExportParameters(includePrivateParameters: false)` — **fizycznie nie da się nim niczego
podpisać**). `JwtBearer` dostaje wyłącznie ten drugi. Para kluczy aplikacji jest
**efemeryczna** (nowa przy każdym starcie procesu) — w repo nie ma żadnego klucza prywatnego.

> ⚠️ **Nigdy do produkcji:** efemeryczny klucz w pamięci procesu to wygoda demo. Produkcyjny
> klucz prywatny żyje w KMS/HSM/Key Vault, ma rotację i wiele `kid` w JWKS naraz. Hasło
> `demo-only-password` użytkownika `alice` jest jawne w kodzie wyłącznie dla przykładu.

Test `Jwks_ExposesOnlyPublicKey` sprawdza, że JWKS zawiera `kty/n/e`, a **nie zawiera**
żadnej ze składowych prywatnych RSA (`d, p, q, dp, dq, qi`).

> 🎯 **Dlaczego to ważne:** wyciek składowej prywatnej do endpointu publicznego to katastrofa
> niewidoczna w żadnym teście funkcjonalnym — aplikacja działa idealnie, a każdy może
> podpisywać tokeny. Taki test kosztuje 10 linijek.

## 2. ⏱️ Zegar sterowany z testu zamiast `Thread.Sleep`

Access token żyje 60 sekund, refresh token 7 dni. Nikt nie chce czekać tygodnia w CI.
Rozwiązanie: aplikacja nie woła `DateTime.UtcNow`, tylko wstrzykniętego `TimeProvider`
(`TimeProvider.System` w produkcji), a fixture podmienia go na `FakeTimeProvider`:

```csharp
builder.ConfigureTestServices(services =>
{
    services.RemoveAll<KeyMaterial>();
    services.AddSingleton(new KeyMaterial(TestRsa));   // klucz trzymany przez TEST
    services.RemoveAll<TimeProvider>();
    services.AddSingleton<TimeProvider>(Time);         // FakeTimeProvider
});
```

I test, który „przeżywa" tydzień w ułamku sekundy (pełny `[Test]` w `TokenLifecycleTests.cs`):

```csharp
f.Time.Advance(TimeSpan.FromSeconds(59));
var before = await f.GetProfileAsync(tokens.AccessToken);   // 200
f.Time.Advance(TimeSpan.FromSeconds(2));
var after  = await f.GetProfileAsync(tokens.AccessToken);   // 401
```

Dwa szczegóły, które mają znaczenie:

- Walidację czasu życia w `JwtBearer` robi własny `LifetimeValidator` czytający ten sam
  `TimeProvider` — inaczej middleware i tak patrzyłoby na prawdziwy zegar systemowy i test
  byłby bez sensu. `ClockSkew = TimeSpan.Zero`, żeby granica 60 s była ostra.
- Opcje `JwtBearer` budujemy z DI (`AddOptions<JwtBearerOptions>(...).Configure<KeyMaterial,
  TimeProvider>(...)`), **nie** z konfiguracji czytanej eagerly w `Program.cs`. Dzięki temu
  `ConfigureTestServices` podmienia klucz i zegar bez żadnych hacków. (Że to jest
  konieczne w każdym układzie — nie sprawdzałem; w tym kodzie po prostu działa.)

Ponieważ testy przesuwają zegar, klasa używa `Shared = SharedType.None` — **każdy test dostaje
własny host i własny zegar**. Wspólny zegar to wspólny stan, czyli flaky testy w kolejności
zależnej od planisty (patrz wydanie #5).

> 🎯 **Dlaczego to ważne:** testy wygasania zwykle robi się `Thread.Sleep` (wolne, flaky) albo
> w ogóle się ich nie robi (i wygasanie psuje się po cichu). `FakeTimeProvider` daje
> determinizm i granicę „59 s ok, 61 s nie" sprawdzoną co do sekundy.

## 3. 🔄 Rotacja refresh tokenu i wykrywanie ponownego użycia

Refresh token jest jednorazowy. Każdy `/auth/refresh` zużywa stary token i wydaje nowy z tej
samej „rodziny". Najciekawszy przypadek to **reuse detection**: jeśli ktoś przedłoży token
już zużyty, zakładamy kradzież i unieważniamy **całą rodzinę** — także najnowszy token
uczciwego klienta. Test odtwarza scenariusz kradzieży:

```csharp
var r1 = (await f.LoginAsync()).RefreshToken;
var rotate = await f.RefreshAsync(r1);                 // r1 -> r2 (legalnie)
var r2 = (await rotate.Content.ReadFromJsonAsync<TokenResponse>())!.RefreshToken;

var replay = await f.RefreshAsync(r1);                 // złodziej: zużyty r1  -> 401
var victim = await f.RefreshAsync(r2);                 // legalny r2 też       -> 401
```

Magazyn trzyma tylko **SHA-256 tokenu**, nigdy sam token, i jest w pamięci (demo — nie
przeżyje restartu, nie skaluje się na wiele instancji). Osobny test sprawdza, że refresh
token wygasa po 7 dniach: `7 dni − 1 s` → `200`, a po kolejnych 7 dniach → `401`.

> 🎯 **Dlaczego to ważne:** bez reuse detection skradziony refresh token to klucz do konta
> na tydzień, a właściciel niczego nie zauważy. Z nim: pierwsza próba użycia kopii
> wylogowuje obu — i ten test jest jedyną rzeczą, która pilnuje, żeby tak pozostało po
> refaktoryzacji.

## 4. 🗡️ Katalog ataków: jeden test, osiem fałszerstw

Projekt `AuthApi.Security.Tests` ma jeden test parametryzowany po nazwie ataku
(`[MethodDataSource]` + `[DisplayName("Atak $attack -> 401")]`) i fabrykę `Forge`:

| Atak | Co robi |
|---|---|
| `attacker-rsa-key` | poprawny RS256, ale podpisany kluczem atakującego |
| `alg-none` | nagłówek `"alg":"none"`, pusty podpis, `sub=admin` |
| `hs256-public-key-der-as-secret` | klasyczne „algorithm confusion": HS256, a sekretem są bajty klucza **publicznego** (DER) |
| `hs256-public-key-pem-as-secret` | to samo, sekretem jest tekst PEM klucza publicznego |
| `wrong-audience` / `wrong-issuer` | prawidłowy podpis, zły `aud` / `iss` |
| `tampered-payload` | prawdziwy nagłówek i podpis, podmieniony payload (`sub=admin`) |
| `expired-1s-ago` | prawidłowy podpis, `exp` sekundę temu |

Obok jest **test kontrolny**: token podpisany kluczem aplikacji → `200`. Bez niego `401`
z ataków mogłoby oznaczać po prostu „cała autoryzacja jest zepsuta".

W nazwach testów TUnit podstawił nazwę ataku do `$attack` — w wyniku `dotnet test` widać
`passed Atak alg-none -> 401`, `passed Atak tampered-payload -> 401` itd., zamiast
bezimiennych `ForgedToken_IsRejected(attack: "…")`.

## 5. 🧬 Mutacje: czy te testy w ogóle potrafią oblać?

Zielone testy bezpieczeństwa są podejrzane, dopóki nie zobaczysz ich czerwonych. Zrobiłem dwie
ręczne mutacje `TokenValidationParameters` i uruchomiłem projekt bezpieczeństwa (po obu
mutacjach przywróciłem oryginał):

**Mutacja A — usunięta `ValidAlgorithms = [RS256]`:** `total: 9, failed: 0` — **nic nie padło**.
Powód (wniosek z wyniku, nie z dokumentacji): `HS256` z kluczem publicznym RSA jako sekretem
i tak jest odrzucany, bo klucz w `IssuerSigningKey` jest typu RSA i nie nadaje się do
weryfikacji HMAC. Biała lista algorytmów to więc **obrona w głąb**: zostawiam ją, ale ten
zestaw testów nie udowodni, że jest potrzebna. Uczciwa lekcja: test, który nie padł po
usunięciu zabezpieczenia, nie pokrywa tego zabezpieczenia.

**Mutacja B — `RequireSignedTokens = false`:** `total: 9, failed: 1, succeeded: 8`. Padł
dokładnie `alg-none`, a komunikat asercji to realne:

```
failed Atak alg-none -> 401 (741ms)
  [Test Failure] AssertionException: Expected to be equal to Unauthorized
but received OK
```

Niepodpisany token z `sub=admin` został wpuszczony. Ten jeden parametr stoi między Tobą a
nieograniczonym podszywaniem się pod dowolnego użytkownika.

> 🎯 **Dlaczego to ważne:** mutacje (nawet ręczne, dwie linijki) odpowiadają na pytanie, na
> które sam kod testowy nie odpowie: *czy ten test coś chroni?* Dla testów bezpieczeństwa to
> jedyny uczciwy sposób.

## 6. 🧱 Trzy projekty i `ProjectReference` między nimi

Układ solution (`TunitRs256.slnx`):

```
AuthApi/                 # Web API: RS256, JWKS, login, refresh (bez testów)
AuthTestKit/             # biblioteka (NIE projekt testowy): AuthFixture, AuthClient, Forge
  └─ ProjectReference → AuthApi
AuthApi.Tests/           # TUnit: cykl życia tokenów (6 testów)
  └─ ProjectReference → AuthTestKit
AuthApi.Security.Tests/  # TUnit: katalog ataków (9 testów)
  └─ ProjectReference → AuthTestKit
```

Wspólny kod testowy (fixture, helpery HTTP, fabryka fałszywych tokenów) mieszka w osobnej
bibliotece `AuthTestKit`, zamiast być skopiowany do obu projektów (jak w #12). Biblioteka
referencjonuje tylko `TUnit.Core` (typy atrybutów i `IAsyncInitializer`), nie pełny pakiet `TUnit` —
runnerem pozostają dwa projekty testowe.

Trzy zmierzone fakty:

1. **`[ClassDataSource<AuthFixture>]` z typem z innej assembly działa** — bez żadnych
   dodatkowych zabiegów. `AuthApi.Tests` (`SharedType.None`, 6 testów) zakończył z
   `AuthFixture.InitializeCount=6`; `AuthApi.Security.Tests` (`SharedType.PerTestSession`,
   9 testów) z `InitializeCount=1`.
2. **Wspólna biblioteka ≠ wspólny proces.** PID-y z jednego przebiegu: `641969` i `641967`.
   Statyczne liczniki z `AuthTestKit` są osobne w każdym projekcie testowym (te same liczniki
   z 6 i 1 powyżej) — `PerTestSession` oznacza „raz na przebieg *tego procesu*", nie raz na
   cały `dotnet test` (dowód procesowy z wydania #12 dostał tu drugie potwierdzenie).
3. **Hook `[AfterEvery(Assembly)]` zdefiniowany w bibliotece pomocniczej odpalił się** — raz dla
   każdego projektu testowego, z `context.Assembly` wskazującym na ten **testowy** projekt
   (`AuthApi.Tests`, potem `AuthApi.Security.Tests`). Zmierzyłem sam fakt; mechanizmu
   (generator źródeł vs. odkrywanie w czasie wykonania) nie badałem — i nie sprawdzałem, czy to
   gwarantowane przez TUnit w kolejnych wersjach, więc nie opieraj na tym krytycznej logiki
   bez własnego testu regresyjnego.

> 🎯 **Dlaczego to ważne:** `TestKit` jako biblioteka to naturalny krok, gdy testy
> integracyjne rosną — jedna fixture, jedna fabryka danych, wiele projektów. Ale pamiętaj
> o procesach: wspólny **kod** nie jest wspólnym **stanem**.

## 7. 🏷️ `[Category]`, `--treenode-filter` i pułapka kodu wyjścia 8

Klasy mają `[Category("lifecycle")]` i `[Category("security")]`. Filtr po kategorii (na
poziomie solution z dwoma projektami):

```
dotnet test --solution TunitRs256.slnx --treenode-filter "/*/*/*/*[Category=security]"
```

Realny wynik: projekt `AuthApi.Security.Tests` — `passed (2s 847ms)`, 9 testów. Projekt
`AuthApi.Tests` — **`Zero tests ran`, `Exit code: 8`**, a całość kończy się:

```
Test run summary: Failed!
  ...
  error: 1
Test run completed with non-success exit code: 8
```

Czyli filtr, który w jednym z projektów niczego nie dopasował, **wywraca cały przebieg** —
dokładnie to, czego nie chcesz w pipeline'ie CI uruchamiającym „tylko testy bezpieczeństwa".
Rozwiązanie sprawdzone na tej maszynie: `--ignore-exit-code 8` →
`Test run summary: Passed!`, `total: 9, succeeded: 9`.

> 🎯 **Dlaczego to ważne:** kategorie + filtr to sposób na szybkie „smoke" i osobne etapy CI,
> ale w solution z wieloma projektami domyślnie zero dopasowań = czerwony build. Dodaj
> `--ignore-exit-code 8` świadomie (pamiętając, że ukrywa też sytuację „literówka w filtrze,
> nie uruchomiono nic").

Drobne spostrzeżenie: w `--output Detailed` każdy test wypisuje logi całej aplikacji
(`Microsoft.AspNetCore.*`) — TUnit zbiera standardowe wyjście testu i pokazuje je przy teście.
Przy porażce (jak w mutacji B) to sporo hałasu, ale dokładnie tam masz ślad, że
`/secure/profile` zwrócił `200`.

---

## ✅ Co zweryfikowano, a co nie

- ✔️ `dotnet test --solution TunitRs256.slnx`: **15/15** (6 `AuthApi.Tests` + 9
  `AuthApi.Security.Tests`), TUnit 1.72.16, .NET SDK 10.0.400, net10.0 — trzy pełne przebiegi,
  wszystkie zielone; pierwszy przebieg: `duration: 6s 858ms`.
- ✔️ RS256: nagłówek tokenu `alg=RS256` + `kid` (asercja na `JsonWebToken.Alg/Kid`); JWKS bez
  składowych prywatnych.
- ✔️ 8 wariantów fałszerstwa → `401`, kontrola → `200`; mutacja `RequireSignedTokens=false` →
  1 porażka (`alg-none` → `200`); usunięcie `ValidAlgorithms` → 0 porażek.
- ✔️ Rotacja refresh tokenu, reuse detection (całą rodzinę), wygasanie 60 s / 7 dni na
  `FakeTimeProvider`.
- ✔️ Trzy projekty z `ProjectReference` (`AuthTestKit` → `AuthApi`; oba testowe → `AuthTestKit`);
  `[ClassDataSource<T>]` z typem z biblioteki; różne PID-y; hook `[AfterEvery(Assembly)]` z
  biblioteki odpalił się dla obu projektów testowych.
- ✔️ `--treenode-filter "/*/*/*/*[Category=security]"` → w projekcie bez dopasowań exit code 8 →
  `Failed!`; z `--ignore-exit-code 8` → `Passed!`.
- ⚠️ Uruchomienie `dotnet test` z korzenia repo (bez `global.json` w katalogu roboczym lub
  powyżej) **nie zadziałało**: SDK przełącza się na tryb VSTest i kończy `MSB1001: Unknown
  switch` na `--solution`/`--project`. Obejście: uruchamiać z `code/` (tam leży `global.json`
  z `"runner": "Microsoft.Testing.Platform"`). Zweryfikowałem to mechanizm tymczasowym
  `global.json` w katalogu nadrzędnym (usunięty po testach); samej komendy `cd code` +
  `dotnet test` w tej sesji nie uruchamiałem — środowisko nie pozwala na `cd x && …`.
- ⚠️ **Niezweryfikowane:** rotacja kluczy (kilka `kid` w JWKS, walidacja po `kid`), pobieranie
  JWKS przez `ConfigurationManager`/`MetadataAddress` zamiast statycznego klucza, współbieżne
  odświeżanie tym samym tokenem (jest `lock`, ale nie ma testu wyścigu), RS256 z certyfikatem
  X.509 (temat rubryki o certyfikatach), działanie na SDK innych niż 10.0.400.
- ⚠️ Nie udało się usunąć katalogów `bin/` i `obj/` po testach (środowisko odrzuciło
  `rm -r`); są wykluczone przez `code/.gitignore` i nie powinny trafić do commita.

**Pełny, uruchamialny przykład:** [`code/`](code/) — solution
[`TunitRs256.slnx`](code/TunitRs256.slnx).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — komendy + prawdziwy output `dotnet test`.

---

<div align="center">

[← wróć do wydania #13 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
