# Kod do wydania #1 — Certyfikaty i TLS (X.509): od klucza do łańcucha zaufania

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go
odpalić od zera.

Wymagania: `openssl` (sprawdzone na `OpenSSL 3.0.2`) oraz **.NET 10 SDK**
(`dotnet --version` → `10.x`; jeśli `dotnet` nie jest na `PATH`:
`export PATH="$HOME/.dotnet:$PATH"`).

> **Bezpieczeństwo — przeczytaj zanim skopiujesz cokolwiek dalej:** wszystkie
> klucze prywatne i certyfikaty generowane przez `openssl/generate-pki.sh` są
> **wyłącznie demonstracyjne/edukacyjne**. Powstają lokalnie, na chwilę, tylko
> po to żeby pokazać mechanizm. Nigdy nie używajcie ich do niczego
> produkcyjnego ani nie traktujcie jako czegokolwiek poufnego. Katalog
> `openssl/pki/` jest w `.gitignore` tego folderu właśnie z tego powodu — jeśli
> mimo to trafi do repo, potraktujcie go jak każdy inny przypadkowo
> zacommitowany sekret (rotacja/usunięcie), nie jak realny incydent.

## Fragment prasówki, którego dotyczy ten kod

> Certyfikat to w istocie: "ja, wystawca, poświadczam podpisem, że ten oto
> klucz publiczny należy do tego oto podmiotu". Self-signed certyfikat
> (`Issuer == Subject`) jest kryptograficznie w pełni poprawny, ale nikt z
> zewnątrz nie poświadczył tożsamości jego właściciela - dlatego klient musi
> **jawnie** zdecydować, że mu ufa (zainstalować go w swoim magazynie
> zaufania), inaczej dostanie `self signed certificate` /
> `unable to get local issuer certificate`.

## 1. `openssl` — własne CA i certyfikat podpisany tym CA

```bash
cd openssl
./generate-pki.sh
```

Skrypt (od zera, bez żadnych wcześniejszych plików):

1. generuje klucz prywatny i self-signed certyfikat root CA (`ca.key`, `ca.pem`),
2. generuje klucz + CSR + certyfikat `leaf.pem`, podpisany tym CA
   (`CN=api.prasowka.local`),
3. generuje niepowiązany, self-signed certyfikat `rogue.pem` (do demonstracji
   błędu zaufania),
4. wypisuje pełną treść `leaf.pem` (`openssl x509 -text -noout`),
5. weryfikuje oba certyfikaty przez `openssl verify -CAfile ca.pem`.

Pliki lądują w `openssl/pki/` (gitignored — patrz notka bezpieczeństwa wyżej).

Oczekiwany output końcowej weryfikacji:

```
-- leaf.pem względem naszego CA (oczekiwane: OK) --
leaf.pem: OK
-- rogue.pem względem naszego CA (oczekiwane: BŁĄD, bo to inny, niepowiązany certyfikat) --
C = PL, O = Rogue Self-Signed, CN = rogue.local
error 18 at 0 depth lookup: self-signed certificate
error rogue.pem: verification failed
```

Szybka inspekcja samego leaf certyfikatu:

```bash
openssl x509 -in pki/leaf.pem -noout -subject -issuer -dates -ext subjectAltName
```

```
subject=C = PL, O = Prasowka Demo, CN = api.prasowka.local
issuer=C = PL, O = Prasowka Demo CA, CN = Prasowka Root CA
notBefore=Sep 24 22:08:44 2026 GMT
notAfter=Dec 27 22:08:44 2028 GMT
X509v3 Subject Alternative Name:
    DNS:api.prasowka.local
```

## 2. .NET — `X509Certificate2` + `X509Chain`

Wymaga plików z kroku 1 (`openssl/pki/ca.pem`, `leaf.pem`, `rogue.pem`) —
uruchom `openssl/generate-pki.sh` najpierw.

```bash
export PATH="$HOME/.dotnet:$PATH"
cd dotnet/CertChainDemo
dotnet run
```

(Program domyślnie szuka `../../openssl/pki` względem swojego katalogu; można
podać inną ścieżkę: `dotnet run -- /pełna/ścieżka/do/pki`.)

Oczekiwany output (sprawdzone lokalnie na `.NET SDK 10.0.400`):

```
== Certyfikat leaf (wystawiony przez nasze CA) ==
  Subject: CN=api.prasowka.local, O=Prasowka Demo, C=PL
  Issuer:  CN=Prasowka Root CA, O=Prasowka Demo CA, C=PL
  Ważny:   2026-09-24 .. 2028-12-27
  Thumbprint (SHA1): 7DBDC0F0CE3F929ECA871051AB42A9702A71E0E8

== Certyfikat CA ==
  Subject: CN=Prasowka Root CA, O=Prasowka Demo CA, C=PL
  Issuer:  CN=Prasowka Root CA, O=Prasowka Demo CA, C=PL
  Ważny:   2026-09-24 .. 2036-09-21
  Thumbprint (SHA1): 8C18A7FEEF091474D713EBED48C637F1E6CE7A64

== Scenariusz 1: leaf.pem, nasze CA dodane jako zaufany custom root ==
Chain valid: True
  (brak problemów - łańcuch zbudowany do zaufanego korzenia)

== Scenariusz 2: leaf.pem, DOMYŚLNY magazyn zaufania systemu (nasze CA NIE jest zainstalowane) ==
Chain valid: False
  -> PartialChain: unable to get local issuer certificate

== Scenariusz 3: rogue.pem (self-signed, obcy), nasze CA jako custom root ==
Chain valid: False
  -> UntrustedRoot: self-signed certificate
```

Thumbprinty i daty ważności będą inne przy każdym uruchomieniu
`generate-pki.sh` (nowy losowy klucz za każdym razem) — sama treść i status
scenariuszy 1-3 pozostaje identyczna.

`dotnet build` w `dotnet/CertChainDemo/` kończy się `0 Warning(s)`, `0 Error(s)`.
