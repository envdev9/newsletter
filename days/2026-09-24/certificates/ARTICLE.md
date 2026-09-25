<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #1 — 24 września 2026

![TLS / X.509](https://img.shields.io/badge/TLS_%2F_X.509-2E8B57?style=for-the-badge&logo=letsencrypt&logoColor=white)

## Certyfikaty od zera: dlaczego przeglądarka ufa jednemu kluczowi, a drugiemu nie

</div>

---

> _"SSL certificate problem: self signed certificate" to nie jest błąd narzędzia -
> to narzędzie poprawnie robi dokładnie to, do czego certyfikaty służą: odmawia
> zaufania czemuś, czego nikt z zewnątrz nie poświadczył._

To pierwsze wydanie rubryki o certyfikatach i TLS - zaczynamy od fundamentu,
na którym stoi absolutnie wszystko dalej: **czym różni się klucz publiczny od
prywatnego, jak z tej różnicy wynika podpis cyfrowy, i jak z podpisów buduje się
łańcuch zaufania** od self-signed root CA aż do certyfikatu serwera, na którym
się łączycie. Teorię domykamy dwoma realnymi eksperymentami: generujemy własny
CA i certyfikat przez `openssl` (prawdziwe komendy, prawdziwy output), a potem
weryfikujemy ten łańcuch programowo w .NET (`X509Certificate2` + `X509Chain`,
też z prawdziwym outputem - łącznie z przypadkiem, gdzie walidacja się psuje).
Cel tej rubryki nie jest "poznaj kilka ciekawostek" - jest **zrozumieć mechanizm
na tyle dobrze, żeby samemu zdiagnozować dowolny błąd TLS w logach**, nie tylko
skopiować rozwiązanie ze Stack Overflow.

---

## 1️⃣ Klucz publiczny i prywatny - skąd bierze się magia

### Problem, który to rozwiązuje

Klasyczne szyfrowanie (symetryczne) ma jeden klucz do szyfrowania i
odszyfrowania. Działa świetnie, jeśli obie strony już wcześniej bezpiecznie
wymieniły ten klucz - ale to właśnie jest problem "jajko i kura": żeby bezpiecznie
przesłać klucz, potrzebujesz już bezpiecznego kanału, a jeśli go masz, to po co
Ci klucz? Internet nie ma bezpiecznego kanału "z góry" - łączysz się z serwerem,
którego nigdy wcześniej nie widzieliście, przez sieć, którą ktoś może
podsłuchiwać.

### Jak to działa naprawdę

Kryptografia asymetryczna (RSA, ECDSA i inne) generuje **parę matematycznie
powiązanych kluczy**: to, co zaszyfrujesz jednym, da się odszyfrować **tylko**
drugim z tej pary - nie tym samym. To jest cała magia. Jeden klucz zostaje
**publiczny** (możesz go rozdawać każdemu, wkleić na stronę, wysłać mailem -
nic złego się nie stanie), drugi zostaje **prywatny** (nigdy, przenigdy nie
opuszcza twojej maszyny).

W praktyce RSA opiera się na tym, że łatwo jest wymnożyć dwie duże liczby
pierwsze, ale ekstremalnie trudno (przy dzisiejszej mocy obliczeniowej,
przy kluczach 2048+ bitów) rozłożyć ich iloczyn z powrotem na czynniki. Klucz
publiczny zawiera ten iloczyn, klucz prywatny zawiera oryginalne liczby
pierwsze. Nie musicie umieć rozkładać liczb na czynniki, żeby zrozumieć TLS -
musicie tylko zapamiętać **efekt**: znajomość klucza publicznego w żaden
praktyczny sposób nie pozwala odtworzyć klucza prywatnego.

Z tej jednej właściwości matematycznej wynikają **dwa zupełnie różne
zastosowania**, które developerzy regularnie ze sobą mylą:

| Cel | Kto czym szyfruje | Kto czym odczytuje/weryfikuje | Po co |
|---|---|---|---|
| **Poufność** (szyfrowanie) | Nadawca szyfruje **kluczem publicznym** odbiorcy | Odbiorca odszyfrowuje **swoim kluczem prywatnym** | Tylko właściciel klucza prywatnego przeczyta wiadomość |
| **Autentyczność** (podpis) | Podpisujący szyfruje (podpisuje) skrót danych **swoim kluczem prywatnym** | Każdy weryfikuje **kluczem publicznym** podpisującego | Każdy może potwierdzić, że dane pochodzą od właściciela klucza prywatnego i nie zostały zmienione |

To drugie zastosowanie - podpis - jest tym, na czym stoją certyfikaty X.509.
W realnym TLS 1.2/1.3 samo szyfrowanie ruchu HTTP nie odbywa się już przez
RSA (za wolne dla dużych danych) - RSA/ECDSA służy do **uzgodnienia** jednorazowego
klucza symetrycznego (handshake) i do **podpisywania**, a cały dalszy ruch leci
szybkim szyfrem symetrycznym (AES-GCM, ChaCha20). To ważne rozróżnienie: TLS
to hybryda, nie "czyste RSA na każdy bajt".

### Podpis cyfrowy krok po kroku

1. Podpisujący liczy skrót (hash, np. SHA-256) danych, które chce podpisać.
2. Szyfruje ten skrót swoim **kluczem prywatnym** - wynik to podpis.
3. Odbiorca niezależnie liczy skrót tych samych danych.
4. Odbiorca odszyfrowuje podpis **kluczem publicznym** podpisującego - dostaje
   skrót, który podpisujący faktycznie policzył.
5. Jeśli oba skróty się zgadzają: dane nie zostały zmienione (integralność) I
   pochodzą od kogoś, kto ma odpowiadający klucz prywatny (autentyczność).

To dokładnie ten mechanizm certyfikat X.509 wykorzystuje - z jedną kluczową
różnicą: to, co jest "podpisywane", to nie dowolna wiadomość, tylko **czyjś
klucz publiczny razem z jego tożsamością** (`Subject: CN=api.example.com, ...`).
Certyfikat to w istocie: *"ja, wystawca, poświadczam podpisem, że ten oto klucz
publiczny należy do tego oto podmiotu"*.

---

## 2️⃣ Łańcuch zaufania: root CA → intermediate → leaf

### Problem, który to rozwiązuje

Skoro certyfikat to "podpisane poświadczenie", to od razu pojawia się pytanie:
**kto poświadcza wystawcę?** Gdyby każdy mógł sam siebie poświadczyć bez żadnej
dalszej weryfikacji, certyfikaty byłyby bezwartościowe - atakujący też umie
wygenerować parę kluczy i podpisać nią cokolwiek.

### Jak to działa naprawdę

X.509 rozwiązuje to hierarchią podpisów, zwykle trzypoziomową:

```
Root CA (self-signed)
   │  podpisuje kluczem prywatnym roota
   ▼
Intermediate CA
   │  podpisuje kluczem prywatnym intermediate
   ▼
Leaf / end-entity certificate (np. wasz serwer)
```

- **Root CA** to certyfikat **self-signed** (`Issuer == Subject`) - podpisuje
  sam siebie własnym kluczem prywatnym, bo nie ma nikogo "wyżej", kto mógłby go
  podpisać. Jego klucz publiczny jest **wstępnie zainstalowany** w systemie
  operacyjnym / przeglądarce (setki rootów, audytowane latami przez CA/Browser
  Forum, WebTrust). To jest **jedyne miejsce w całym łańcuchu, gdzie zaufanie
  bierze się "znikąd" - z decyzji producenta systemu, nie z kryptografii**.
  Cała reszta łańcucha to już czysta matematyka.
- Root prawie nigdy nie podpisuje certyfikatów serwerów bezpośrednio - jego
  klucz prywatny jest przechowywany offline, w sejfie, bo jego kompromitacja
  unieważnia zaufanie do całego świata. Zamiast tego root podpisuje jeden lub
  kilka certyfikatów **intermediate CA**, które są operacyjnie używane do
  podpisywania certyfikatów końcowych.
- **Leaf certificate** (wasz `api.example.com`) jest podpisany kluczem
  prywatnym intermediate CA. `BasicConstraints: CA:FALSE` mówi jasno: ten
  certyfikat sam nie może niczego dalej podpisywać.

### Jak klient weryfikuje cały łańcuch

Kiedy przeglądarka/`HttpClient` dostaje certyfikat serwera, robi w skrócie:

1. Bierze `leaf.pem`, sprawdza pole `Issuer` - to nazwa intermediate CA.
2. Znajduje certyfikat tego intermediate (serwer zwykle go dosyła razem z
   leaf, żeby klient nie musiał go szukać w sieci).
3. Weryfikuje podpis na `leaf.pem` kluczem publicznym z certyfikatu
   intermediate (dokładnie mechanizm z sekcji 1).
4. Sprawdza `Issuer` certyfikatu intermediate - to nazwa roota. Szuka tego
   roota **we własnym, lokalnym magazynie zaufanych certyfikatów** (nie w
   sieci - to musi być lokalne, bo magazyn zaufanych rootów to jedyny punkt
   zaczepienia całej układanki).
5. Jeśli root jest w lokalnym magazynie zaufania: łańcuch jest **kompletny i
   zaufany** - koniec weryfikacji, sukces.
6. Jeśli któregoś ogniwa brakuje, podpis się nie zgadza, albo root nie jest w
   magazynie zaufania: **łańcuch jest niezaufany** - to właśnie komunikat
   `unable to get local issuer certificate` / `self signed certificate` /
   "połączenie nie jest prywatne".

### Self-signed vs CA-signed - dlaczego jeden budzi zaufanie, a drugi ostrzeżenie

**Self-signed certificate** to certyfikat, w którym `Issuer == Subject` -
podmiot podpisał sam siebie. Kryptograficznie taki podpis jest w pełni
poprawny (klucz prywatny faktycznie pasuje do publicznego), ale to
**nie mówi wam nic o tym, kim naprawdę jest właściciel**. Każdy - łącznie z
atakującym - może w sekundę wygenerować self-signed certyfikat z
`CN=twojbank.pl`. Podpis potwierdza tylko "ten klucz publiczny i ta nazwa
występują razem", a nie "ta nazwa naprawdę należy do tego, kto twierdzi że
jest jej właścicielem".

**CA-signed certificate** ma tę samą kryptografię, ale wystawca (CA) - zanim
podpisał - **zweryfikował kontrolę nad domeną/organizacją** (np. przez DNS/HTTP
challenge w ACME/Let's Encrypt, albo dokumenty firmowe przy certyfikatach EV/OV).
Przeglądarka ufa nie samemu podpisowi, tylko **decyzji roota, który jest
audytowany zewnętrznie i zobowiązany do rzetelnej weryfikacji** (naruszenie
tego zaufania = usunięcie roota z magazynów wszystkich przeglądarek świata -
to się realnie zdarzało, np. sprawa Symantec/DigiCert w 2017-2018).

Dlatego self-signed certyfikaty są w pełni sensowne **wtedy, gdy sami jesteście
obiema stronami** i świadomie instalujecie swój root w zaufanym magazynie
(homelab, testy, mTLS między własnymi usługami - dokładnie to, co robimy w
sekcji 4 tego wydania). Nie mają sensu tam, gdzie łączy się z wami ktoś obcy,
kto nie ma powodu ufać waszemu kluczowi.

---

## 3️⃣ TLS 1.2 vs TLS 1.3 - co realnie się zmieniło

Kilka konkretów, nie "1.3 jest nowsze więc lepsze":

- **Handshake:** TLS 1.2 potrzebuje **2 pełne round-tripy** (ClientHello →
  ServerHello+certyfikat+parametry klucza → ClientKeyExchange+Finished →
  Finished), zanim popłynie pierwszy bajt danych aplikacji. TLS 1.3 robi to w
  **1 round-tripie** - klient od razu w `ClientHello` proponuje `key_share`
  (parametry Diffie-Hellman), więc serwer w jednej odpowiedzi kończy
  uzgadnianie klucza i wysyła `Finished`. Przy resumpcji (powrót do znanego
  serwera) TLS 1.3 potrafi nawet **0-RTT** - dane aplikacji lecą razem z
  pierwszym pakietem (kosztem pewnych ograniczeń co do odporności na replay
  attack dla tych pierwszych danych).
- **Forward secrecy obowiązkowo:** TLS 1.2 dopuszczał statyczny RSA key
  exchange - jeśli ktoś kiedyś ukradnie klucz prywatny serwera, może
  odszyfrować **cały wcześniej nagrany ruch**. TLS 1.3 wymusza efemeryczne
  (EC)DHE przy każdym połączeniu - klucz sesji ginie razem z sesją, kradzież
  klucza prywatnego serwera nie odszyfrowuje przeszłości.
- **Usunięty balast:** TLS 1.3 wyrzucił RC4, CBC-mode w starym stylu (podatny
  na ataki typu BEAST/Lucky13), kompresję (CRIME), renegocjację (podatną na
  ataki typu triple handshake) i statyczne RSA/DH. Mniej opcji = mniej
  powierzchni ataku i prostszy kod do audytu.
- **Więcej handshake'u zaszyfrowane:** w TLS 1.3 certyfikat serwera jest
  wysyłany już zaszyfrowany (po uzgodnieniu kluczy z `ClientHello`/`ServerHello`),
  co utrudnia pasywne podsłuchiwanie, do jakich serwisów faktycznie się
  łączycie (choć SNI w `ClientHello` wciąż zwykle leci jawnie, chyba że jest
  ECH - Encrypted Client Hello).

Praktycznie: jeśli macie wybór, wymuszajcie **minimum TLS 1.2**, docelowo
**TLS 1.3** wszędzie gdzie się da - w .NET robi się to przez
`SslClientAuthenticationOptions.EnabledSslProtocols` / Kestrel
`HttpsConnectionAdapterOptions`, ale domyślne ustawienie (`SslProtocols.None` =
"pozwól systemowi operacyjnemu wynegocjować najlepszy wspólny wariant") jest
**właściwym wyborem w 99% przypadków** - ręczne przypinanie konkretnej wersji
zwykle tylko psuje kompatybilność w przyszłości, gdy stara wersja zostanie
wyłączona po stronie OS.

---

## 4️⃣ Praktyka 1: własne CA i certyfikat przez `openssl`

Cała teoria z sekcji 1-2 w praktyce, krok po kroku, prawdziwymi komendami
(pełny skrypt: [`code/openssl/generate-pki.sh`](code/openssl/generate-pki.sh)).

### Krok 1-2: root CA (klucz + self-signed certyfikat)

```bash
openssl genrsa -out ca.key 4096

openssl req -x509 -new -key ca.key -sha256 -days 3650 \
  -subj "/C=PL/O=Prasowka Demo CA/CN=Prasowka Root CA" \
  -out ca.pem
```

`-x509` mówi opensslowi: nie twórz CSR, od razu wystaw self-signed certyfikat
(bo to root - nikt inny go nie podpisuje).

### Krok 3-5: leaf - klucz, CSR, podpisanie przez nasze CA

```bash
openssl genrsa -out leaf.key 2048
openssl req -new -key leaf.key \
  -subj "/C=PL/O=Prasowka Demo/CN=api.prasowka.local" \
  -out leaf.csr

openssl x509 -req -in leaf.csr -CA ca.pem -CAkey ca.key -CAcreateserial \
  -days 825 -sha256 -extfile leaf.ext -out leaf.pem
```

(`leaf.ext` ustawia `subjectAltName=DNS:api.prasowka.local`,
`basicConstraints=CA:FALSE`, `extendedKeyUsage=serverAuth` - pełna treść w
skrypcie.) Realny output tego kroku:

```
=== 5. Podpisanie CSR naszym CA -> certyfikat leaf.pem (CA-signed) ===
Certificate request self-signature ok
subject=C = PL, O = Prasowka Demo, CN = api.prasowka.local
```

### Inspekcja wygenerowanego certyfikatu (prawdziwy output)

```bash
openssl x509 -in leaf.pem -noout -subject -issuer -dates -ext subjectAltName
```

```
subject=C = PL, O = Prasowka Demo, CN = api.prasowka.local
issuer=C = PL, O = Prasowka Demo CA, CN = Prasowka Root CA
notBefore=Sep 24 22:08:44 2026 GMT
notAfter=Dec 27 22:08:44 2028 GMT
X509v3 Subject Alternative Name:
    DNS:api.prasowka.local
```

Widać dokładnie sekcję 2 w akcji: `subject` leafa to nasz serwer, `issuer`
leafa to nasze CA - to pole jest tym, po którym klient (i za chwilę .NET)
odbudowuje łańcuch.

### Krok 6 + weryfikacja przez `openssl verify` (prawdziwy output)

Dodatkowo generujemy `rogue.pem` - certyfikat self-signed, zupełnie
niepowiązany z naszym CA (symuluje typowy realny przypadek: serwer wystawia
sam sobie certyfikat):

```bash
openssl verify -CAfile ca.pem leaf.pem
openssl verify -CAfile ca.pem rogue.pem
```

```
leaf.pem: OK
C = PL, O = Rogue Self-Signed, CN = rogue.local
error 18 at 0 depth lookup: self-signed certificate
error rogue.pem: verification failed
```

To jest to samo zdanie, które zobaczycie za chwilę w .NET, i to samo, które
zobaczylibyście w logach `curl`/nginx/dowolnego klienta TLS na świecie -
`openssl verify` tylko nazywa błąd wprost, zamiast owijać go w bardziej
ogólnikowy komunikat przeglądarki.

---

## 5️⃣ Praktyka 2: programowa weryfikacja łańcucha w .NET

`X509Certificate2` ładuje pojedynczy certyfikat, ale sam w sobie **nic nie
weryfikuje** - to tylko kontener na dane certyfikatu. Weryfikacją łańcucha
(dokładnie kroki 1-6 z sekcji 2) zajmuje się `X509Chain`. Pełny kod:
[`code/dotnet/CertChainDemo/Program.cs`](code/dotnet/CertChainDemo/Program.cs).

Kluczowy fragment - budowa łańcucha z **jawnie wskazanym** zaufanym CA
(`CustomRootTrust`), bez dotykania magazynu systemowego:

```csharp
using var chain = new X509Chain();
chain.ChainPolicy.TrustMode = X509ChainTrustMode.CustomRootTrust;
chain.ChainPolicy.CustomTrustStore.Add(trustedCa);
chain.ChainPolicy.RevocationMode = X509RevocationMode.NoCheck;

bool valid = chain.Build(subject);
```

`X509CertificateLoader.LoadCertificateFromFile(...)` (a nie przestarzały już
konstruktor `new X509Certificate2(path)`) to aktualny, zalecany sposób
wczytania certyfikatu od .NET 9 wzwyż.

### Realny output (`dotnet run`, .NET SDK 10.0.400)

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

Trzy scenariusze to trzy realne sytuacje z codziennej pracy:

1. **Scenariusz 1** to jak powinien wyglądać wasz `HttpClient`/`SslStream` w
   testach integracyjnych albo mTLS między własnymi usługami - jawnie mówicie
   "ufam temu jednemu CA", nie ruszając magazynu systemowego całej maszyny.
2. **Scenariusz 2** to dokładnie to, co dostaniecie, jeśli wdrożycie ten sam
   `leaf.pem` na serwer produkcyjny bez zainstalowania `ca.pem` po stronie
   klienta - `PartialChain: unable to get local issuer certificate` to
   .NET-owy odpowiednik `curl`-owego `SSL certificate problem: unable to get
   local issuer certificate`. Certyfikat sam w sobie jest technicznie
   bez zarzutu - problem w tym, że nikt, komu klient ufa, go nie poświadczył.
3. **Scenariusz 3** to `self signed certificate` - dokładnie ten komunikat,
   który zobaczycie, gdy ktoś (albo wy sami, przez pomyłkę) wystawi certyfikat
   serwera bez żadnego CA w ogóle. `UntrustedRoot` w .NET i `self-signed
   certificate` w `openssl verify` to ten sam błąd nazwany przez dwa różne
   narzędzia.

Wszystko powyżej sprawdzone lokalnie, na żywo, bez zmyślania - dokładne
komendy do odtworzenia: [`code/README.md`](code/README.md).

---

## 📎 Co dalej w tej rubryce

Kolejne wydania podniosą poziom: certyfikaty pośrednie (multi-level chain),
mTLS z obu stron, konfiguracja Kestrel/HTTPS w ASP.NET Core, magazyn
certyfikatów systemu (`X509Store`), OCSP/CRL (odwoływanie certyfikatów), SNI,
ACME/Let's Encrypt, przypinanie certyfikatów (pinning) i typowe pułapki przy
mTLS w Kubernetes/Kestrel.

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — dokładne komendy dla obu części
(`openssl` i `.NET`).

---

<div align="center">

[← wróć do wydania #1 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
