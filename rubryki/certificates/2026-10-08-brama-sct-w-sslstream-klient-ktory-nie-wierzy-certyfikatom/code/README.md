# Kod do wydania #15 — Brama SCT w `SslStream`: klient, który nie wierzy certyfikatom bez dowodu z logu CT

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (sprawdzone na 10.0.400), `openssl` (sprawdzone na 3.0.2), Linux.
Opcjonalnie Python 3 + `cryptography` jako niezależny weryfikator SCT.
**Bez sieci zewnętrznej i bez Dockera** — handshake TLS idzie po loopbacku w jednym procesie.

> **Bezpieczeństwo:** wszystkie klucze (2 rooty, 3 "logi CT", klucze liści; ECDSA P-256) żyją **wyłącznie w pamięci**
> procesu. Na dysk (`work/`, ignorowane przez git) trafiają tylko certyfikaty i klucze **publiczne** `*.pem`.
> Domena: `srv.example.test`. Żadnych sekretów ani adresów zewnętrznych.

## Fragment prasówki, którego dotyczy ten kod

> `RemoteCertificateValidationCallback` to jedyne miejsce, w którym możesz w .NET dopisać własną politykę zaufania.
> Budujemy w nim "bramę SCT": własny łańcuch (`CustomRootTrust`), sprawdzenie nazwy, a potem rozbiór rozszerzenia
> Embedded SCT, rekonstrukcja TBS precertu i weryfikacja podpisu każdego SCT kluczem zaufanego logu — to wszystko
> przepuszczone przez **prawdziwe handshake'i TLS 1.3** (`SslStream` klient ↔ serwer) w 16 scenariuszach.

## Struktura

```
code/
├── dotnet/SctGate/     # Program.cs + csproj: PKI + 3 logi CT w pamięci, 16 handshake'ów SslStream
├── verify_sct.py       # niezależna weryfikacja SCT (Python cryptography) na plikach PEM z work/
└── work/               # generowane (gitignored): root.pem, log*-pub.pem, leaf-S*.pem (tylko publiczne)
```

## Uruchomienie (każde polecenie osobno, z katalogu `code/`)

```bash
dotnet build dotnet/SctGate/SctGate.csproj -c Release
dotnet run --no-build -c Release --project dotnet/SctGate -- work
```

Program wypisuje dla każdego scenariusza: oczekiwanie, wynik, powód odrzucenia przez bramę oraz komunikat klienta
i serwera; na końcu `rozbieznosci oczekiwania vs wynik: 0` (kod wyjścia 0). Certyfikaty są losowe
(serial, klucze), więc identyfikatory logów i serial różnią się między uruchomieniami.

Kontrola niezależnymi narzędziami (po uruchomieniu programu):

```bash
openssl verify -CAfile work/root.pem -verify_hostname srv.example.test work/leaf-S2.pem
openssl x509 -noout -text -certopt no_pubkey,no_sigdump -in work/leaf-S2.pem
python3 verify_sct.py work/leaf-S8.pem work/root.pem work/log1-pub.pem work/log2-pub.pem
python3 verify_sct.py work/leaf-S5.pem work/root.pem work/log1-pub.pem
python3 verify_sct.py work/leaf-S7.pem work/root.pem work/log1-pub.pem
```

Oczekiwane: S8 — dwa razy `podpis OK`; S5 (zepsuty bit) i S7 (SCT przeniesiony) — `podpis NIEPOPRAWNY`.

## Scenariusze

| Id | Co | Wynik |
|---|---|---|
| S0 | brak callbacka | REJECT (`PartialChain`) |
| S1 | naiwny callback (łańcuch + nazwa), cert bez SCT | **ACCEPT** (dziura) |
| S2 | brama min=1, 1 ważny SCT | ACCEPT |
| S3 | brama min=1, brak SCT | REJECT |
| S4 | SCT od nieznanego logu | REJECT |
| S5 | SCT z odwróconym bitem podpisu | REJECT |
| S6 | SCT podpisany poprawnie, timestamp +1 dzień | REJECT |
| S7 | SCT przeniesiony do certu o innym SAN | REJECT |
| S8 | min=2, SCT z log1 + log2 | ACCEPT |
| S9 | min=2, jeden SCT | REJECT |
| S10 | min=2, dwa SCT z tego samego logu | REJECT |
| S11 | min=1, SCT-śmieć + ważny SCT | ACCEPT |
| S12 | ważny SCT, zły `TargetHost` | REJECT |
| S13 | ważny SCT, cert z obcego roota | REJECT |
| S14 | SCT podpisany dla złego `issuer_key_hash` | REJECT |
| S15 | obcięta lista SCT (malformed) | REJECT |

## Uwaga o środowisku

Żadnych skryptów `.sh` — komendy wykonywane pojedynczo. W środowisku, w którym powstało wydanie, `python3 -c` było
blokowane, dlatego weryfikator Pythona jest plikiem `verify_sct.py`.
