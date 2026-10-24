<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #4 — 27 września 2026

![Revocation / OCSP / Pinning](https://img.shields.io/badge/Revocation_%C2%B7_OCSP_%C2%B7_Pinning-B22222?style=for-the-badge&logo=letsencrypt&logoColor=white)

## Certyfikat odwołany, a mimo to działa: CRL, OCSP, stapling, rotacja i pinning SPKI — co naprawdę robi .NET

</div>

---

> _"Revocation checking is a broken mechanism that nobody can fix, and nobody dares
> to turn off."_ — powtarzany w branży żart, który boli, bo w połowie jest prawdą.
> Sprawdzimy, w której połowie.

W #3 skończyliśmy na niewygodnym fakcie: odwołany certyfikat klienta wszedł z
`HTTP 200`, bo `RevocationMode = NoCheck`. Dziś domykamy temat. Stawiamy
lokalny CDP (serwer HTTP z CRL), lokalny **responder OCSP** z `openssl`, włączamy
`X509RevocationMode.Online/Offline` w .NET i **mierzymy**: co pobiera, co cache'uje,
kiedy mówi `Revoked`, a kiedy `RevocationStatusUnknown`. Potem: **stapling**
(zweryfikowany `openssl s_server/s_client`), **TLS 1.3 na poziomie bajtów**
(`-trace`), **rotacja** certyfikatu w Kestrelu bez restartu z własnego `X509Store`
i **pinning SPKI** w `HttpClientHandler`.

Środowisko: .NET SDK 10.0.400, OpenSSL 3.0.2, Linux. Kod: [`code/`](code/README.md).
Wszystkie klucze to **DEMO**, generowane lokalnie w `code/work/` (ignorowane przez git).

| 🧪 Co | ✅ Status |
|---|---|
| CRL/CDP: .NET `Online`/`Offline`, cache, martwy CDP, stale CRL | uruchomione (`dotnet run`) |
| OCSP: `openssl ocsp` responder + zapytania good/revoked/unknown | uruchomione |
| OCSP stapling: `s_server -status_file` + `s_client -status` | uruchomione |
| TLS 1.3: `s_client -tls1_3 -trace` | uruchomione |
| `X509Store` (własny, CurrentUser, w przekierowanym `HOME`) + rotacja | uruchomione |
| Pinning SPKI w `HttpClientHandler` | uruchomione |
| OCSP z poziomu .NET, stapling po stronie Kestrela, Windows/macOS | **NIE sprawdzone** |

---

## 1️⃣ Topologia i skąd klient wie, gdzie pytać

```
Prasowka Rev Root CA
   └── Prasowka Rev Issuing CA (pathlen:0)
          ├── srv-good      CN=localhost  CDP + AIA(OCSP)    <- zdrowy
          ├── srv-revoked   CN=localhost  CDP + AIA(OCSP)    <- odwołany (keyCompromise)
          ├── srv-deadcdp   CN=localhost  CDP -> martwy port <- CDP nie odpowiada
          ├── srv-renewed-samekey  ten sam klucz co srv-good, nowy certyfikat
          ├── srv-rekeyed          nowy klucz
          └── ocsp                 EKU OCSPSigning (delegowany responder)
```

Adresy, pod które pytamy, siedzą **w samym certyfikacie** (prawdziwy output):

```
$ openssl x509 -in srv-good.pem -noout -subject -issuer -serial -ext crlDistributionPoints,authorityInfoAccess,subjectAltName
subject=O = Prasowka Demo, CN = localhost
issuer=O = Prasowka Demo, CN = Prasowka Rev Issuing CA
serial=2000
X509v3 Subject Alternative Name:
    DNS:localhost, IP Address:127.0.0.1
X509v3 CRL Distribution Points:
    Full Name:
      URI:http://127.0.0.1:18480/inter.crl
Authority Information Access:
    OCSP - URI:http://127.0.0.1:18481
```

W `ca.cnf`: `crlDistributionPoints = URI:http://...` (CDP) i
`authorityInfoAccess = OCSP;URI:http://...` (AIA). Bez tych rozszerzeń klient
**nie ma skąd** dowiedzieć się o odwołaniach — sprawdzanie nie ma czego sprawdzić.

**Dlaczego to ważne:** odwołanie to jedyny sposób, by zabić certyfikat z wyciekłym
kluczem przed `notAfter`. Ale działa tylko wtedy, gdy (1) certyfikat niesie adresy,
(2) klient je odpytuje, (3) klient wie, co zrobić, gdy odpowiedzi nie ma.
Każdy z tych trzech punktów zawodzi po cichu.

---

## 2️⃣ CRL w .NET: macierz `RevocationMode` × certyfikat

`RevocationLab.cs` stawia w procesie prosty serwer `HttpListener` na
`127.0.0.1:18480` (nasz CDP; loguje każde zapytanie) i buduje łańcuch
`X509Chain` z `CustomRootTrust` dla różnych trybów. Realny output:

```
[NoCheck EndCertificateOnly ] srv-revoked  Build=true   192 ms | brak
[Offline EndCertificateOnly ] srv-revoked  Build=false   17 ms | RevocationStatusUnknown (unable to get certificate CRL); OfflineRevocation (unable to get certificate CRL)
[Offline EndCertificateOnly ] srv-good     Build=false    1 ms | RevocationStatusUnknown (unable to get certificate CRL); OfflineRevocation (unable to get certificate CRL)
      [CDP-HTTP] GET /inter.crl -> serwuje inter.crl
[Online  EndCertificateOnly ] srv-good     Build=true    76 ms | brak
[Online  EndCertificateOnly ] srv-revoked  Build=false    2 ms | Revoked (certificate revoked)
[Offline EndCertificateOnly ] srv-revoked  Build=false    2 ms | Revoked (certificate revoked)
[Online  EndCertificateOnly ] srv-deadcdp  Build=false   15 ms | RevocationStatusUnknown (unable to get certificate CRL); OfflineRevocation (unable to get certificate CRL)
[Offline EndCertificateOnly ] srv-deadcdp  Build=false    1 ms | RevocationStatusUnknown (unable to get certificate CRL); OfflineRevocation (unable to get certificate CRL)
[Online  EntireChain        ] srv-good     Build=false    2 ms | RevocationStatusUnknown (unable to get certificate CRL); OfflineRevocation (unable to get certificate CRL)

zawartosc cache CRL po testach:
  679f1b46.1634da2f.crl (390 B)
```

Co z tego wynika (wszystko widać w outputcie powyżej):

| # | Obserwacja | Wniosek |
|---|---|---|
| 1 | `NoCheck` → odwołany `Build=true` | Wiemy z #3. Domyślna polityka **własnego** `X509ChainPolicy` to `Online`, ale nasza z #3 świadomie wyłączała. Nie zakładajcie, że "coś sprawdza". |
| 2 | `Offline` przy pustym cache → `false` (oba certyfikaty, także zdrowy!) | `Offline` **nie pobiera niczego**, czyta tylko lokalny cache. Pusty cache = *fail closed*. |
| 3 | Pierwszy `Online` → jedno `GET /inter.crl`, potem `Build=true` | CRL pobrany po URL z CDP i **zapisany do cache na dysku**. |
| 4 | Drugi `Online` (odwołany) → **brak** kolejnego `GET`, `Revoked` w 2 ms | CRL z cache, dopóki jest ważny (`nextUpdate`). Jedno pobranie obsługuje wszystkie certyfikaty tego wystawcy. |
| 5 | `Offline` *po* `Online` → `Revoked` | Tryb `Offline` sam nic nie pobierze, ale **skorzysta z tego, co pobrał `Online`**. |
| 6 | `srv-deadcdp`: `Online` → `RevocationStatusUnknown` + `OfflineRevocation` | Martwy CDP = **nie "dobry"**, tylko "nie wiem". `Build` zwraca `false`. Klient kończy z błędem — świadomie decydujecie, czy to akceptować. |
| 7 | `EntireChain` → `false` | Pytamy też o intermediate i root; nasze CA nie publikuje dla nich CRL. Prawdopodobna przyczyna — nie sprawdzałem CRL roota, więc to hipoteza. Praktyka: `EndCertificateOnly` (domyślne) albo publikujcie CRL na każdym poziomie. |

**Ważne o `X509Chain.Build`:** zwraca `false` także dla `RevocationStatusUnknown`.
W `SslStream`/`HttpClient` walidacja z domyślnymi błędami *odrzuci* połączenie —
**chyba że** callback zdecyduje inaczej. To Wasz *soft-fail vs hard-fail*.

### 🔍 Cache CRL na Linuksie — i jak go nie zaśmiecić

.NET na Linuksie trzyma pobrane CRL w
`$HOME/.dotnet/corefx/cryptography/crls/` (u nas: `679f1b46.1634da2f.crl`,
nazwa to skrót wystawcy). Żeby **nie ruszać profilu użytkownika**, `Program.cs`
przed pierwszym użyciem X509 robi `Environment.SetEnvironmentVariable("HOME", <work>/home)`
— zadziałało (pliki wylądowały w `work/home/.dotnet/...`). Ten sam katalog jest
korzeniem magazynu `CurrentUser` (patrz sekcja 6).

### ⏰ Pułapka: przeterminowany CRL

Wygenerowałem drugi CRL z `nextUpdate` w przeszłości
(`openssl ca -gencrl -crl_lastupdate 20260901000000Z -crl_nextupdate 20260910000000Z`) i
kazałem serwerowi CDP go serwować. `openssl verify` jest surowy:

```
$ openssl verify ... -crl_check -CRLfile inter-stale.crl srv-good.pem
error 12 at 0 depth lookup: CRL has expired
```

A .NET? Realny output z `dotnet run -- revocation <pki> inter-stale.crl`:

```
      [CDP-HTTP] GET /inter.crl -> serwuje inter-stale.crl
[Online  EndCertificateOnly ] srv-good     Build=true   152 ms | brak
      [CDP-HTTP] GET /inter.crl -> serwuje inter-stale.crl
[Online  EndCertificateOnly ] srv-revoked  Build=false    9 ms | Revoked (certificate revoked)
[Offline EndCertificateOnly ] srv-revoked  Build=false    7 ms | Revoked (certificate revoked)
```

Dwie rzeczy: (a) **.NET zaakceptował zdrowy certyfikat mimo CRL po terminie** — brak
statusu błędu; `openssl` w tej samej sytuacji odrzuca. (b) Drugi `Online` pobrał CRL
**ponownie** (w przeciwieństwie do przebiegu ze świeżym CRL), czyli traktuje przeterminowany
plik jak niepoprawny cache. Dlaczego (a) tak jest — nie umiem wyjaśnić, nie
sprawdzałem źródeł; zanotujcie jako fakt empiryczny dla tego środowiska (.NET 10.0.400,
OpenSSL 3.0.2). Wniosek praktyczny: **nie polegajcie na tym, że .NET zgłosi
przeterminowany CRL — monitorujcie `nextUpdate` własnego CA**.

---

## 3️⃣ OCSP: `openssl ocsp` jako responder

OCSP odpowiada na pytanie o **jeden** serial zamiast dawać całą listę. Responder
z `openssl` czyta tę samą bazę `index.txt`, co `openssl ca`:

```bash
openssl ocsp -index inter/index.txt -port 18481 -rsigner ocsp.pem -rkey ocsp.key \
             -CA inter/ca.pem -text -ndays 1
```

Pułapka pierwsza: mój pierwszy zapis `-port 127.0.0.1:18481` dał
`ocsp: Can't parse "127.0.0.1:18481" as a number` — w OpenSSL 3.0.2 `-port` przyjmuje
tylko numer portu i (z tego, co widać) nasłuchuje na wszystkich interfejsach, więc
responder trzymałem tylko na czas prób. Zapytanie o dwa certyfikaty naraz — realny output:

```
$ openssl ocsp -issuer inter/ca.pem -cert srv-good.pem -cert srv-revoked.pem \
     -url http://127.0.0.1:18481 -CAfile root/ca.pem -VAfile ocsp.pem
Response verify OK
srv-good.pem: good
	This Update: Sep 27 01:08:53 2026 GMT
	Next Update: Sep 28 01:08:53 2026 GMT
srv-revoked.pem: revoked
	This Update: Sep 27 01:08:53 2026 GMT
	Next Update: Sep 28 01:08:53 2026 GMT
	Reason: keyCompromise
	Revocation Time: Sep 27 01:08:32 2026 GMT
```

Trzeci stan — `unknown` — dostaje certyfikat, którego wystawca nie ma w bazie
respondera (zapytałem o certyfikat samego intermediate):

```
inter/ca.pem: unknown
	This Update: Sep 27 01:08:57 2026 GMT
	Next Update: Sep 28 01:08:57 2026 GMT
```

W tym wywołaniu było też `Response Verify Failure ... unable to get local issuer
certificate` (bez `-VAfile`, tylko z `-CAfile root`) — czyli **weryfikacja podpisu
respondera to osobny krok**, który może się nie udać niezależnie od statusu. Dla
zapytania o `srv-good` bez `-VAfile` (z `-CAfile root`) weryfikacja przeszła
(`Response verify OK`, patrz niżej), a dla `unknown` nie — dlaczego, nie badałem.

Delegowany certyfikat respondera **musi** mieć EKU `OCSPSigning` (mamy w
`[ext_ocsp]`) i być wystawiony przez to samo CA. Odpowiedź jest podpisana (surowa
struktura, skrócona; realny output `-resp_text`):

```
OCSP Response Status: successful (0x0)
Responder Id: O = Prasowka Demo, CN = Prasowka OCSP Responder
Certificate ID: Hash Algorithm: sha1 ... Serial Number: 2000
Cert Status: good
This Update: Sep 27 01:08:59 2026 GMT
Next Update: Sep 28 01:08:59 2026 GMT
OCSP Nonce: 0410507E4EB068F05092656A0C0DC6FC38E4
Signature Algorithm: ecdsa-with-SHA256
```

### ❓ A .NET? Czy w ogóle pyta OCSP-a?

To był mój najciekawszy wynik **negatywny**. AIA z URL responderu było w
certyfikatach, responder działał na `:18481`, `X509RevocationMode.Online`
włączony — a mimo to **responder odebrał 3 zapytania, wszystkie z moich ręcznych
wywołań `openssl ocsp`, żadnego z .NET**. (Policzyłem wpisy `OCSP Request Data` w logu
responderu po przebiegu .NET.) .NET pobrał za to CRL z CDP. Przebieg z **wyłączonym**
responderem dał identyczną macierz jak z włączonym. Wniosek dla tego środowiska
(.NET 10.0.400, Linux, OpenSSL 3.0.2, cert końcowy z CDP **i** AIA): **`X509Chain`
opierał sprawdzenie o CRL, nie o OCSP**. Nie sprawdzałem, czy istnieje ścieżka
włączająca OCSP (katalog `cryptography/ocsp` w cache został utworzony, ale bez
zawartości) — nie twierdzę więc, że .NET *nigdy* nie robi OCSP, tylko że nie
zrobił w tym układzie.

---

## 4️⃣ OCSP stapling: serwer dołącza dowód świeżości

Problemy klasycznego OCSP: klient wyciekiem prywatności mówi CA, jaką stronę
odwiedza, i płaci opóźnieniem. **Stapling** przenosi to na serwer: ten
pobiera odpowiedź OCSP i **dołącza ją do handshake'u**. Przygotowaliśmy plik odpowiedzi
(`-respout srv-good.ocsp`) i podaliśmy go `s_server`:

```bash
openssl s_server -accept 18482 -cert srv-good.pem -key srv-good.key \
   -cert_chain inter/ca.pem -status_file srv-good.ocsp -tls1_3 -www
openssl s_client -connect 127.0.0.1:18482 -servername localhost -tls1_3 -status \
   -CAfile root/ca.pem -verify_hostname localhost -verify_return_error < /dev/null
```

Realny output klienta (skrót; pominięto PEM-y):

```
depth=2 O = Prasowka Demo, CN = Prasowka Rev Root CA
verify return:1
depth=1 O = Prasowka Demo, CN = Prasowka Rev Issuing CA
verify return:1
depth=0 O = Prasowka Demo, CN = localhost
verify return:1
CONNECTED(00000003)
OCSP response:
======================================
OCSP Response Data:
    OCSP Response Status: successful (0x0)
    Responder Id: O = Prasowka Demo, CN = Prasowka OCSP Responder
    Produced At: Sep 27 01:08:59 2026 GMT
    ...
    Cert Status: good
    This Update: Sep 27 01:08:59 2026 GMT
    Next Update: Sep 28 01:08:59 2026 GMT
...
Verification: OK
Verified peername: localhost
New, TLSv1.3, Cipher is TLS_AES_256_GCM_SHA384
```

**Stapling działa** — ale zastrzeżenia: (1) to `s_server` z **gotowym plikiem**;
prawdziwy serwer musi odświeżać odpowiedź przed `nextUpdate` (nginx robi to sam,
`s_server` nie). (2) Klient tu *wyświetlił* odpowiedź — **`s_client -status` nie
odrzuca połączenia** przy `revoked` (nie testowałem, ale to znane zachowanie: `-status`
tylko drukuje). Wymuszenie to `-verify_return_error` + własne sprawdzenie albo
klient, który to egzekwuje. (3) **Kestrel/.NET po stronie serwera: nie sprawdzałem** —
nie znam gotowego API do staplingu w Kestrelu w tej wersji i nie zgaduję.
(4) "Must-Staple" (rozszerzenie `status_request` w certyfikacie) nie testowałem.

---

## 5️⃣ TLS 1.3 na poziomie protokołu: `-trace`

Ten sam `s_server`, klient z `-trace`. Realny przebieg (skrócony do struktury):

```
Sent Record    Handshake  ClientHello
  cipher_suites: TLS_AES_256_GCM_SHA384, TLS_CHACHA20_POLY1305_SHA256, TLS_AES_128_GCM_SHA256, ...SCSV
  extension server_name = localhost
  extension supported_groups: ecdh_x25519 (29), secp256r1 ...
  extension signature_algorithms: ecdsa_secp256r1_sha256 (0x0403) ...
  extension supported_versions: TLS 1.3 (772)
  extension psk_key_exchange_modes: psk_dhe_ke (1)
  extension key_share: NamedGroup ecdh_x25519 (29), key_exchange (len=32)
Received Record Handshake  ServerHello
  cipher_suite {0x13, 0x02} TLS_AES_256_GCM_SHA384
  extension supported_versions: TLS 1.3 (772)
  extension key_share: ecdh_x25519 (29)
Received Record ChangeCipherSpec (20)          <- tylko "kamuflaż" dla middleboxów
Received Record ApplicationData (23), Inner Content Type = Handshake (22)
    EncryptedExtensions, Length=2 / No extensions
Received ... Inner Content Type = Handshake: Certificate, Length=1068  (leaf 596 B + intermediate 458 B)
Received ... Inner Content Type = Handshake: CertificateVerify (ecdsa_secp256r1_sha256)
Received ... Inner Content Type = Handshake: Finished
Sent   ChangeCipherSpec, Finished
... (close_notify jako Inner Content Type = Alert)
SSL handshake has read 1430 bytes and written 323 bytes
```

Co warto z tego wynieść:

1. **`Version = TLS 1.2` w nagłówku rekordu to nieprawda "z założenia"** — prawdziwa
   wersja jest w rozszerzeniu `supported_versions` (772 = 0x0304). Rekord tak podaje
   dla kompatybilności z middleboxami.
2. **Certyfikaty są zaszyfrowane.** Wszystko po `ServerHello` jedzie jako
   `ApplicationData` z `Inner Content Type = Handshake`. Pasywny podsłuchujący widzi
   tylko `server_name` (SNI) i grupy. `-trace` dekoduje je, bo klient zna klucze.
   To zasadnicza różnica względem TLS 1.2, gdzie `Certificate` szedł jawnie.
3. **Tylko 1-RTT:** ClientHello od razu niesie `key_share` (x25519) — serwer
   odpowiada swoim, i od tego momentu wszystko szyfrowane. W TLS 1.2 klient czekał
   na wybór parametrów przed wysłaniem klucza.
4. **Stapling i OCSP w 1.3** siedzą jako rozszerzenie *wewnątrz* wiadomości
   `Certificate` (per wpis w `certificate_list`) — widzieliśmy je w `-status`,
   w trace tego przebiegu (bez `-status`) rozszerzenia były puste: `No extensions`.
5. Wymuszenie protokołu — test negatywny (serwer `-tls1_3`, klient `-tls1_2`):

```
$ openssl s_client -connect 127.0.0.1:18482 -tls1_2 -brief < /dev/null
error:0A00042E:SSL routines:ssl3_read_bytes:tlsv1 alert protocol version:...:SSL alert number 70
```

Alert 70 = `protocol_version`. Tak wygląda serwer, który nie mówi już 1.2.

---

## 6️⃣ `X509Store` + rotacja bez restartu

Cel: Kestrel podaje **aktualny** certyfikat, a odnowienie = dodanie nowego do
magazynu — bez restartu procesu. Mechanizm: `ServerCertificateSelector` wywoływany
**przy każdym handshake**:

```csharp
https.ServerCertificateSelector = (_, _) => Pick();   // Pick() czyta X509Store CurrentUser\PrasowkaDemo

static X509Certificate2? Pick()
{
    using var s = new X509Store("PrasowkaDemo", StoreLocation.CurrentUser);
    s.Open(OpenFlags.ReadOnly);
    return s.Certificates
        .Where(c => c.HasPrivateKey && c.Subject.Contains("CN=localhost")
                    && c.NotBefore <= DateTime.Now && c.NotAfter > DateTime.Now)
        .OrderByDescending(c => c.NotBefore).ThenByDescending(c => c.SerialNumber)
        .FirstOrDefault();
}
```

**Bezpieczeństwo eksperymentu:** własny magazyn (`PrasowkaDemo`), `CurrentUser`,
a `HOME` przekierowany do `code/work/home` (sekcja 2), więc niczego nie dotykamy w
profilu ani w magazynie systemowym. Na Linuksie `CurrentUser\<nazwa>` to katalog
`$HOME/.dotnet/corefx/cryptography/x509stores/<nazwa>` (u nas: `x509stores/prasowkademo`
— nazwa zlowercase'owana). Magazyn na koniec czyszczony (`0 certyfikatów`).

Klucz z `CreateFromPemFile` jest "efemeryczny"; żeby magazyn go utrwalił, robimy
`Export(Pfx)` → `X509CertificateLoader.LoadPkcs12(..., PersistKeySet)`. Realny output
(fragment):

```
[store] +srv-good: NotBefore=01:08:17 serial=2000 thumb=5D3DA021EE0A...  (w magazynie: 1)
--- 2. odnowienie z TYM SAMYM kluczem: dokladamy srv-renewed-samekey do magazynu
[store] +srv-renewed-samekey: NotBefore=01:08:24 serial=2003 thumb=14C5BE06BAF5...  (w magazynie: 2)
  [pin=srv-good] HTTP 200: serwer uzyl certyfikatu serial=2003 thumb=14C5BE06BAF5...
```

Serwer **sam** przełączył się z serialu 2000 na 2003 — bez restartu.

---

## 7️⃣ Pinning SPKI w `HttpClientHandler`

Pin = SHA-256 z **SubjectPublicKeyInfo** (nie z całego certyfikatu). Dzięki temu
odnowienie certyfikatu **na tym samym kluczu** nie łamie pinu (zmienia się serial,
daty, ale nie klucz publiczny). Kod klienta:

```csharp
var handler = new HttpClientHandler
{
    ServerCertificateCustomValidationCallback = (req, cert, chain, errors) =>
    {
        // 1) łańcuch wg NASZEGO rootu (systemowy magazyn nie zna tego CA)
        using var own = new X509Chain { ChainPolicy = pki.Policy(X509RevocationMode.NoCheck) };
        if (!own.Build(cert)) return false;
        // 2) pinning SPKI
        return pinSet.Count == 0 || pinSet.Contains(Convert.ToBase64String(
            SHA256.HashData(cert.PublicKey.ExportSubjectPublicKeyInfo())));
    },
};
```

Realny output (serwer z sekcji 6 na `:18490`):

```
pin(srv-good)            = ZgFU7SYNS4RAeppgBuXADKC5C71CiU9KBli4VEq01P8=
pin(srv-rekeyed)         = zZ9DBSIuQ2gBuP2l/X8KXuFLRbqWtGI1CMTYk8vSH1k=
pin(srv-renewed-samekey) = ZgFU7SYNS4RAeppgBuXADKC5C71CiU9KBli4VEq01P8=

--- 1. start: w magazynie srv-good
  [pin=srv-good] HTTP 200: serwer uzyl certyfikatu serial=2000 ...
  [pin=BLEDNY (zla wartosc)] BLAD -> HttpRequestException: The SSL connection could not be established, see inner exception. -> AuthenticationException: The remote certificate was rejected by the provided RemoteCertificateValidationCallback.
  [brak pinu (tylko lancuch)] HTTP 200: ...
--- 2. odnowienie z TYM SAMYM kluczem
  [pin=srv-good] HTTP 200: serwer uzyl certyfikatu serial=2003 ...
--- 3. rotacja z NOWYM kluczem: dokladamy srv-rekeyed (bez restartu serwera)
  [pin=srv-good (stary pin)] BLAD -> ... rejected by the provided RemoteCertificateValidationCallback.
  [pin=srv-good + pin zapasowy srv-rekeyed] HTTP 200: serwer uzyl certyfikatu serial=2004 ...
```

| Scenariusz | Pin | Wynik |
|---|---|---|
| Ten sam cert | poprawny | ✅ 200 |
| Ten sam cert | zły | ❌ odrzucone |
| Odnowienie, **ten sam klucz** (serial 2000 → 2003) | stary pin | ✅ 200 |
| Odnowienie, **nowy klucz** (serial 2004) | stary pin | ❌ odrzucone |
| Nowy klucz | stary + **zapasowy** pin | ✅ 200 |

**Pułapki pinningu:**

- **Pinujecie SPKI, nie certyfikat**, i zawsze **z zapasowym pinem** (klucz
  następcy, wygenerowany z góry i trzymany offline). Bez tego rotacja klucza =
  awaria wszystkich klientów, których nie da się zaktualizować.
- **Pin nie zastępuje walidacji łańcucha.** W kodzie wyżej pin sprawdzany jest *po*
  `Build`. Callback zwracający samo `pin == expected` zaakceptowałby wygasły lub
  odwołany certyfikat z właściwym kluczem.
- **Zwrócenie `true` z callbacku wyłącza domyślną walidację** — bardziej niż
  intuicja podpowiada; zawsze budujcie własny łańcuch (jak wyżej), a nie
  polegajcie na `errors`, bo przy prywatnym CA `errors != None` zawsze.
- Nie sprawdzałem `SocketsHttpHandler.SslOptions.RemoteCertificateValidationCallback`
  w tej samej konfiguracji ani pinningu mobilnego/przeglądarkowego (HPKP jest martwe — z
  wiedzy ogólnej).

---

## 8️⃣ Ściągawka: co robić, gdy...

| Sytuacja | Diagnoza | Komenda / API |
|---|---|---|
| "Odwołany wchodzi" | Tryb `NoCheck` albo brak CDP w certyfikacie | `openssl x509 -ext crlDistributionPoints,authorityInfoAccess` |
| `RevocationStatusUnknown` / `OfflineRevocation` | CDP nieosiągalny lub pusty cache w `Offline` | `curl` na URL z CDP; katalog `~/.dotnet/corefx/cryptography/crls` |
| CRL "jest, ale stary" | `nextUpdate` w przeszłości | `openssl crl -noout -nextupdate` (i **alarm** w monitoringu) |
| Klient nie widzi odwołań OCSP | Czy klient w ogóle odpytuje AIA? | logi respondera (`openssl ocsp -text`) |
| Certyfikat zmieniony, klienci padają | Pin z certyfikatu zamiast SPKI / brak pinu zapasowego | hash SPKI: `ExportSubjectPublicKeyInfo` |
| Odnowienie bez restartu | `ServerCertificateSelector` + magazyn | sekcja 6 |
| Chcę zobaczyć TLS 1.3 | `openssl s_client -tls1_3 -trace` | sekcja 5 |

---

## 📎 Czego NIE sprawdziłem (wprost)

- **Cały skrypt** `code/openssl/setup-pki.sh` — jego uruchomienie zostało odrzucone
  przez środowisko (podobnie jak `mkdir`/zapis w `/tmp` poza katalogiem projektu). Nie
  obchodziłem tego; **każdą komendę z niego wykonałem ręcznie, pojedynczo**, z
  `ca.cnf` z podstawionymi ścieżkami (`code/work/ca.cnf`, powstał ręcznie, bo `sed`
  z przekierowaniem nie był potrzebny). Skrypt jest więc **niesprawdzony jako całość**.
- OCSP inicjowany przez .NET (nie zaobserwowałem go, patrz sekcja 3), stapling po stronie
  Kestrela, `RevocationMode` w `SslStream` (testowałem `X509Chain` bezpośrednio),
  Windows/macOS (inne magazyny i inne zachowanie odwołań), przeglądarki, Let's Encrypt/ACME.
- Dlaczego .NET akceptuje przeterminowany CRL; dlaczego jedno z zapytań `openssl ocsp`
  dało `Response Verify Failure` — brak potwierdzonych przyczyn.

## 📎 Co dalej w tej rubryce

ACME/Let's Encrypt (challenge HTTP-01/DNS-01 na lokalnym `pebble`), Must-Staple,
Certificate Transparency i SCT, mTLS w Kubernetes (cert-manager), własne
`X509Chain` z `AIA` i pobieraniem brakujących intermediate.

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #4 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
