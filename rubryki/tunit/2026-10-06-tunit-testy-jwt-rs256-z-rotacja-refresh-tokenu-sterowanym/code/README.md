# Kod do wydania #13 — TUnit: JWT RS256, rotacja refresh tokenu, `FakeTimeProvider`, wspólny `AuthTestKit`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej fragment + jak odpalić kod.

Wymagania: **.NET 10 SDK** (sprawdzone na `10.0.400`). Podstawy: wydania #1–#12, w
szczególności #5 (`WebApplicationFactory` + TUnit), #9 (JWT w testach, `MapInboundClaims`),
#12 (kilka projektów testowych = kilka procesów).

## Fragment prasówki, którego dotyczy ten kod

> W wydaniu #9 testowaliśmy JWT podpisany **symetrycznie** (HS256) i zostawiliśmy otwarte
> trzy pytania: klucze asymetryczne, odświeżanie tokenu i wspólny kod między projektami
> testowymi. Dziś wszystkie trzy w jednym wydaniu — i dowód, że testy bezpieczeństwa
> **naprawdę łapią błędy**.
>
> RS256: wystawca trzyma klucz prywatny, walidator dostaje wyłącznie publiczny (`KeyMaterial.
> ValidationKey`, bez składowych prywatnych). Czas w aplikacji pochodzi z `TimeProvider`,
> a fixture podmienia go na `FakeTimeProvider` — testy "przeżywają" 7 dni w milisekundy.
> Refresh token jest jednorazowy; ponowne użycie zużytego unieważnia całą rodzinę.
> Osiem wariantów fałszerstwa (`alg:none`, algorithm confusion HS256 z kluczem publicznym,
> zły klucz, zły `aud`/`iss`, podmieniony payload, wygasły) → `401`, a test kontrolny → `200`.
> Mutacja `RequireSignedTokens=false` oblała dokładnie jeden test (`alg-none` dostał `200`);
> usunięcie `ValidAlgorithms` nie oblało żadnego (obrona w głąb).

> ⚠️ **Nigdy do produkcji.** Klucz RSA jest efemeryczny (generowany w pamięci przy starcie),
> użytkownik `alice` / hasło `demo-only-password` jest jawne w kodzie, magazyn refresh
> tokenów jest w pamięci. To demonstracja mechaniki, nie wzorzec zarządzania kluczami i
> użytkownikami.

## Struktura

```
global.json                      # "test": { "runner": "Microsoft.Testing.Platform" } -- WYMAGANE
TunitRs256.slnx
AuthApi/                         # Web API (bez testów)
├── KeyMaterial.cs               # para RSA: SigningKey (prywatny) / ValidationKey (publiczny)
├── TokenService.cs              # wystawianie access tokenu RS256, czas z TimeProvider
├── RefreshTokenStore.cs         # rotacja + reuse detection (SHA-256 tokenu)
└── Program.cs                   # /auth/login, /auth/refresh, /secure/profile, /.well-known/jwks.json
AuthTestKit/                     # biblioteka wspólna (ProjectReference -> AuthApi)
├── AuthFixture.cs               # WebApplicationFactory<Program> + klucz RSA testu + FakeTimeProvider
├── AuthClient.cs                # helpery HTTP (Login/Refresh/GetProfile)
├── Forge.cs                     # fabryka tokenów, w tym 8 wariantów fałszerstw
└── KitHooks.cs                  # [AfterEvery(Assembly)] zdefiniowany W BIBLIOTECE
AuthApi.Tests/                   # TUnit, 6 testów  [Category("lifecycle")], SharedType.None
AuthApi.Security.Tests/          # TUnit, 9 testów  [Category("security")], SharedType.PerTestSession
```

Pakiety: `TUnit 1.72.16` (oba projekty testowe), `TUnit.Core 1.72.16` + `Microsoft.AspNetCore.Mvc.Testing
10.0.12` + `Microsoft.Extensions.TimeProvider.Testing 10.10.0` (AuthTestKit),
`Microsoft.AspNetCore.Authentication.JwtBearer 10.0.12` (AuthApi).

## Jak odpalić od zera

```bash
cd code
dotnet test --solution TunitRs256.slnx --results-directory /tmp/tunit-rs256-results
```

Uruchamiaj z folderu `code/` — tam jest `global.json` przełączający `dotnet test` na tryb
Microsoft.Testing.Platform. Z katalogu bez takiego pliku (ani wyżej w drzewie) komenda kończy
się `MSB1001: Unknown switch` na `--solution` (zmierzone). W tej sesji sprawdziłem to
mechanizmem tymczasowego `global.json` w katalogu nadrzędnym; bezpośrednio `cd code` + komendy
nie uruchamiałem.

Pełny log (z logami aplikacji przy każdym teście): dodaj `--output Detailed`.

Tylko jedna kategoria (UWAGA na kod wyjścia 8 — patrz niżej):

```bash
dotnet test --solution TunitRs256.slnx --results-directory /tmp/tunit-rs256-results --treenode-filter "/*/*/*/*[Category=security]" --ignore-exit-code 8
```

Jeden projekt:

```bash
dotnet test --project AuthApi.Security.Tests --results-directory /tmp/tunit-rs256-results
```

## Prawdziwy output (15/15, przebieg bez `--output Detailed`)

```
Running tests from .../AuthApi.Security.Tests/bin/Debug/net10.0/AuthApi.Security.Tests.dll (net10.0|x64)
Running tests from .../AuthApi.Tests/bin/Debug/net10.0/AuthApi.Tests.dll (net10.0|x64)
.../AuthApi.Tests.dll (net10.0|x64) passed (4s 650ms)
.../AuthApi.Security.Tests.dll (net10.0|x64) passed (5s 728ms)

Test run summary: Passed!
  total: 15
  failed: 0
  succeeded: 15
  skipped: 0
  duration: 6s 339ms
```

Nazwy testów widoczne w `--output Detailed` (dzięki `[DisplayName]`), m.in.:

```
passed KONTROLA: token podpisany kluczem aplikacji jest akceptowany
passed Atak alg-none -> 401
passed Atak hs256-public-key-der-as-secret -> 401
passed Atak hs256-public-key-pem-as-secret -> 401
passed Atak wrong-audience -> 401
passed Atak wrong-issuer -> 401
passed Atak tampered-payload -> 401
passed Atak expired-1s-ago -> 401
passed Atak attacker-rsa-key -> 401
passed Access token zyje 60 s: 59 s OK, 61 s -> 401 (bez Thread.Sleep)
passed Reuse detection: ponowne uzycie zuzytego refresh tokenu uniewaznia CALA rodzine
passed Refresh token wygasa po 7 dniach
```

Hooki `[AfterEvery(Assembly)]` (w tym ten z biblioteki `AuthTestKit`) w jednym przebiegu:

```
=== [AuthTestKit] hook zdefiniowany W BIBLIOTECE, odpalony dla assembly AuthApi.Tests ===
=== [AuthApi.Tests] [AfterEvery(Assembly)] PID=641969 testow=6 AuthFixture.InitializeCount=6 ===
=== [AuthTestKit] hook zdefiniowany W BIBLIOTECE, odpalony dla assembly AuthApi.Security.Tests ===
=== [AuthApi.Security.Tests] [AfterEvery(Assembly)] PID=641967 testow=9 AuthFixture.InitializeCount=1 ===
```

### Filtr kategorii bez dopasowań w jednym projekcie (zmierzone)

Bez `--ignore-exit-code 8`:

```
.../AuthApi.Tests.dll (net10.0|x64) Zero tests ran (812ms)
Exit code: 8
.../AuthApi.Security.Tests.dll (net10.0|x64) passed (2s 847ms)

Test run summary: Failed!
  error: 1
  total: 9
  failed: 0
  succeeded: 9
Test run completed with non-success exit code: 8
```

Z `--ignore-exit-code 8`: `Test run summary: Passed!`, `total: 9`, `succeeded: 9`.

## Eksperyment: czy te testy potrafią oblać (mutacje)

W `AuthApi/Program.cs`, w `TokenValidationParameters`:

| Mutacja | Wynik `AuthApi.Security.Tests` |
|---|---|
| usunięcie linii `ValidAlgorithms = [RS256]` | `total: 9, failed: 0` — brak porażek (obrona w głąb) |
| `RequireSignedTokens = false` | `total: 9, failed: 1` — `Atak alg-none -> 401`: `Expected to be equal to Unauthorized but received OK` |

Po obu mutacjach kod został przywrócony do oryginału (wersja w repo jest bezpieczna).
Spróbuj sam: zmień, uruchom `dotnet test --project AuthApi.Security.Tests`, cofnij.

## Nie zweryfikowano

Rotacja kluczy z wieloma `kid` w JWKS, pobieranie JWKS przez `ConfigurationManager`, test
wyścigu przy jednoczesnym odświeżaniu tym samym tokenem, RS256 z certyfikatem X.509, SDK inne
niż `10.0.400`. Mechanizm, dla którego hook z biblioteki pomocniczej się odpala, nie był
badany (zmierzony został tylko sam fakt).

Uwaga o artefaktach: po testach w katalogach projektów zostały `bin/` i `obj/` (środowisko
odrzuciło ich usunięcie); `.gitignore` w tym katalogu je wyklucza.
