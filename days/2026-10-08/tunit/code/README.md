# Kod do wydania #15 — TUnit: rotacja kluczy z wyprzedzeniem i klucze z certyfikatów X.509

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej fragment + jak odpalić kod.

Wymagania: **.NET 10 SDK** (sprawdzone na `10.0.400`), dostęp do NuGet. Podstawy: wydania #13–#14 (JWT RS256,
JWKS po HTTP, rotacja kluczy).

## Fragment prasówki, którego dotyczy ten kod

> Wystawca publikuje w JWKS **certyfikaty X.509** (`x5c`, `x5t#S256`), a walidator pobiera je po HTTP.
> Zmierzone: gdy klucz jest opublikowany i walidator zdążył odświeżyć JWKS **przed** aktywacją, pierwszy
> token z nowym kluczem dostaje `200` (bez dodatkowych pobrań JWKS); w odwrotnej kolejności `401`.
> **Wygasły** lub **jeszcze nieważny** certyfikat nadal podpisuje tokeny przyjmowane przez `JwtBearer` (`200`),
> dopóki sami nie dodamy sprawdzenia dat w `IssuerSigningKeyValidator` (wtedy `401`). Dwie instancje wystawcy
> z kolejnymi `kid` (`key-1`) mają identyczne `kid` dla różnych kluczy.

> ⚠️ **Nigdy do produkcji.** Certyfikaty są samopodpisane i efemeryczne (w pamięci), użytkownik `alice` /
> `demo-only-password` jest jawny w kodzie, `RequireHttpsMetadata = false` (demo na `http://127.0.0.1`).

## Struktura

```
global.json                 # "test": { "runner": "Microsoft.Testing.Platform" } -- WYMAGANE
CertKeys.slnx
IssuerApi/                  # KeyRing na certyfikatach X.509 (Add/Activate/Retire), JWKS z x5c, discovery
ResourceApi/                # JwtBearer + MetadataAddress, IssuerSigningKeyValidator (sonda + opcjonalna walidacja dat)
CertTests/                  # TUnit, 10 wynikow
├── Env.cs                  # Issuer i Validator: prawdziwe serwery Kestrel na losowych portach
└── CertKeyTests.cs         # rotacja z wyprzedzeniem, zawartosc JWKS/tokenu, waznosc certyfikatu, dwie instancje
```

Pakiety: `TUnit 1.72.16` (CertTests), `Microsoft.AspNetCore.Authentication.JwtBearer 10.0.12`
(IssuerApi, ResourceApi).

## Jak odpalić od zera

```bash
cd code
dotnet test --solution CertKeys.slnx --results-directory /tmp/tunit-certkeys-results
```

Uruchamiaj z folderu `code/` (tam jest `global.json`). Zmierzone w mojej sesji: `dotnet test --solution ...`
z katalogu bez `global.json` w górę drzewa kończy się `MSB1001: Unknown switch`; użyłem tymczasowego
`global.json` poza repo. Sama sekwencja `cd code` + komenda nie była uruchamiana.

Z liniami `[pomiar]`:

```bash
dotnet test --solution CertKeys.slnx --results-directory /tmp/tunit-certkeys-results --output Detailed
```

## Prawdziwy output (10/10, jeden przebieg)

```
Test run summary: Passed!
  total: 10
  failed: 0
  succeeded: 10
  skipped: 0
  duration: 11s 267ms
```

Linie `[pomiar]` z `--output Detailed`:

```
[pomiar] naglowek tokenu: {"alg":"RS256","kid":"R4Th7b34qffFHz0VXJMWrgrIlZmWlOCcOL7SPYpGvy0","x5t":"7knf-llL-6EIP0e55EVfuEChbpA","typ":"JWT"}
[pomiar] pola JWKS: kty,use,alg,kid,n,e,x5c,x5t#S256
[pomiar] kid==x5t#S256: True; cert.Subject=CN=demo-issuer-1; HasPrivateKey(z DER)=False
[pomiar] cert=expired egzekwowanie=False -> status=200 typy-kluczy-w-walidatorze=X509SecurityKey
[pomiar] cert=expired egzekwowanie=True -> status=401 typy-kluczy-w-walidatorze=X509SecurityKey
[pomiar] cert=not-yet-valid egzekwowanie=False -> status=200 typy-kluczy-w-walidatorze=X509SecurityKey
[pomiar] cert=not-yet-valid egzekwowanie=True -> status=401 typy-kluczy-w-walidatorze=X509SecurityKey
[pomiar] odswiezenie-przed-aktywacja=True (udane=True) pierwszy-status=200 pobrania-JWKS: przed-aktywacja=2 po-pierwszym-zadaniu=2
[pomiar] odswiezenie-przed-aktywacja=False (udane=True) pierwszy-status=401 pobrania-JWKS: przed-aktywacja=1 po-pierwszym-zadaniu=2
[pomiar] kid=Thumbprint: kidA==kidB: False; token B u walidatora A -> 401; pobrania JWKS u A: 1 -> 2
[pomiar] kid=Sequential: kidA==kidB: True; token B u walidatora A -> 401; pobrania JWKS u A: 1 -> 2
```

## Nie zweryfikowano

Drugi i kolejne przebiegi (flakowanie — po pierwszym przebiegu środowisko przestało zezwalać na polecenia);
walidacja łańcucha `x5c` i CRL/OCSP; certyfikaty z prawdziwego CA; JWKS przez HTTPS; wspólny JWKS z balanserem;
okno publikacja→aktywacja dłuższe niż `AutomaticRefreshInterval`; mechanizm, dla którego odrzucony podpis przy
znanym `kid` też zwiększa licznik pobrań JWKS; SDK inne niż `10.0.400`.

Artefakty: po testach zostały `bin/` i `obj/` (wykluczone przez `.gitignore` w tym katalogu).
