<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #15 — 8 października 2026

![SCT gate](https://img.shields.io/badge/TLS_%C2%B7_SCT_enforcement_%C2%B7_RFC_6962_%C2%B7_SslStream-5B2C83?style=for-the-badge&logo=letsencrypt&logoColor=white)

## Brama SCT w `SslStream`: klient, który nie wierzy certyfikatom bez dowodu z logu CT

</div>

---

> _W #6 zbudowaliśmy Certificate Transparency od zera i sprawdzaliśmy SCT na
> papierze — w konsoli, poza jakimkolwiek połączeniem. Dziś ten sam dowód
> egzekwujemy w żywym handshake'u: klient TLS zrywa połączenie, jeśli
> certyfikat serwera nie ma ważnego SCT._

**Dlaczego to ważne dla .NET deva?** Bo `SslStream` **sam z siebie nie sprawdza
SCT w ogóle**. Chrome i Safari wymuszają CT, ale Twój `HttpClient`, gRPC-owy
klient i usługa łącząca się z partnerem — nie. Jeśli chcesz mieć gwarancję „ten
certyfikat widziały publiczne logi", musisz ją sam napisać w
`RemoteCertificateValidationCallback`. A to callback, w którym pomyłka kosztuje
najwięcej: jedno `return true` i cała walidacja znika. Poniżej pełna,
uruchomiona implementacja z 16 prawdziwymi handshake'ami.

Środowisko: .NET SDK 10.0.400, OpenSSL 3.0.2, Python + `cryptography`
(jako niezależny weryfikator), Linux, **bez sieci zewnętrznej i bez Dockera**.
Kod: [`code/`](code/README.md).

| 🧪 Co | ✅ Status |
|---|---|
| Embedded SCT (RFC 6962) kodowany i weryfikowany ręcznie w C# | działa; `0 Warning(s), 0 Error(s)` |
| 16 handshake'ów TLS 1.3 `SslStream` ↔ `SslStream` po loopbacku | **0 rozbieżności** oczekiwanie vs wynik |
| Niezależna kontrola: `openssl x509 -text`, `openssl verify`, Python `cryptography` | zgodne (podpisy dobre OK, zepsute i przeniesione NIEPOPRAWNE) |
| Klucze prywatne na dysku | **żadnych** — tylko publiczne `*.pem` |
| Prawdziwe logi CT, prawdziwe CA, SCT przez rozszerzenie TLS / OCSP | **NIE sprawdzone** (sekcja 6) |

---

## 1️⃣ Co dokładnie sprawdza brama

Certyfikat z osadzonym SCT (OID `1.3.6.1.4.1.11129.2.4.2`) niesie listę
obietnic „log X widział ten precertyfikat o czasie T". Każdy SCT podpisuje
log strukturą (RFC 6962 §3.2):

```
version(0) | signature_type(0) | timestamp(8) | entry_type(1 = precert)
| issuer_key_hash(32) | tbs_certificate<24> | extensions<16>
```

Kluczowy szczegół: `tbs_certificate` to TBS **bez samego rozszerzenia SCT**.
Klient musi więc wyciąć rozszerzenie z DER-a certyfikatu i dostać bajt-w-bajt
to, co log podpisał. W C# robimy to na `AsnReader`/`AsnWriter` (kopiujemy
każdy element surowo, pomijamy tylko rozszerzenie o danym OID):

```csharp
string o = exts.ReadSequence().ReadObjectIdentifier();
if (o != oid) w.WriteEncodedValue(raw);   // raw = PeekEncodedValue() sprzed odczytu
```

Wystawca zrobił to samo w drugą stronę, a w kodzie jest kontrola
spójności: po wycięciu SCT z certu finalnego TBS **musi** być równy TBS
precertu — inaczej program rzuca wyjątek (nie rzucił).

Callback składa trzy kroki, w tej kolejności:

1. **nazwa** — `SslPolicyErrors.RemoteCertificateNameMismatch` → odrzuć;
2. **łańcuch** — własny `X509Chain` z `CustomRootTrust` i naszym rootem
   (ignorujemy `sslPolicyErrors.RemoteCertificateChainErrors`, bo system roota
   nie zna);
3. **SCT** — dla każdego SCT: znany log? timestamp nie z przyszłości? podpis
   poprawny kluczem tego logu nad (timestamp, hash klucza wystawcy, TBS)?
   Liczymy **różne** logi i porównujemy z progiem.

```csharp
var r = SctPolicy.Evaluate(x, ch.ChainElements[1].Certificate, trusted, min, DateTimeOffset.UtcNow);
return r.Ok;
```

---

## 2️⃣ Wynik — realny output (skrócony o linie „serwer:")

Każdy scenariusz to osobne połączenie TCP na loopbacku i osobny handshake.
Poniżej wynik uruchomienia (identyfikatory logów i serial są losowe przy każdym
uruchomieniu):

```
id   oczek.  wynik   opis
S0   REJECT  REJECT  bez callbacka (domyslna walidacja), root nieznany systemowi
                    klient: AuthenticationException: ... errors in the certificate chain: PartialChain
S1   ACCEPT  ACCEPT  NAIWNY callback (lancuch+nazwa), cert BEZ SCT
                    klient: handshake OK (Tls13), odpowiedz "pong"
S2   ACCEPT  ACCEPT  brama SCT min=1, jeden wazny SCT z log1
                    brama : 1 wazny(ch) z roznych logow (wymagane 1); SCT#0: OK (log 97CB50D3...)
S3   REJECT  REJECT  brama SCT min=1, cert BEZ SCT
                    brama : brak rozszerzenia SCT
S4   REJECT  REJECT  brama SCT min=1, SCT od nieznanego logu
                    brama : ... SCT#0: nieznany log D29CEB13...
S5   REJECT  REJECT  brama SCT min=1, SCT z odwroconym bitem w podpisie
                    brama : ... SCT#0: zly podpis (log 97CB50D3...)
S6   REJECT  REJECT  brama SCT min=1, SCT poprawnie podpisany, timestamp +1 dzien
                    brama : ... SCT#0: timestamp z przyszlosci
S7   REJECT  REJECT  brama SCT min=1, SCT przeniesiony z innego certu (inny SAN)
                    brama : ... SCT#0: zly podpis (log 97CB50D3...)
S8   ACCEPT  ACCEPT  brama SCT min=2, dwa SCT z log1 i log2
                    brama : 2 wazny(ch) z roznych logow (wymagane 2); SCT#0: OK (...); SCT#1: OK (...)
S9   REJECT  REJECT  brama SCT min=2, tylko jeden SCT
S10  REJECT  REJECT  brama SCT min=2, dwa SCT z TEGO SAMEGO logu
                    brama : 1 wazny(ch) z roznych logow (wymagane 2); SCT#0: OK; SCT#1: OK
S11  ACCEPT  ACCEPT  brama SCT min=1, SCT-smiec (nieznany log) + wazny SCT
S12  REJECT  REJECT  brama SCT min=1, wazny SCT, ale zly host (TargetHost)
                    brama : nazwa hosta nie pasuje
S13  REJECT  REJECT  brama SCT min=1, wazny SCT, ale cert z OBCEGO roota
                    brama : lancuch: PartialChain
S14  REJECT  REJECT  brama SCT min=1, SCT podpisany dla zlego issuer_key_hash
S15  REJECT  REJECT  brama SCT min=1, lista SCT obcieta (malformed)
                    brama : malformed: dlugosc listy 120 != 110
rozbieznosci oczekiwania vs wynik: 0
```

Kolumna „oczek." jest zapisana w kodzie przed uruchomieniem; wynik zgadza się
we wszystkich 16 przypadkach. Jedyne potknięcie przy pierwszym uruchomieniu
to pomyłka w API (patrz haczyk 7).

---

## 3️⃣ Niezależna kontrola

Skoro i wystawca, i weryfikator to ten sam autor (ja), potrzebny jest ktoś
trzeci. Trzy niezależne narzędzia czytają te same pliki PEM:

**`openssl verify`** potwierdza łańcuch i nazwę (OpenSSL ignoruje SCT):

```
$ openssl verify -CAfile work/root.pem -verify_hostname srv.example.test work/leaf-S2.pem
work/leaf-S2.pem: OK
```

**`openssl x509 -text`** na OpenSSL 3.0.2 tym razem **pretty-printuje** SCT
(w #6 mój eksperyment kończył się surowym dumpem — widać zależność od
sposobu zbudowania rozszerzenia/buildu; nie dochodziłem dlaczego):

```
CT Precertificate SCTs:
    Signed Certificate Timestamp:
        Version   : v1 (0x0)
        Log ID    : 97:CB:50:D3:B1:6E:D1:0B:...
        Timestamp : Oct  8 00:38:23.337 2026 GMT
        Extensions: none
        Signature : ecdsa-with-SHA256
```

**Python `cryptography`** (`verify_sct.py`) odtwarza TBS precertu własną
metodą (`tbs_precertificate_bytes`), buduje strukturę z §3.2 i weryfikuje
podpis kluczem publicznym logu — kod C# nie bierze w tym udziału:

```
leaf-S8.pem: SCT-ow w certyfikacie: 2
  log_id=97cb50d3... v1 PRE_CERTIFICATE: podpis OK
  log_id=815debc0... v1 PRE_CERTIFICATE: podpis OK
leaf-S5.pem: ... podpis NIEPOPRAWNY      (zepsuty bit)
leaf-S7.pem: ... podpis NIEPOPRAWNY      (SCT przeniesiony)
```

Zgodność z Pythonem oznacza coś mocniejszego niż „C# zgadza się z C#":
format `digitally-signed`, rekonstrukcja TBS i `issuer_key_hash` są poprawne
względem drugiej, niezależnej implementacji.

---

## 4️⃣ Haczyki — to, co naprawdę trzeba wiedzieć

### 🪤 Haczyk 1: poprawna walidacja łańcucha NIE znaczy „widziały to logi" (S1)

Callback, który „naprawia" nieznany root (budujemy łańcuch z własnym rootem,
sprawdzamy nazwę, zwracamy wynik `Build`), przepuszcza certyfikat **bez
żadnego SCT**: `handshake OK (Tls13)`. Dla serwera, któremu ufasz z racji
roota, to może być dokładnie to, co chcesz — ale to nie jest CT. Jeśli
polityka brzmi „wymagam SCT", musi być napisana jawnie.

### 🪤 Haczyk 2: rozstrzygający jest podpis nad TBS, nie sama obecność SCT (S5, S7, S14)

Samo „cert ma rozszerzenie SCT" nie znaczy nic. Przeniesienie SCT z innego
certyfikatu (S7: inny SAN, ten sam serial i daty), zmiana jednego bitu (S5)
i podpis nad złym `issuer_key_hash` (S14) — wszystkie oblewają na
weryfikacji podpisu. Sprawdzaj kryptografię, nie flagi.

### 🪤 Haczyk 3: zliczaj RÓŻNE logi (S10)

Dwa SCT z tego samego logu to jeden głos. Liczymy `HashSet` po `log_id`.
Bez tego „min=2" jest trywialne do obejścia (jedno zgłoszenie do jednego
logu dwa razy).

### 🪤 Haczyk 4: jeden śmieciowy SCT nie powinien zabijać certu (S11)

Lista może zawierać SCT-y z logów, których klient nie zna. Polityka „każdy
SCT musi być znany i poprawny" odrzuciłaby cert tylko dlatego, że wystawca
zgłosił go też do logu, którego nie masz na liście. Nasza polityka: licz
tylko poprawne i znane, ignoruj resztę. Odwrotne podejście (strict) to
decyzja projektowa — tu jej nie testowałem.

### 🪤 Haczyk 5: zegar i `timestamp` z przyszłości (S6)

SCT z timestampem w przyszłości, podpisany poprawnie, jest odrzucany. Bez
tego log (lub ktoś, kto ma jego klucz) mógłby wystawić SCT „z przyszłości",
który wygląda wiarygodnie. Uwaga na dryf zegara: nasz kod nie ma żadnej
tolerancji — produkcyjnie potrzebna będzie niewielka.

### 🪤 Haczyk 6: błąd po stronie klienta to wyjątek bez treści (wszystkie REJECT)

Klient dostaje zawsze to samo:
`AuthenticationException: The remote certificate was rejected by the provided
RemoteCertificateValidationCallback.` Powodu nie ma w wyjątku — zwracasz
tylko `bool`. Dlatego w kodzie powód zapisywany jest bokiem (`gateReason`);
w prawdziwej aplikacji loguj go w callbacku, inaczej diagnoza w
produkcji będzie zgadywaniem. Serwer w naszych testach widział po odrzuceniu
`EndOfStreamException` (koniec strumienia przy czytaniu danych) — **nie
rozróżniałem**, czy handshake serwera już się zakończył (w TLS 1.3 serwer
może skończyć wcześniej), czy zerwał się w trakcie.

### 🪤 Haczyk 7: pułapki API w .NET

- `ECDsa.SignData` domyślnie zwraca podpis w formacie IEEE P1363 (`r‖s`),
  a SCT niesie DER — trzeba wskazać `DSASignatureFormat.Rfc3279DerSequence`
  przy podpisie i weryfikacji (analogiczna pułapka jak w ACME, #13).
- `X509Extension.RawData` to zawartość `extnValue`, a SCT jest tam
  **jeszcze raz** opakowany w `OCTET STRING` — dwa poziomy.
- `CertificateRequest.CreateSelfSigned` zwraca cert **już z kluczem
  prywatnym**; `CopyWithPrivateKey` rzuca wtedy
  `InvalidOperationException: The certificate already has an associated
  private key` (zdarzyło mi się w pierwszym uruchomieniu).
- `GetSerialNumber()` zwraca bajty w kolejności little-endian — przy
  przepisywaniu serialu trzeba odwrócić.

### 🪤 Haczyk 8: `SslStream` nie pokaże Ci SCT dostarczonego inaczej niż w certyfikacie

Z wiedzy ogólnej i z kształtu API (tego nie próbowałem obchodzić, więc
traktuj jako **niezweryfikowane**): callback dostaje tylko certyfikat i
łańcuch; nie dostaje rozszerzeń TLS ani zszytej odpowiedzi OCSP. Dlatego
w .NET da się egzekwować wyłącznie SCT **osadzone w certyfikacie** — SCT
dostarczone rozszerzeniem TLS `signed_certificate_timestamp` lub w OCSP
nie są dla callbacka widoczne.

---

## 5️⃣ Co z tego dla .NET

- Wzorzec: **osobny** `X509Chain` z `CustomRootTrust` w callbacku, flagi
  `SslPolicyErrors` sprawdzane selektywnie (nazwa — tak, błędy łańcucha — nie,
  bo liczy je własny `Build`). Nie rób `return true`.
- Polityka SCT to funkcja czysta `(cert, issuer, logi, próg, czas) → wynik+powód`
  — łatwo ją testować jednostkowo bez TLS (to robi `SctPolicy.Evaluate`).
- Lista zaufanych logów (id → klucz publiczny) to konfiguracja, którą
  trzeba rotować; w produkcji pochodzi z listy logów przeglądarek
  (z wiedzy ogólnej, tu niezmierzone).
- Realne wymagania liczby SCT zależą od polityki (u przeglądarek m.in. od
  okresu ważności certu) — z wiedzy ogólnej, **bez weryfikacji**; nasze
  `min` to wartość z konfiguracji.

---

## 6️⃣ Czego NIE zweryfikowałem (wprost)

- **Prawdziwe logi CT i prawdziwe CA.** „Logi" to trzy klucze ECDSA w tym
  samym procesie; żadnego `add-pre-chain`, STH, ani kontaktu z
  rzeczywistym logiem. Nie badałem też, że certy z Web PKI mają SCT w
  formacie dokładnie takim jak tu (wystawiane przez *precertificate signing
  CA* — u nas precert i cert mają tego samego wystawcę).
- **SCT w rozszerzeniu TLS i w OCSP** — niedostępne w `SslStream` (wiedza
  ogólna, patrz haczyk 8), nie próbowałem tego obejść ani zmierzyć.
- **Kestrel/serwer jako strona egzekwująca** (np. mTLS i SCT dla klienta) —
  nie testowane; serwer w eksperymencie to goły `SslStream`.
- **Dryf zegara, odwołanie logów, okna czasowe logów (temporal sharding)** —
  brak.
- **Niezależność weryfikatorów:** łańcuch w .NET na Linuksie liczy systemowy
  OpenSSL (jak w #14, z wiedzy o implementacji). Zgodność SCT z Pythonem
  jest niezależna, ale dotyczy tylko podpisu; reguły polityki (próg, różne
  logi, śmieciowe SCT) to **moje** reguły, nie standard.
- **Windows/macOS, inne wersje .NET i OpenSSL** — tylko Linux, .NET 10.0.400,
  OpenSSL 3.0.2.
- **Powód różnicy z #6** (pretty-print SCT w `openssl x509 -text`): nie
  zbadany.

## 📎 Co dalej w tej rubryce

`consistency proof` (RFC 6962 §2.1.2) między dwoma STH + gossip, Must-Staple
(`id-pe-tlsfeature`) razem ze staplingiem, CAA/DANE (TLSA wyliczany z certu),
Kestrel jako strona egzekwująca, Windows/macOS store, ACME z `pebble`.

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #15 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
