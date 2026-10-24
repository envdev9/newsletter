# Kod do wydania #14 — TUnit: rotacja kluczy JWKS po prawdziwym HTTP i wyścig refresh tokenu

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej fragment + jak odpalić kod.

Wymagania: **.NET 10 SDK** (sprawdzone na `10.0.400`), dostęp do NuGet. Podstawy: wydania #1–#13, w
szczególności #13 (JWT RS256, refresh token z rotacją).

## Fragment prasówki, którego dotyczy ten kod

> Serwis walidujący tokeny jest osobnym procesem, który **pobiera JWKS od wystawcy przez HTTP**, a
> wystawca wymienia klucze. Test uruchamia dwa prawdziwe serwery Kestrel (losowe porty) i liczy
> pobrania JWKS po stronie wystawcy. Zmierzone: pierwszy token z nowym `kid` dostaje `401`, kolejne
> `200`; 20 tokenów z wymyślonym `kid` to tylko 2 pobrania JWKS; **wycofany klucz nadal działa**
> po odświeżeniu JWKS (do skrócenia `LastKnownGoodLifetime`); wyścig 32 żądań `/auth/refresh` ma
> jednego zwycięzcę, a mutacja (usunięty `lock`) przeżyła test HTTP i padła dopiero na teście
> z wątkami (1 na 21 przebiegów).

> ⚠️ **Nigdy do produkcji.** Klucze RSA są efemeryczne (w pamięci), użytkownik `alice` /
> `demo-only-password` jest jawny w kodzie, magazyn refresh tokenów jest w pamięci,
> `RequireHttpsMetadata = false` (demo na `http://127.0.0.1`).

## Struktura

```
global.json                 # "test": { "runner": "Microsoft.Testing.Platform" } -- WYMAGANE
KeyRotation.slnx
IssuerApi/                  # wystawca: KeyRing (wiele kid), RefreshTokenStore, JWKS + discovery
ResourceApi/                # walidator: JwtBearer + MetadataAddress (ConfigurationManager po HTTP)
RotationTests/              # TUnit, 34 wyniki
├── Env.cs                  # startuje oba serwery na losowych portach, helpery HTTP, PollUntilAsync
├── KeyRotationTests.cs     # 7 testow: cache, rotacja, zalew kid, wycofanie klucza, flaga
├── RefreshRaceTests.cs     # wyscig HTTP (6 przebiegow) + wyscig na magazynie (21 przebiegow)
└── ScratchTests.cs         # pusty plik (pozostalosc po sondzie; rm odrzucone) -- do skasowania
```

Pakiety: `TUnit 1.72.16` (RotationTests), `Microsoft.AspNetCore.Authentication.JwtBearer 10.0.12`
(IssuerApi, ResourceApi).

## Jak odpalić od zera

```bash
cd code
dotnet test --solution KeyRotation.slnx --results-directory /tmp/tunit-rotation-results
```

Uruchamiaj z folderu `code/` (tam jest `global.json`). Zmierzone na .NET 10 SDK: `dotnet test
<plik>.csproj` bez `--project` kończy się `Testing with VSTest target is no longer supported by
Microsoft.Testing.Platform on .NET 10 SDK`, a `dotnet test --project ...` z katalogu bez `global.json`
(ani wyżej w drzewie) — `MSB1001: Unknown switch`. W tej sesji użyłem tymczasowego `global.json`
w katalogu nadrzędnym repo; sama sekwencja `cd code` + komenda nie była uruchamiana.

Jeden projekt, pełny log z liniami `[pomiar]`:

```bash
dotnet test --project RotationTests --results-directory /tmp/tunit-rotation-results --output Detailed
```

Tylko testy rotacji / tylko wyścig:

```bash
dotnet test --project RotationTests --results-directory /tmp/tunit-rotation-results --treenode-filter "/*/*/KeyRotationTests/*/*"
dotnet test --project RotationTests --results-directory /tmp/tunit-rotation-results --treenode-filter "/*/*/RefreshRaceTests/*/*"
```

## Prawdziwy output (34/34)

```
Test run summary: Passed!
  total: 34
  failed: 0
  succeeded: 34
  skipped: 0
  duration: 11s 771ms
```

(`KeyRotationTests` osobno: 7/7; testy trwają ok. 10-11 s, bo czekają na interwały odświeżania.)

Linie `[pomiar]` z `--output Detailed` (czasy `ms` zmieniają się między przebiegami):

```
[pomiar] stary=OK nowy-pierwszy=Unauthorized proby-do-200=2 ms=107 pobrania-JWKS: przed=1 po=2
[pomiar] 20 falszywych kid -> pobrania JWKS lacznie=2
[pomiar] druga rotacja: proby-do-200=22 ms=1113 pobrania-JWKS: przed=2 po=3 (interwal 3000 ms)
[pomiar] shortLkg=False: zaraz po Retire=OK; po 'wymuszaczu': ostatni=OK proby=73 ms=4007 pobrania-JWKS: przed=1 po=5
[pomiar] shortLkg=True: zaraz po Retire=OK; po 'wymuszaczu': ostatni=Unauthorized proby=21 ms=1290 pobrania-JWKS: przed=1 po=3
[pomiar] bez RefreshOnIssuerKeyNotFound: ostatni=OK proby=2 pobrania JWKS=2
[pomiar] 200=1 401=31
```

## Eksperyment: mutacja `lock` w `IssuerApi/RefreshTokenStore.cs`

Zamień `lock (_gate)` w `Rotate` na sam blok `{ ... }` i uruchom wyścig:

| Test | Wynik po usunięciu `lock` |
|---|---|
| `ConcurrentRefresh_ExactlyOneWins` (HTTP, 6 przebiegów) | 6/6 zielone — mutacja przeżyła |
| `ConcurrentRotate_OnStore_ExactlyOneWins` (64 wątki, 21 przebiegów) | 1 czerwony: `Expected to be 1 but found 2` |

Wynik probabilistyczny — w innym przebiegu może paść więcej lub mniej razy. Po mutacji kod
został przywrócony (wersja w repo ma `lock`).

## Nie zweryfikowano

Domyślna wartość `LastKnownGoodLifetime`; mechanizm, dla którego `RefreshOnIssuerKeyNotFound = false`
nie wyłącza odświeżania i dla którego stary klucz działa po odświeżeniu JWKS (zmierzone skutki,
kodu biblioteki nie czytałem); rotacja z wyprzedzeniem (publikacja klucza przed podpisywaniem);
`AutomaticRefreshInterval` w skali godzin (minimum 5 min jest `static readonly`, nie da się go skrócić
w teście); RS256 z certyfikatem X.509; SDK inne niż `10.0.400`.

Artefakty: po testach zostały `bin/` i `obj/` (wykluczone przez `.gitignore` w tym katalogu).
