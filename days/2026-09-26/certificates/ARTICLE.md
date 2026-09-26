<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #3 — 26 września 2026

![mTLS / X.509](https://img.shields.io/badge/mTLS_%2F_X.509-2E8B57?style=for-the-badge&logo=letsencrypt&logoColor=white)

## mTLS w Kestrelu: gdy serwer też chce zobaczyć dowód tożsamości klienta — i sześć sposobów, na jakie to się psuje

</div>

---

> _"The response ended prematurely."_ - tyle powie wam `HttpClient`, kiedy
> serwer odrzuci wasz certyfikat klienta. Cała prawda o tym, dlaczego, leży po
> stronie serwera - i domyślnie nie jest tam zalogowana.

W wydaniu #1 zbudowaliśmy łańcuch zaufania i sprawdziliśmy go w `X509Chain`.
Dziś ten sam mechanizm dostaje drugi kierunek: **mTLS** - serwer wymaga od
klienta certyfikatu i weryfikuje go tak samo skrupulatnie, jak klient weryfikuje
serwer. Stawiamy własne CA z **pośrednim (intermediate)**, serwer w Kestrelu z
`ClientCertificateMode.RequireCertificate`, klienta w `HttpClient`, a potem
psujemy wszystko po kolei: brak certyfikatu klienta, zły EKU, wygasły, obcy
wystawca, brak intermediate w łańcuchu serwera, IP zamiast nazwy, odwołany
(CRL). Każdy błąd pokazujemy **prawdziwym outputem** z `dotnet` i `openssl`.

Środowisko: .NET SDK 10.0.400, OpenSSL 3.0.2, Linux. Kod:
[`code/`](code/README.md). Klucze EC P-256 generowane w `/tmp`, nigdy w repo.

---

## 1️⃣ Topologia: root → intermediate → (serwer, klient)

```
Prasowka mTLS Root CA (self-signed, ufany przez obie strony)
        └── Prasowka mTLS Issuing CA (CA:TRUE, pathlen:0)
                 ├── CN=localhost         SAN: DNS:localhost, IP:127.0.0.1   EKU: serverAuth
                 └── CN=alice-service                                        EKU: clientAuth
```

Trzy rzeczy, które w praktyce robią różnicę i o których łatwo zapomnieć:

- **SAN, nie CN.** Nazwa hosta jest sprawdzana względem `subjectAltName`. IP
  też musi być w SAN jako `IP:`, nie jako `DNS:`.
- **EKU (Extended Key Usage).** Certyfikat serwera ma `serverAuth`, klienta
  `clientAuth`. To osobne "pozwolenia" i walidatory je egzekwują.
- **`pathlen:0` na intermediate** - ten CA może wystawiać tylko certyfikaty
  końcowe, nie kolejne CA. Ogranicza szkody przy jego wycieku.

Podpisujemy przez `openssl ca` (nie `x509 -req`), bo tylko on prowadzi bazę
wystawionych certyfikatów (`index.txt`) - a bez niej nie ma odwoływania i CRL.
Rozszerzenia w [`code/openssl/ca.cnf`](code/openssl/ca.cnf), np.:

```ini
[ext_client]
basicConstraints       = critical,CA:FALSE
keyUsage               = critical,digitalSignature
extendedKeyUsage       = clientAuth
```

Inspekcja wystawionych certyfikatów (prawdziwy output):

```
$ openssl x509 -in server.pem -noout -subject -issuer -dates -ext subjectAltName,extendedKeyUsage
subject=O = Prasowka Demo, CN = localhost
issuer=O = Prasowka Demo, CN = Prasowka mTLS Issuing CA
notBefore=Sep 26 01:11:32 2026 GMT
notAfter=Sep 26 01:11:32 2027 GMT
X509v3 Extended Key Usage:
    TLS Web Server Authentication
X509v3 Subject Alternative Name:
    DNS:localhost, IP Address:127.0.0.1

$ openssl x509 -in client.pem -noout -subject -issuer -dates -ext extendedKeyUsage,keyUsage
subject=O = Prasowka Demo, CN = alice-service
issuer=O = Prasowka Demo, CN = Prasowka mTLS Issuing CA
notBefore=Sep 26 01:11:34 2026 GMT
notAfter=Sep 26 01:11:34 2027 GMT
X509v3 Key Usage: critical
    Digital Signature
X509v3 Extended Key Usage:
    TLS Web Client Authentication
```

**Dlaczego to ważne:** mTLS to najtańszy sposób uwierzytelnienia usługa-usługa
bez haseł i tokenów, ale tylko wtedy, gdy walidacja jest *szczelna*: własny
root zamiast systemowego magazynu, sprawdzony EKU, świadomość co z odwołaniami.
Reszta artykułu to lista miejsc, gdzie ta szczelność ucieka.

---

## 2️⃣ Serwer: Kestrel z `RequireCertificate`

Pełny kod: [`MtlsServer.cs`](code/dotnet/MtlsDemo/MtlsServer.cs). Sedno:

```csharp
https.ServerCertificate = serverCert;                                   // leaf + klucz
https.ServerCertificateChain = new X509Certificate2Collection(intermediate); // .NET 8+
https.ClientCertificateMode = ClientCertificateMode.RequireCertificate;

// Walidacja klienta wg NASZEJ polityki: ufamy tylko naszemu rootowi.
https.OnAuthenticate = (_, ssl) => ssl.CertificateChainPolicy = clientPolicy;
https.ClientCertificateValidation = (cert, chain, errors) =>
{
    log($"[serwer] {cert.Subject} | {errors} | chain: {Pki.Describe(chain)}");
    return errors == SslPolicyErrors.None;
};
```

gdzie polityka to:

```csharp
var policy = new X509ChainPolicy
{
    TrustMode = X509ChainTrustMode.CustomRootTrust,
    RevocationMode = X509RevocationMode.NoCheck,
};
policy.CustomTrustStore.Add(root);
policy.ApplicationPolicy.Add(new Oid("1.3.6.1.5.5.7.3.2")); // clientAuth
```

Dlaczego `CertificateChainPolicy`, a nie sam callback? Bo klient certyfikatu
**nie jest** w magazynie systemowym; bez własnej polityki każdy klient dostałby
`PartialChain`/`UntrustedRoot`. Dlaczego callback w ogóle? Bo **Kestrel domyślnie
loguje tylko ogólnik**. Realny wpis z logu Kestrela (poziom Debug), gdy klient
przyszedł z niepełnym łańcuchem:

```
dbug: Microsoft.AspNetCore.Server.Kestrel.Https.Internal.HttpsConnectionMiddleware[1] Failed to authenticate HTTPS connection. System.Security.Authentication.AuthenticationException: The remote certificate was rejected by the provided RemoteCertificateValidationCallback.
```

...i to samo dostajemy dla *każdej* przyczyny. Powód (`NotTimeValid`,
`PartialChain`, `NotValidForUsage`) widać dopiero, gdy sami zalogujemy
`chain.ChainStatus` w `ClientCertificateValidation`. W produkcji dodajcie taki
log - inaczej diagnoza to zgadywanie.

## 3️⃣ Klient: `HttpClient` z certyfikatem i z własnym zaufaniem

```csharp
var handler = new SocketsHttpHandler();
handler.SslOptions.CertificateChainPolicy = pki.TrustPolicy(Pki.ServerAuthOid);
handler.SslOptions.ClientCertificateContext =
    SslStreamCertificateContext.Create(clientCert, new X509Certificate2Collection(intermediate), offline: true);
```

Kluczowy szczegół: **`ClientCertificateContext` z intermediate.** Zwykłe
`ClientCertificates.Add(cert)` wysyła tylko leaf, a serwer nie ma skąd wziąć
pośredniego CA. Realny dowód: ten sam `client.pem` przez `openssl s_client` -
najpierw bez `-cert_chain` (tylko leaf), potem z nim. Log serwera przy
pierwszej próbie:

```
[serwer] certyfikat klienta: CN=alice-service, O=Prasowka Demo | SslPolicyErrors=RemoteCertificateChainErrors | chain: PartialChain (unable to get local issuer certificate)
```

a po dodaniu `-cert_chain intermediate.pem` serwer odpowiada:

```
HTTP/1.1 200 OK
Server: Kestrel
Czesc, CN=alice-service, O=Prasowka Demo (wystawca: CN=Prasowka mTLS Issuing CA, O=Prasowka Demo)
```

(Ostatnia linia `unexpected eof while reading` po odpowiedzi to skutek
`Connection: close` bez `close_notify` w `s_client`, nie błąd mTLS.)

---

## 4️⃣ Mikroskop: sześć porażek (realny output z `dotnet run -- demo`)

Serwer poprawny (SAN + intermediate), `RequireCertificate`. HttpClient sam
ponawia zapytanie po zerwaniu połączenia, więc w logu zostawiamy pierwszą linię
z każdej strony (tak działa `Program.cs`).

```
=== A. Serwer poprawny (SAN + intermediate w handshake), RequireCertificate ===
  -- klient: alice (clientAuth, wystawca: nasze CA)
[klient] certyfikat serwera: CN=localhost, O=Prasowka Demo | SslPolicyErrors=None | chain: brak
[serwer] certyfikat klienta: CN=alice-service, O=Prasowka Demo | SslPolicyErrors=None | chain: brak
    HTTP 200: Czesc, CN=alice-service, O=Prasowka Demo (wystawca: CN=Prasowka mTLS Issuing CA, O=Prasowka Demo)
  -- klient: BEZ certyfikatu klienta
[klient] certyfikat serwera: CN=localhost, O=Prasowka Demo | SslPolicyErrors=None | chain: brak
    BLAD -> HttpRequestException: An error occurred while sending the request.
      -> HttpIOException: The response ended prematurely. (ResponseEnded)
  -- klient: mallory (EKU = serverAuth, nie clientAuth)
[klient] certyfikat serwera: CN=localhost, O=Prasowka Demo | SslPolicyErrors=None | chain: brak
[serwer] certyfikat klienta: CN=mallory-wrong-eku, O=Prasowka Demo | SslPolicyErrors=RemoteCertificateChainErrors | chain: NotValidForUsage (The certificate has invalid policy.)
    BLAD -> HttpRequestException: An error occurred while sending the request.
      -> HttpIOException: The response ended prematurely. (ResponseEnded)
  -- klient: bob (wygasly w 2025)
[klient] certyfikat serwera: CN=localhost, O=Prasowka Demo | SslPolicyErrors=None | chain: brak
[serwer] certyfikat klienta: CN=bob-expired, O=Prasowka Demo | SslPolicyErrors=RemoteCertificateChainErrors | chain: NotTimeValid (certificate has expired)
    BLAD -> HttpRequestException: An error occurred while sending the request.
      -> HttpIOException: The response ended prematurely. (ResponseEnded)
  -- klient: eve (podpisana przez OBCE CA)
[klient] certyfikat serwera: CN=localhost, O=Prasowka Demo | SslPolicyErrors=None | chain: brak
[serwer] certyfikat klienta: CN=eve-rogue-ca, O=Obca Firma | SslPolicyErrors=RemoteCertificateChainErrors | chain: PartialChain (unable to get local issuer certificate)
    BLAD -> HttpRequestException: An error occurred while sending the request.
      -> HttpIOException: The response ended prematurely. (ResponseEnded)
  -- klient: carol (ODWOLANA w CRL - .NET bez RevocationMode nie sprawdza)
[klient] certyfikat serwera: CN=localhost, O=Prasowka Demo | SslPolicyErrors=None | chain: brak
[serwer] certyfikat klienta: CN=carol-revoked, O=Prasowka Demo | SslPolicyErrors=None | chain: brak
    HTTP 200: Czesc, CN=carol-revoked, O=Prasowka Demo (wystawca: CN=Prasowka mTLS Issuing CA, O=Prasowka Demo)
```

### Anatomia błędów

**1. Brak certyfikatu klienta.** Po stronie klienta: `The response ended
prematurely`. W TLS 1.3 handshake *z punktu widzenia klienta* kończy się
sukcesem, zanim serwer ocenił jego certyfikat, więc odmowa wygląda jak zerwane
połączenie po fakcie. Tak samo w `openssl s_client` (`-brief` mówi
`CONNECTION ESTABLISHED`, `Verification: OK`, a dopiero odczyt kończy się):

```
error:0A000126:SSL routines:ssl3_read_n:unexpected eof while reading
```

Callback walidacji po stronie serwera **w ogóle nie jest wywoływany** (nie ma
czego walidować) - w powyższym logu dla tego klienta nie ma linii `[serwer]`.
**Wniosek: diagnozę mTLS zaczynajcie od logów serwera, nie klienta.**

**2. Zły EKU.** Certyfikat klienta z `serverAuth` zamiast `clientAuth`:
`NotValidForUsage`. `openssl verify -purpose sslclient` daje ten sam werdykt
własnymi słowami:

```
error 26 at 0 depth lookup: unsupported certificate purpose
```

Ciekawostka z scenariusza B: nawet gdy w mojej polityce **nie** dodałem
`ApplicationPolicy` (flaga `CheckClientEku=false`), `SslStream` i tak zgłosił
`NotValidForUsage` - EKU dla klienta jest egzekwowane domyślnie. W tym
przebiegu pojawił się dodatkowo `PartialChain`, którego nie umiem wyjaśnić
(nie mam potwierdzonej przyczyny; nie zgaduję).

**3. Wygasły.** `NotTimeValid (certificate has expired)`; w `openssl`:

```
error 10 at 0 depth lookup: certificate has expired
```

Wygasły certyfikat klienta to klasyk poranka po długim weekendzie: usługa
działała miesiącami bez zmian i nagle "sama" przestaje. Monitorujcie
`notAfter`.

**4. Obcy wystawca.** `PartialChain (unable to get local issuer certificate)`
- w `openssl`: `error 20 at 0 depth lookup: unable to get local issuer
certificate`. Uwaga na mylący komunikat: nie znaczy "brakuje pliku", tylko
"nie potrafię zbudować drogi do ufanego rootu".

**5. Odwołany certyfikat, który przechodzi.** Ostatni klient (`carol`) jest
**odwołany** w CRL z powodem `keyCompromise` - a serwer wpuścił go z `HTTP 200`.
Bo `RevocationMode = NoCheck`. Wniosek: **domyślnie mTLS w .NET nie zna pojęcia
odwołania**, dopóki go świadomie nie włączycie i nie dostarczycie CRL/OCSP.
Poniżej pokazujemy, jak wygląda sprawdzenie w `openssl`.

---

## 5️⃣ Błędy po stronie serwera, które widzi klient

```
=== C. Certyfikat serwera BEZ SAN (tylko CN=localhost) ===
  -- klient: alice, laczymy sie po nazwie localhost
[klient] certyfikat serwera: CN=localhost, O=Prasowka Demo | SslPolicyErrors=None | chain: brak
    HTTP 200: Czesc, CN=alice-service, ...
  -- klient: alice, laczymy sie po 127.0.0.1
[klient] certyfikat serwera: CN=localhost, O=Prasowka Demo | SslPolicyErrors=RemoteCertificateNameMismatch | chain: brak
    BLAD -> HttpRequestException: The SSL connection could not be established, see inner exception.
      -> AuthenticationException: The remote certificate was rejected by the provided RemoteCertificateValidationCallback.

=== C2. Kontrola: certyfikat serwera Z SAN (DNS:localhost, IP:127.0.0.1) ===
  -- klient: alice, po 127.0.0.1
    HTTP 200: Czesc, CN=alice-service, ...
```

**Brak SAN - zaskoczenie, którego się nie spodziewałem.** Zakładałem, że
certyfikat bez SAN zostanie odrzucony przez każdego. W tym środowisku (.NET na
Linuksie/OpenSSL 3.0.2) **DNS `localhost` przeszedł na podstawie samego `CN`**
(fallback), także w `openssl verify -verify_hostname` i w
`s_client -verify_hostname` (`Verification: OK`, `Verified peername: localhost`)
oraz w Pythonie (`ssl.create_default_context`, TLSv1.3 bez błędu).
Nie przeszedł natomiast **adres IP**: `RemoteCertificateNameMismatch` w .NET,
w `openssl`:

```
$ openssl s_client -connect 127.0.0.1:18445 -CAfile root.pem -verify_ip 127.0.0.1 -verify_return_error -brief
depth=0 O = Prasowka Demo, CN = localhost
verify error:num=64:IP address mismatch
```

Ostrożnie z wnioskiem: przeglądarki (Chrome od 58) i m.in. Go **ignorują CN**
i wymagają SAN - **tego tu nie sprawdzałem**, opieram się na powszechnej wiedzy.
Praktyka: zawsze dawajcie SAN; fakt, że "u mnie działa", bo klient robi
fallback do CN, to mina na później (zmiana klienta = awaria).

**Brak intermediate w łańcuchu serwera:**

```
=== D. Serwer NIE dosyla intermediate (tylko leaf) ===
  -- klient: alice
[klient] certyfikat serwera: CN=localhost, O=Prasowka Demo | SslPolicyErrors=RemoteCertificateChainErrors | chain: PartialChain (unable to get local issuer certificate)
    BLAD -> HttpRequestException: The SSL connection could not be established, see inner exception.
      -> AuthenticationException: The remote certificate was rejected by the provided RemoteCertificateValidationCallback.
```

`openssl s_client` na serwerze z samym leafem:

```
$ openssl s_client -connect 127.0.0.1:18444 -servername localhost -CAfile root.pem -verify_return_error -brief
depth=0 O = Prasowka Demo, CN = localhost
verify error:num=20:unable to get local issuer certificate
error:0A000086:SSL routines:tls_post_process_server_certificate:certificate verify failed
```

To najbardziej zdradliwy błąd w produkcji, bo **działa w przeglądarce, a nie
działa w kliencie serwisowym**: przeglądarki potrafią dociągnąć brakujący
intermediate z rozszerzenia AIA (i cache'ują), `HttpClient` z własnym zaufaniem
- nie. (Zachowanie przeglądarek z AIA - z wiedzy ogólnej, tu niesprawdzane.)
Naprawa: `ServerCertificateChain` w Kestrelu (albo pełny łańcuch w PFX/PEM
pod nginxem). Sanity-check: `openssl s_client -connect host:443 -showcerts`
- musi pokazać leaf **i** intermediate; **nigdy** root (root ma być u klienta).

Kontrolnie, gdy serwer jest dobrze skonfigurowany, `s_client` z pełnym
łańcuchem:

```
depth=2 O = Prasowka Demo, CN = Prasowka mTLS Root CA
verify return:1
depth=1 O = Prasowka Demo, CN = Prasowka mTLS Issuing CA
verify return:1
depth=0 O = Prasowka Demo, CN = localhost
verify return:1
```

---

## 6️⃣ Odwołania: CRL w `openssl` (i czego nie sprawdziłem w .NET)

Odwołujemy certyfikat `carol` i generujemy CRL:

```bash
openssl ca -batch -config ca.cnf -name ca_inter -revoke client-revoked.pem -crl_reason keyCompromise
openssl ca -batch -config ca.cnf -name ca_inter -gencrl -out inter.crl
```

```
Revoking Certificate 2005.
Data Base Updated
```

```
$ openssl crl -in inter.crl -noout -text
Certificate Revocation List (CRL):
        Version 2 (0x1)
        Signature Algorithm: ecdsa-with-SHA256
        Issuer: O = Prasowka Demo, CN = Prasowka mTLS Issuing CA
        Last Update: Sep 26 01:11:41 2026 GMT
        Next Update: Oct 26 01:11:41 2026 GMT
Revoked Certificates:
    Serial Number: 2005
        Revocation Date: Sep 26 01:11:39 2026 GMT
        CRL entry extensions:
            X509v3 CRL Reason Code:
                Key Compromise
```

Weryfikacja z `-crl_check` (trzy wyniki, wszystkie prawdziwe):

```
$ openssl verify -CAfile root.pem -untrusted intermediate.pem -purpose sslclient -crl_check -CRLfile inter.crl client-revoked.pem
O = Prasowka Demo, CN = carol-revoked
error 23 at 0 depth lookup: certificate revoked

$ openssl verify ... -crl_check -CRLfile inter.crl client.pem
client.pem: OK

$ openssl verify ... -crl_check client.pem        # brak pliku CRL
error 3 at 0 depth lookup: unable to get certificate CRL
```

Ostatni wynik jest lekcją: **`-crl_check` jest "fail closed"** - brak CRL to
błąd, nie ciche pominięcie. Tak samo `X509RevocationMode.Online/Offline` w .NET
ma swoje `RevocationStatusUnknown`/`OfflineRevocation`. Mamy więc realny
dylemat: fail-open (jak nasze `NoCheck`, odwołany wchodzi) albo fail-closed
(awaria CA/CRL kładzie produkcję).

**Czego NIE sprawdziłem:** włączenia sprawdzania odwołań w .NET
(`RevocationMode.Offline` z CRL w magazynie / dystrybucją przez CDP),
OCSP i OCSP stapling. Nie zgaduję tu nic - to materiał na osobne wydanie.
Do zapamiętania jedynie: CRL ma `Next Update` (u nas 30 dni), po którym
przestaje być wiarygodny.

---

## 7️⃣ Ściągawka diagnostyczna

| Objaw | Co robić | Realny komunikat |
|---|---|---|
| Klient: `response ended prematurely`, TLS 1.3 | logi **serwera**; brak cert klienta lub odmowa | `unexpected eof while reading` |
| Serwer: `PartialChain` | klient nie wysłał intermediate albo obcy CA | `unable to get local issuer certificate` |
| Serwer: `NotValidForUsage` | `openssl x509 -ext extendedKeyUsage` | `unsupported certificate purpose` |
| `NotTimeValid` | `openssl x509 -noout -dates` | `certificate has expired` |
| Klient: `PartialChain` na serwerze | `s_client -showcerts`: brak intermediate | `verify error:num=20` |
| Klient: `RemoteCertificateNameMismatch` | `x509 -ext subjectAltName`, `-verify_ip`/`-verify_hostname` | `IP address mismatch` |
| Odwołany wchodzi | włączyć revocation, dostarczyć CRL | `certificate revoked` (openssl) |

Zasada ogólna: **każdą awarię TLS rozpatrujecie jako pytanie "który z trzech
elementów zawiódł": łańcuch (kto podpisał), przeznaczenie (EKU/nazwa), czas
(`notBefore`/`notAfter`/odwołanie)**.

---

## 📎 Uwaga o odtwarzalności

Skrypt `code/openssl/generate-mtls-pki.sh` składa te same komendy `openssl` w
całość, ale w środowisku, w którym powstało to wydanie, uruchomienie skryptu
jako takiego zostało zablokowane. Dlatego wszystkie komendy z outputem powyżej
uruchamiałem **pojedynczo, ręcznie** (te same argumenty), a sam skrypt jako
całość jest **niesprawdzony w tym przebiegu** - przed użyciem przeczytajcie go
i odpalcie u siebie. Projekt .NET został zbudowany (`0 Warning(s), 0 Error(s)`)
i uruchomiony na PKI wygenerowanym tymi ręcznymi komendami.

## 📎 Co dalej w tej rubryce

Włączanie odwołań w .NET (CRL/OCSP/stapling), magazyn certyfikatów systemu
(`X509Store`), SNI, ACME/Let's Encrypt, pinning, rotacja certyfikatów bez
restartu i mTLS w Kubernetes.

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #3 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
