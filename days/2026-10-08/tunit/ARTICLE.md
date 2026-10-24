<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #15 — 8 października 2026

![TUnit](https://img.shields.io/badge/TUnit-2EA44F?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-ekspert-8250DF?style=for-the-badge)
![X.509](https://img.shields.io/badge/X.509-klucze_z_certyfikatów-D63384?style=for-the-badge)

## TUnit: rotacja kluczy z wyprzedzeniem i klucze z certyfikatów X.509 — czy walidator sprawdza, że certyfikat wygasł?

</div>

---

> _"Certyfikat, który wygasł wczoraj, podpisuje dziś tokeny — i nikt w potoku walidacji nie zaprotestował."_

W wydaniu #14 zmierzyliśmy, że przy rotacji kluczy **pierwszy** użytkownik z nowym `kid` dostaje `401`,
i napisaliśmy tylko hipotezę: „publikuj klucz z wyprzedzeniem”. Dziś ją sprawdzamy testem. Przy okazji
przesiadamy się z gołych kluczy RSA na **certyfikaty X.509 w JWKS** (`x5c`, `x5t#S256`) i pytamy o rzecz,
którą większość zespołów zakłada bez dowodu: czy walidator sam pilnuje dat ważności certyfikatu?

Sprawdzone: `.NET SDK 10.0.400`, **`TUnit 1.72.16`** (ta sama co w #14 — nie sprawdzałem, czy jest nowsza:
zapytanie do NuGet zostało odrzucone przez środowisko), `Microsoft.AspNetCore.Authentication.JwtBearer 10.0.12`.
`dotnet test`: **10/10**, jeden pełny przebieg (patrz „Co zweryfikowano”), ok. 11 s.

| 🧩 Pytanie | 🏷️ Jak zmierzone | 💡 Wynik |
|---|---|---|
| Czy publikacja klucza **przed** aktywacją usuwa pierwszy `401`? | `Add` → wymuszone odświeżenie JWKS u walidatora → `Activate` | tak: pierwszy token z nowym kluczem → **`200`**, pobrań JWKS: 2 przed aktywacją i **2 po** (aktywacja nic nie kosztuje) |
| A gdy aktywujemy przed odświeżeniem walidatora? | ten sam test, bez kroku odświeżenia | **`401`**, pobrania JWKS 1 → 2 (jak w #14) |
| Czy walidator odrzuca token podpisany **wygasłym** certyfikatem? | cert `NotAfter` = wczoraj, token świeży | domyślnie **nie: `200`**; z własnym `IssuerSigningKeyValidator`: `401` |
| A certyfikatem, który zacznie obowiązywać jutro? | cert `NotBefore` = jutro | domyślnie **`200`**; z własną walidacją: `401` |
| Jakiego typu klucz dostaje walidator z JWKS z `x5c`? | sonda w `IssuerSigningKeyValidator` | **`X509SecurityKey`** |
| Dwie instancje wystawcy z kolejnymi `kid` (`key-1`)? | token instancji B u walidatora zaufanego A | `kid` **identyczne**, wynik `401` (jak przy `kid` = odcisk certyfikatu) |

---

## 1. 🪪 Klucz z certyfikatu: co faktycznie ląduje w JWKS i w tokenie

Wystawca generuje certyfikat samopodpisany w pamięci (`CertificateRequest.CreateSelfSigned(notBefore,
notAfter)`), podpisuje `X509SecurityKey` i publikuje w JWKS. Zmierzone pola jednego klucza:

```
[pomiar] pola JWKS: kty,use,alg,kid,n,e,x5c,x5t#S256
[pomiar] kid==x5t#S256: True; cert.Subject=CN=demo-issuer-1; HasPrivateKey(z DER)=False
[pomiar] naglowek tokenu: {"alg":"RS256","kid":"R4Th7b34qffFHz0VXJMWrgrIlZmWlOCcOL7SPYpGvy0","x5t":"7knf-llL-6EIP0e55EVfuEChbpA","typ":"JWT"}
```

- `x5c` to certyfikat w **zwykłym base64 DER** (nie base64url!), `x5t#S256` to odcisk SHA-256 w base64url.
  Test dekoduje `x5c`, liczy SHA-256 i porównuje z deklarowanym `x5t#S256`; dodatkowo sprawdza, że w JWKS
  nie ma żadnego pola prywatnego (`d`, `p`, `q`, `dp`, `dq`, `qi`) i że certyfikat z `x5c` nie ma klucza prywatnego.
- Ustawiłem `kid` = ten sam odcisk SHA-256. Zaleta: `kid` jest globalnie unikalny, a nie „`key-1`” w każdym
  środowisku (p. sekcja 4).
- Nagłówek tokenu **sam** dostał dodatkowe pole `x5t` (nie ustawiałem go) — `X509SecurityKey` dopisuje je
  przy podpisywaniu. Ma 27 znaków, co odpowiada 20 bajtom, czyli skrótowi SHA-1 (to wniosek z długości; algorytmu
  nie sprawdzałem w kodzie biblioteki).

> 🎯 **Dlaczego to ważne:** przy certyfikatach „klucz” ma tożsamość (odcisk, daty ważności, subject), więc
> da się go zinwentaryzować i audytować. Test, który dekoduje `x5c` i porównuje odcisk, wyłapie rozjazd
> między tym, co wystawca deklaruje, a tym, co faktycznie publikuje.

## 2. 🕰️ Rotacja z wyprzedzeniem: publikacja ≠ aktywacja

Klasa `KeyRing` ma teraz trzy niezależne czynności zamiast jednej: `Add` (publikuje w JWKS), `Activate`
(od teraz tym podpisujemy), `Retire` (usuwa z JWKS). Test parametryzowany `[Arguments]` sprawdza dwie
kolejności:

```
[pomiar] odswiezenie-przed-aktywacja=True (udane=True) pierwszy-status=200 pobrania-JWKS: przed-aktywacja=2 po-pierwszym-zadaniu=2
[pomiar] odswiezenie-przed-aktywacja=False (udane=True) pierwszy-status=401 pobrania-JWKS: przed-aktywacja=1 po-pierwszym-zadaniu=2
```

Czyli hipoteza z #14 się potwierdziła: gdy walidator **zdążył** odświeżyć JWKS między publikacją a aktywacją,
pierwszy token z nowym kluczem przechodzi, a licznik pobrań u wystawcy się nie zmienia. W złej kolejności
dostajemy dokładnie ten `401`, który znamy.

Uczciwie o ograniczeniu: „walidator zdążył odświeżyć” wymusiłem sztucznie — tokenem z nieznanym `kid`
(`ForceJwksRefreshAsync`). W produkcji o tym decyduje `AutomaticRefreshInterval` (wg #14 domyślnie 12 h — tej
wartości tu nie mierzyłem; minimum to 5 min), więc **okno między publikacją a aktywacją musi być dłuższe niż interwał
odświeżania wszystkich walidatorów**. Tego okna test nie potrafi zmierzyć (minimum 5 min nie da się skrócić).

> 🎯 **Dlaczego to ważne:** „rotacja bez przestoju” to dwa wdrożenia i pauza między nimi, a nie jedno
> wywołanie. Test z dwiema kolejnościami zamienia tę regułę w coś, co CI może pilnować.

## 3. ⏳ Wygasły certyfikat podpisuje tokeny — i nikt nie protestuje

Test: certyfikat z `NotAfter` = wczoraj (albo `NotBefore` = jutro) jest aktywny; token jest świeży i poprawny.
Cztery kombinacje (dwa typy złej daty × walidator domyślny/z egzekwowaniem):

```
[pomiar] cert=expired       egzekwowanie=False -> status=200 typy-kluczy-w-walidatorze=X509SecurityKey
[pomiar] cert=expired       egzekwowanie=True  -> status=401 typy-kluczy-w-walidatorze=X509SecurityKey
[pomiar] cert=not-yet-valid egzekwowanie=False -> status=200 typy-kluczy-w-walidatorze=X509SecurityKey
[pomiar] cert=not-yet-valid egzekwowanie=True  -> status=401 typy-kluczy-w-walidatorze=X509SecurityKey
```

W konfiguracji, którą testowałem (`ValidateIssuerSigningKey = true`, `JwtBearer` 10.0.12), **daty ważności
certyfikatu nie są sprawdzane** — certyfikat jest tylko nośnikiem klucza publicznego. Egzekwowanie dodajemy
sami w `TokenValidationParameters.IssuerSigningKeyValidator`: dla `X509SecurityKey` porównujemy
`Certificate.NotBefore/NotAfter` z bieżącym czasem. Ten sam punkt rozszerzenia posłużył za sondę: stąd wiemy,
że biblioteka zbudowała z `x5c` obiekt `X509SecurityKey`.

Czego to **nie** jest: nie budujemy łańcucha, nie sprawdzamy zaufanej kotwicy ani unieważnień (CRL/OCSP).
Certyfikaty są samopodpisane, a zaufanie wynika wyłącznie z tego, że JWKS pobieramy od zaufanego wystawcy
(w produkcji: po HTTPS — tu `RequireHttpsMetadata = false` tylko dla demo na `127.0.0.1`). Pełna walidacja
łańcucha `x5c` jest tematem rubryki o certyfikatach i **nie została tu zweryfikowana**.

> 🎯 **Dlaczego to ważne:** zespoły przenoszą się na certyfikaty, bo „mają datę ważności”, a potem okazuje
> się, że data nic nie robi, dopóki ktoś jej nie sprawdzi. Test z wygasłym certyfikatem to najtańszy
> sposób, by to zobaczyć przed incydentem, a nie w nim.

## 4. 👯 Dwie instancje wystawcy: ten sam `kid` dla różnych kluczy

Scenariusz: dwie instancje wystawcy A i B, każda z własnym pierścieniem. Z kolejnymi numerami oba
pierścienie nazywają pierwszy klucz `key-1`:

```
[pomiar] kid=Sequential: kidA==kidB: True;  token B u walidatora A -> 401; pobrania JWKS u A: 1 -> 2
[pomiar] kid=Thumbprint: kidA==kidB: False; token B u walidatora A -> 401; pobrania JWKS u A: 1 -> 2
```

Wynik ten sam (`401`, bo klucz B nigdy nie ma w JWKS A), więc **status HTTP nie rozróżnia tych przypadków**.
Różnica jest diagnostyczna: przy `key-1` vs `key-1` walidator „zna” `kid`, a odrzuca podpis — z zewnątrz wygląda
jak uszkodzony token, nie jak „nieznany klucz”. Przy `kid` = odcisk certyfikatu `kid` jest tożsamością
klucza i zbieżność znaczy to samo co zbieżność klucza.

Zaskoczenie, którego nie rozstrzygam: licznik pobrań JWKS u A wzrósł 1 → 2 **w obu trybach**, także wtedy, gdy
`kid` był znany (`key-1`). Wygląda na to, że odrzucony podpis przy znanym `kid` też wymusza odświeżenie
JWKS (mechanizmu nie sprawdzałem w kodzie). Próbowałem zmierzyć, czy 20 takich żądań zalewa wystawcę
— przebieg nie doszedł do skutku (środowisko przestało zezwalać na polecenia), więc **tego nie wiem**.

Nie testowałem prawdziwego scenariusza z balanserem przed dwiema instancjami i **wspólnym** JWKS —
w tym teście walidator ufa jednej instancji.

> 🎯 **Dlaczego to ważne:** w produkcji instancje wystawcy powinny albo dzielić pierścień kluczy, albo mieć
> `kid` globalnie unikalne. Test z dwiema instancjami to ten pierwszy, który ujawnia kolizję nazw.

## 5. 🧪 Nowe w TUnit

- **`[Arguments(...)]` z enumem** (`KidMode`, `HttpStatusCode`) i `[DisplayName]` z `$mode` / `$which` /
  `$refreshBeforeActivate` — nazwa wyniku zawiera wartości argumentów, więc czerwony test mówi, który wariant padł.
- **`await using` na własnych helperach** (`Issuer`, `Validator`) zamiast fixtures: każdy test dostaje świeże
  serwery Kestrel na własnych portach, więc testy nie dzielą stanu i mogą iść równolegle.
- **`using (Assert.Multiple())`** z pętlą `foreach` wewnątrz: seria asercji na polach JWKS zgłasza wszystkie
  porażki naraz.
- **Sonda w produkcie testowanym**: `ResourceOptions.SeenKeyTypes` (kolejka wypełniana w
  `IssuerSigningKeyValidator`) pozwala testowi asercjonować coś, czego nie widać z zewnątrz (typ klucza).
  Cena: kod produktu wie, że jest testowany — w prawdziwym projekcie osobna konfiguracja lub dekorator.

## ✅ Co zweryfikowano, a co nie

- ✔️ `dotnet test --solution CertKeys.slnx`: **10/10** (2 rotacja z wyprzedzeniem, 1 JWKS, 1 nagłówek,
  4 ważność certyfikatu, 2 dwie instancje), TUnit 1.72.16, .NET SDK 10.0.400, net10.0, ok. 11 s.
- ⚠️ **Tylko jeden pełny przebieg.** Pod koniec sesji środowisko przestało zezwalać na jakiekolwiek polecenia
  `Bash`, więc nie powtórzyłem przebiegu (w poprzednich wydaniach robiłem 2–3) i nie badałem flakowania.
  Testy używają pętli odpytujących z limitami 5 s, więc pod obciążeniem mogą być wolniejsze.
- ⚠️ Po tym przebiegu usunąłem z kodu jeden dodatkowy test (20 tokenów ze znanym `kid` i złym podpisem),
  którego nie zdążyłem uruchomić — w repo jest dokładnie ten kod, który przeszedł 10/10.
- ⚠️ Środowisko: `dotnet test --solution` z katalogu bez `global.json` w górę drzewa kończy się
  `MSB1001: Unknown switch` (jak w #13/#14). Użyłem tymczasowego `global.json` w `/tmp/prasowka-programowanie-CAHRWg/`
  (**poza** repo). Czytelnik: uruchamiaj z `code/`, gdzie `global.json` leży.
- ⚠️ **Niezweryfikowane:** domyślny `AutomaticRefreshInterval` w skali godzin; okno między publikacją
  a aktywacją dłuższe niż interwał odświeżania; walidacja łańcucha `x5c` i CRL/OCSP; certyfikaty z prawdziwego
  CA; JWKS przez HTTPS; wspólny JWKS z balanserem; czy lawina tokenów ze znanym `kid` i złym podpisem zalewa
  wystawcę; inne SDK niż 10.0.400.
- ⚠️ Czas realny, nie `FakeTimeProvider`: daty certyfikatów liczone względem zegara systemowego
  (`DateTimeOffset.UtcNow`), walidator porównuje z `DateTime.Now`.
- ⚠️ `bin/` i `obj/` zostały po budowie; wykluczone przez `code/.gitignore`.

**Pełny, uruchamialny przykład:** [`code/`](code/) — solution [`CertKeys.slnx`](code/CertKeys.slnx).

> ⚠️ **Nigdy do produkcji.** Certyfikaty są samopodpisane i efemeryczne, hasło użytkownika `alice` jest jawne
> w kodzie, magazyn kluczy żyje w pamięci, `RequireHttpsMetadata = false`.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — komendy + prawdziwy output `dotnet test`.

---

<div align="center">

[← wróć do wydania #15 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
