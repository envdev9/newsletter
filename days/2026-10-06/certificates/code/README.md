# Kod do wydania #13 — ACME (RFC 8555) od zera: serwer w Pythonie, klient w .NET, http-01

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (sprawdzone na 10.0.400), **Python 3** z pakietem `cryptography`
(sprawdzone: Python 3.10.4, cryptography 50.0.1), `openssl` (sprawdzone na 3.0.2), Linux.
**Bez sieci zewnętrznej i bez Dockera** — wszystko na `127.0.0.1`.

> **Bezpieczeństwo:** serwer ACME to zabawka edukacyjna (stan w pamięci, HTTP zamiast HTTPS,
> brak limitów). Klucz demo-CA żyje tylko w pamięci procesu serwera. Klucz konta ACME klienta
> też tylko w pamięci. Na dysk (`code/work/`, ignorowane przez git) trafiają: `ca.pem`
> (publiczny), `leaf-chain.pem` oraz `leaf.key` — **jednorazowy klucz DEMO**, nie używaj go nigdzie.
> Porty: ACME `14000`, responder http-01 `5002`, opcjonalny `s_server` `14443` — wszystkie tylko loopback.

## Fragment prasówki, którego dotyczy ten kod

> Zamiast `certbot` i zamiast `pebble` (brak sieci, brak binarki) budujemy **oba końce ACME od zera**:
> serwer (Python, ~300 linii: nonce'y, weryfikacja JWS ES256, thumbprint RFC 7638, walidacja http-01,
> CSR → wystawienie certu) i klienta (.NET: JWS, `keyAuthorization`, własny responder HTTP na
> `TcpListener`, `CertificateRequest`). Dwie niezależne implementacje muszą się zgodzić co do każdego
> bajtu podpisanego JWS — i zgadzają się. Potem psujemy protokół na siedem sposobów i patrzymy, jak
> serwer odpowiada kodami `urn:ietf:params:acme:error:*`.

## Struktura

```
code/
├── server/mini_acme.py          # serwer ACME (stdlib http.server + cryptography)
├── dotnet/AcmeLab/              # klient ACME (Program.cs, AcmeLab.csproj)
└── work/                         # generowane (gitignored): ca.pem, leaf-chain.pem, leaf.key
```

## Uruchomienie (każde polecenie osobno, z katalogu `code/`)

```bash
# terminal 1: serwer ACME (zostaje w tle)
python3 server/mini_acme.py --out work

# terminal 2: build + scenariusz
dotnet build dotnet/AcmeLab/AcmeLab.csproj -c Release
dotnet run --no-build -c Release --project dotnet/AcmeLab -- happy demo.example.test work

# niezależna weryfikacja wystawionego certu
openssl verify -CAfile work/ca.pem -verify_hostname demo.example.test work/leaf-chain.pem
openssl x509 -noout -text -in work/leaf-chain.pem

# opcjonalnie: prawdziwy handshake TLS z certem z ACME
openssl s_server -accept 14443 -cert work/leaf-chain.pem -key work/leaf.key -www
openssl s_client -connect 127.0.0.1:14443 -CAfile work/ca.pem -verify_hostname demo.example.test -verify_return_error -brief
```

Scenariusze klienta (`dotnet run ... -- <scenariusz> [domena] [katalog]`):

| Scenariusz | Co psuje | Oczekiwany wynik |
|---|---|---|
| `happy` | nic | cert wystawiony, `openssl verify: OK` |
| `bad-nonce-retry` | pierwszy nonce nieznany | `badNonce` → klient pobiera nowy i ponawia → OK |
| `reuse-nonce` | ponowne użycie nonce (bez retry) | `badNonce` |
| `der-sig` | podpis ES256 w DER zamiast r‖s | `malformed` (71 B zamiast 64) |
| `wrong-url` | nagłówek `url` ≠ adres żądania | `unauthorized` |
| `wrong-account-key` | zepsuty bajt podpisu | `unauthorized` |
| `wrong-keyauth` | responder oddaje złą `keyAuthorization` | authz `invalid` |
| `csr-mismatch` | CSR na inną domenę niż zamówienie | `badCSR` |
| `finalize-early` | finalize przed walidacją | `orderNotReady` |

Serwer **nie jest** restartowany między scenariuszami (stan w pamięci rośnie); restart = nowe CA.

## Uwaga o środowisku, w którym powstał artykuł

Nie używano żadnych skryptów `.sh` — wszystkie komendy wykonano pojedynczo, outputy w artykule są
wklejone z tych przebiegów. Sprzątanie plików `work/`, `bin/`, `obj/` przez `rm` było w tej sesji
zablokowane — są one ignorowane przez `code/.gitignore`, a po klonowaniu repo ich nie będzie.
