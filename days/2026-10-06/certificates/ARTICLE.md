<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #13 — 6 października 2026

![ACME / RFC 8555](https://img.shields.io/badge/ACME_%C2%B7_RFC_8555_%C2%B7_http--01-1E3A5F?style=for-the-badge&logo=letsencrypt&logoColor=white)

## ACME od zera: własny serwer w Pythonie, własny klient w .NET, challenge http-01 — i siedem sposobów, żeby go zepsuć

</div>

---

> _Let's Encrypt nauczył świat, że certyfikat to nie dokument, który się
> "załatwia", tylko proces, który się automatyzuje. Ten proces ma kilkanaście
> kroków — i każdy z nich jest podpisany._

W #1–#6 budowaliśmy i łamaliśmy zaufanie, mTLS, odwołania i Certificate
Transparency. Wszystkie certyfikaty wystawialiśmy dotąd ręcznie przez `openssl`.
Dziś **ostatnie brakujące ogniwo: skąd certyfikat bierze się w produkcji** —
protokół **ACME (RFC 8555)**. Zamiast odpalać `certbot` (którego nie mamy) czy
`pebble` (brak binarki, brak sieci), **piszemy oba końce protokołu od zera**:
serwer w Pythonie i klienta w C#. Dwie niezależne implementacje muszą zgodzić się
co do każdego bajtu podpisanego JWS — to najlepszy możliwy test poprawności.

Środowisko: .NET SDK 10.0.400, OpenSSL 3.0.2, Python 3.10.4 +
`cryptography` 50.0.1, Linux, **bez sieci zewnętrznej i bez Dockera**.
Kod: [`code/`](code/README.md).

| 🧪 Co | ✅ Status |
|---|---|
| Serwer ACME (nonce, JWS ES256, thumbprint, http-01, CSR → cert) | działa, ~300 linii Pythona |
| Klient ACME w .NET (JWS, keyAuthorization, responder, CSR) | działa, `0 Warning(s), 0 Error(s)` |
| Pełny przepływ `happy` + `openssl verify -verify_hostname` | **OK** |
| Prawdziwy handshake TLS 1.3 z certem z ACME (`s_server`/`s_client`) | `Verification: OK` |
| 7 scenariuszy błędów (nonce, DER vs r‖s, url, podpis, keyAuth, CSR, kolejność) | każdy odrzucony właściwym kodem |
| Prawdziwy Let's Encrypt, DNS-01, TLS-ALPN-01, EAB, CAA, rotacja klucza konta | **NIE sprawdzone** (sekcja 7) |

---

## 1️⃣ Mapa protokołu: co się dzieje między `certbot` a certyfikatem

ACME to JSON przez HTTPS, w którym **każde żądanie POST jest podpisane** kluczem
konta (JWS, RFC 7515). Kroki:

1. `GET /directory` — katalog adresów (`newNonce`, `newAccount`, `newOrder`).
2. `HEAD /new-nonce` — jednorazowy `Replay-Nonce` (ochrona przed replayem).
3. `POST /new-acct` — rejestracja konta; w nagłówku JWS jest **cały klucz publiczny** (`jwk`).
4. `POST /new-order` — "chcę certyfikat na `demo.example.test`"; od teraz JWS niesie tylko `kid` (URL konta).
5. `POST /authz/…` — **POST-as-GET** (pusty payload!) po autoryzację i jej challenge.
6. Klient wystawia plik pod `/.well-known/acme-challenge/<token>` i `POST /chall/… {}`.
7. Serwer **sam** pobiera ten plik (http-01) i porównuje z `token.thumbprint`.
8. `POST …/finalize` z CSR (DER, base64url) → `POST /cert/…` → łańcuch PEM.

Sedno bezpieczeństwa to krok 7: **kto kontroluje HTTP domeny, ten dowodzi
kontroli nad domeną — i to konkretnym kontem**, bo w treści pliku jest
thumbprint klucza konta (sekcja 3).

> 📌 W produkcji CA łączy się na port 80 domeny, z walidacją z wielu punktów
> (multi-perspective issuance). U nas: `127.0.0.1:5002` z nagłówkiem
> `Host: demo.example.test` — odpowiednik opcji `-dnsserver` w `pebble`.
> To jedyne celowe uproszczenie sieciowe; reszta to logika protokołu.

---

## 2️⃣ JWS: pierwszy haczyk, na którym giną klienty

Ciało każdego żądania to „flattened JWS”: `protected`, `payload`, `signature`
(wszystko base64url, bez `=`). Podpisujemy ASCII-string
`protected + "." + payload`. W `protected`:

| Pole | Po co |
|---|---|
| `alg` | u nas wyłącznie `ES256` |
| `nonce` | z ostatniej odpowiedzi serwera, **jednorazowy** |
| `url` | **dokładny** adres żądania — chroni przed przekierowaniem podpisanego ciała na inny endpoint |
| `jwk` **albo** `kid` | dokładnie jedno: `jwk` tylko przy `newAccount`, potem `kid` |

**Haczyk nr 1: format podpisu.** ECDSA w świecie `openssl` to ASN.1 DER
(`SEQUENCE { r, s }`, 70–72 bajty). W JWS to **`r ‖ s`, dokładnie 2×32 bajty**
(RFC 7518 §3.4). .NET ma na to jawny parametr:

```csharp
var fmt = DSASignatureFormat.IeeeP1363FixedFieldConcatenation; // JWS (domyślne w SignData)
// DSASignatureFormat.Rfc3279DerSequence                       // DER = zły format dla JWS
byte[] sig = _key.SignData(data, HashAlgorithmName.SHA256, fmt);
```

Zmierzone: scenariusz `der-sig` (podpis DER) —

```
[client] SERWER ODRZUCIL: HTTP 400 urn:ietf:params:acme:error:malformed - podpis ES256 ma 71 B; wymagane 64 (r||s, nie DER)
```

71 bajtów zamiast 64. Po stronie Pythona robimy odwrotnie —
`encode_dss_signature(r, s)` składa DER z dwóch 32-bajtowych połówek, bo
`cryptography` weryfikuje tylko DER. Dwie biblioteki, dwa dialekty, jedna
konwersja w każdą stronę.

**Haczyk nr 2: współrzędne klucza.** `x` i `y` w JWK muszą mieć **dokładnie 32
bajty** (z wiodącymi zerami). `ECParameters.Q.X` w .NET dla P-256 już tak
zwraca; zrobiona „na piechotę” konwersja `BigInteger` gubiłaby zera i
rozjeżdżała thumbprint raz na ~256 kluczy.

---

## 3️⃣ keyAuthorization i thumbprint (RFC 7638): dlaczego token nie wystarczy

Plik pod `/.well-known/acme-challenge/<token>` zawiera **nie sam token**, tylko

```
keyAuthorization = token + "." + base64url(SHA256(canonical JWK))
```

Kanoniczny JWK (RFC 7638) to JSON z **wyłącznie** polami wymaganymi, kluczami
alfabetycznie, bez spacji:

```csharp
string canon = $"{{\"crv\":\"P-256\",\"kty\":\"EC\",\"x\":\"{x}\",\"y\":\"{y}\"}}";
return B64u(SHA256.HashData(Encoding.UTF8.GetBytes(canon)));
```

Po co thumbprint? Bez niego każdy, kto zobaczy token (np. w logach,
w cache proxy), mógłby „zaliczyć” walidację na swoim koncie. Z thumbprintem
plik jest **związany z kluczem konta, które o certyfikat prosi**. Serwer (Python)
liczy thumbprint z JWK zapisanego przy rejestracji — niezależna implementacja,
ten sam wynik, bo walidacja przeszła.

---

## 4️⃣ Przebieg `happy` — realny output

Serwer: `python3 server/mini_acme.py --out work` (w tle). Klient:

```
[client] scenariusz=happy domena=demo.example.test
[client] konto: thumbprint(JWK)=clgWSlnqD4jV7zRs7dW5V3_Qg87G-jxngd80mRtVkg4
[client] newAccount -> HTTP 201, kid=http://127.0.0.1:14000/acct/ffa8a934
[client] newOrder -> HTTP 201, status=pending
[client] challenge http-01: token=A_us5D98MKny... keyAuthorization = token.thumbprint
[responder] GET /.well-known/acme-challenge/A_us5D98MKnyzDF6Ti6XJgrEo2COrUESlbXoswr7G1s HTTP/1.1 | Host: demo.example.test
[client] POST {} na challenge -> serwer waliduje http-01...
[client] authorization status=valid
[client] finalize -> HTTP 200, order status=valid
[client] certyfikat: subject=CN=demo.example.test serial=2F7C881761FA... NotAfter=2026-10-13 01:47:11Z
```

Zwróć uwagę na linię `[responder]`: **to serwer ACME (Python) zapukał do
naszego responderu** i podał `Host: demo.example.test`. Responder to ~25 linii
na surowym `TcpListener` (nie `HttpListener` — ten sprawdza nagłówek `Host`
względem prefiksu i odrzuciłby nasz zabieg z `Host`; nie testowałem tego
empirycznie, to powód wyboru, nie zmierzony fakt).

Nasz klient pierwszy raz ruszył bez poprawek — ale nie od razu: pierwsza
kompilacja padła na `HttpClient.Send` (metoda synchroniczna, nie da się jej
`await`-ować; trzeba `SendAsync`).

Weryfikacja wystawionego certu **niezależnym narzędziem**:

```
$ openssl verify -CAfile work/ca.pem -verify_hostname demo.example.test work/leaf-chain.pem
work/leaf-chain.pem: OK
$ openssl verify -CAfile work/ca.pem -verify_hostname inna.example.test work/leaf-chain.pem
error 62 at 0 depth lookup: hostname mismatch
```

Fragment `openssl x509 -text`:

```
Issuer: O = Prasowka DEMO, CN = Prasowka mini-ACME DEMO CA
Validity   Not Before: Oct  6 01:42:11 2026 GMT   Not After : Oct 13 01:47:11 2026 GMT
Subject: CN = demo.example.test
X509v3 Basic Constraints: critical  CA:FALSE
X509v3 Key Usage: critical          Digital Signature
X509v3 Extended Key Usage:          TLS Web Server Authentication
X509v3 Subject Alternative Name:    DNS:demo.example.test
```

Zauważ `Not Before` (01:42) = 5 minut **przed** chwilą wystawienia (01:47): nasz
serwer cofa początek ważności o 5 min (tolerancja na rozjazd zegarów) — to
częsta praktyka CA (z wiedzy ogólnej, nie zmierzona u prawdziwych CA). Ważność 7 dni to nasz wybór; Let's Encrypt wystawia dziś
krótsze certyfikaty niż kiedyś, ale **konkretnych aktualnych wartości nie
sprawdzałem** (brak sieci).

---

## 5️⃣ Certyfikat z ACME w prawdziwym handshake'u TLS

```
$ openssl s_client -connect 127.0.0.1:14443 -CAfile work/ca.pem -verify_hostname demo.example.test -verify_return_error -brief
CONNECTION ESTABLISHED
Protocol version: TLSv1.3
Ciphersuite: TLS_AES_256_GCM_SHA384
Peer certificate: CN = demo.example.test
Signature type: ECDSA
Verification: OK
Verified peername: demo.example.test
```

Ten sam serwer **bez** `-CAfile` (zaufanie systemowe):

```
depth=0 CN = demo.example.test
verify error:num=20:unable to get local issuer certificate
... certificate verify failed
```

Czyli dokładnie to, co w #1: certyfikat jest poprawny kryptograficznie, ale
nikt go nie zna. **ACME nie tworzy zaufania — automatyzuje wystawianie.**
Zaufanie nadal zależy od tego, czy root CA jest w magazynie klienta.

---

## 6️⃣ Siedem sposobów na zepsucie protokołu (zmierzone)

Każdy scenariusz to osobne uruchomienie klienta z celowym defektem; wszystkie
wyniki skopiowane z realnych przebiegów.

| # | Scenariusz | Realna odpowiedź serwera | Co to uczy |
|---|---|---|---|
| 1 | `bad-nonce-retry` — nieznany nonce | `badNonce` → klient pobiera nowy i **ponawia → sukces** (log serwera: `POST /new-acct -> 400`, potem `201`) | RFC 8555 §6.5: `badNonce` to sytuacja normalna (np. restart serwera), klient MUSI umieć ponowić |
| 2 | `reuse-nonce` — ten sam nonce dwa razy, bez retry | `400 badNonce - nonce nieznany lub juz uzyty` | nonce jest jednorazowy → replay ciała JWS nie działa |
| 3 | `der-sig` | `400 malformed - podpis ES256 ma 71 B; wymagane 64` | r‖s ≠ DER |
| 4 | `wrong-url` — `url` w nagłówku `…/new-orderx` | `401 unauthorized - naglowek url '…/new-orderx' != '…/new-order'` | podpisane ciało nie przenosi się na inny endpoint |
| 5 | `wrong-account-key` — zepsuty bajt podpisu | `403 unauthorized - podpis JWS nie zgadza sie z kluczem` | podpis jest sprawdzany względem klucza konta z `kid` |
| 6 | `wrong-keyauth` — responder oddaje zły sufiks | authz `invalid`: `unauthorized - zla keyAuthorization: oczekiwano ...oFhJc7cCVw, dostano ...AAAAAAAAAA` | http-01 faktycznie porównuje zawartość, nie tylko status 200 |
| 7a | `csr-mismatch` — CSR na `inna-domena.example.test` po udanej walidacji | `400 badCSR - SAN w CSR ['inna-domena.example.test'] != identyfikatory zamowienia ['demo.example.test']` | walidacja domeny zalicza **zamówienie**, nie dowolny CSR |
| 7b | `finalize-early` — finalize przed walidacją | `403 orderNotReady - status zamowienia: pending` | maszyna stanów zamówienia: `pending → ready → valid` |

Scenariusz 6 pokazuje też ciekawą rzecz w logu respondera: **serwer pobrał plik
i wiedział, że jest zły** — ale nie powiedział klientowi nic w odpowiedzi na
`POST /chall`. Błąd pojawia się dopiero w obiekcie challenge przy kolejnym
`POST-as-GET`. Walidacja jest **asynchroniczna** (u nas wątek w tle); klient musi
odpytywać `authz`, a nie liczyć na odpowiedź na „gotowe”.

> ⚠️ **Haczyk nr 3 (mój własny błąd do przemyślenia):** w pierwszej wersji
> serwera komunikat błędu w scenariuszu 6 skracał oba ciągi do 12 pierwszych
> znaków — a one są **identyczne** (to token), więc komunikat brzmiał
> „oczekiwano saYU…, dostano saYU…”. Błąd leży w sufiksie (thumbprincie).
> Naprawione na porównywanie końcówek. Wniosek ogólny: komunikaty o rozjeździe
> pokazują **miejsce różnicy**, nie początek.

---

## 7️⃣ Czego NIE zweryfikowałem (wprost)

- **Prawdziwy Let's Encrypt / inny publiczny CA** — brak sieci zewnętrznej. Nasz
  klient mówi tylko do własnego serwera; zgodność z produkcyjnym CA to
  **hipoteza**. Realne CA wymagają m.in. HTTPS do API, `Content-Type:
  application/jose+json`, ewentualnie `externalAccountBinding`, obsługi
  `Retry-After` — nic z tego nie jest u nas sprawdzone.
- **`pebble`/`certbot`/`lego`** jako niezależny klient wobec naszego serwera —
  nie ma ich w środowisku (`which` nic nie znalazł), a obrazu nie pobierałem
  (brak sieci). Zgodność serwera ze standardowym klientem **niesprawdzona**;
  sprawdziliśmy tylko parę własny-klient ↔ własny-serwer.
- **DNS-01, TLS-ALPN-01, wildcard, CAA** (sprawdzanie rekordów `CAA` przez CA),
  **rotacja klucza konta** (`keyChange`), **odwołanie certyfikatu** przez ACME
  (`revokeCert`), **ARI** (renewal information) — nie zaimplementowane.
- Serwer: brak HTTPS, brak limitów, jeden algorytm (ES256), tylko `dns`,
  stan w pamięci. Walidacja nie obsługuje przekierowań ani IPv6.
- **Windows/macOS** — wyłącznie Linux.
- Porównania z aktualnymi limitami/okresami ważności publicznych CA to wiedza
  ogólna, nie zmierzona tutaj.

## 8️⃣ Ściągawka

| Pojęcie | Jedno zdanie |
|---|---|
| JWS ES256 | podpis to `r‖s` 64 B; w .NET `IeeeP1363FixedFieldConcatenation` |
| Nonce | jednorazowy; `badNonce` → pobierz nowy i ponów |
| `url` w JWS | musi równać się adresowi żądania |
| `jwk` vs `kid` | `jwk` tylko do `newAccount`, potem `kid` |
| POST-as-GET | POST z pustym `payload` (`""`), zwykły GET → 405 |
| keyAuthorization | `token . base64url(SHA256(kanoniczny JWK))` |
| Walidacja | asynchroniczna; polluj `authz`/`order` |
| Finalize | CSR musi pasować do identyfikatorów zamówienia |

## 📎 Co dalej w tej rubryce

Rozszerzenie serwera o **CAA** (rekordy DNS ograniczające, kto może wystawiać),
**DNS-01**/wildcard, `keyChange`, `revokeCert` (spięcie z OCSP z #4);
zgodność z prawdziwym klientem (`pebble`/`lego`) gdy będzie sieć;
`consistency proof` RFC 6962, Must-Staple + SCT, weryfikacja SCT w
`SslStream`/Kestrelu, DANE, Windows/macOS store.

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #13 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
