# Kod do wydania #3 — mTLS w Kestrelu i diagnostyka błędów zaufania

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: `openssl` (sprawdzone na 3.0.2), **.NET 10 SDK** (sprawdzone na 10.0.400).

> **Bezpieczeństwo:** klucze i certyfikaty są wyłącznie demonstracyjne i
> generowane **poza repo** (domyślnie `/tmp/prasowka-mtls-pki`). Nie używajcie
> ich do niczego produkcyjnego. `.gitignore` blokuje `*.key`, `*.pem`, `*.crl`.

## Fragment prasówki, którego dotyczy ten kod

> mTLS to drugi kierunek tej samej weryfikacji: serwer (Kestrel,
> `ClientCertificateMode.RequireCertificate`) wymaga certyfikatu klienta i
> waliduje go względem własnego rootu (`X509ChainTrustMode.CustomRootTrust`) z
> EKU `clientAuth`; klient (`HttpClient`) wysyła swój certyfikat **razem z
> intermediate** (`SslClientAuthenticationOptions.ClientCertificateContext`).
> Typowe awarie: brak certyfikatu klienta (klient widzi tylko `response ended
> prematurely`), zły EKU (`NotValidForUsage`), wygasły (`NotTimeValid`), obcy
> wystawca lub brak intermediate (`PartialChain`), IP poza SAN
> (`RemoteCertificateNameMismatch`). Domyślnie .NET nie sprawdza odwołań
> (`RevocationMode.NoCheck` w naszej polityce), więc odwołany w CRL certyfikat
> klienta przechodzi.

## 1. PKI (`openssl`)

```bash
bash openssl/generate-mtls-pki.sh /tmp/prasowka-mtls-pki
```

Tworzy: root CA → intermediate CA → certyfikat serwera (SAN `localhost` +
`127.0.0.1`, EKU `serverAuth`), serwer bez SAN, klient (`clientAuth`), klient z
błędnym EKU, wygasły, odwołany (plus `inter.crl`) i klient z obcego CA.
Wzorzec konfiguracji: `openssl/ca.cnf` (znacznik `@PKI@` podmieniany `sed`-em).

> Uwaga: w środowisku, w którym powstało wydanie, uruchomienie tego skryptu jako
> całości było zablokowane, więc **skrypt nie był uruchomiony w całości**;
> identyczne komendy `openssl` (z `ca.cnf` po podstawieniu ścieżki) wykonano
> ręcznie, jedna po drugiej. Jeśli skrypt coś zgłosi, porównajcie z komendami z
> artykułu.

Diagnostyka (przykłady, pełny output w artykule):

```bash
openssl verify -CAfile root.pem -untrusted intermediate.pem -purpose sslclient client-wrongeku.pem
openssl verify -CAfile root.pem -untrusted intermediate.pem -purpose sslclient -crl_check -CRLfile inter.crl client-revoked.pem
openssl s_client -connect 127.0.0.1:18443 -servername localhost -CAfile root.pem \
  -cert client.pem -key client.key -cert_chain intermediate.pem -verify_hostname localhost -verify_return_error -brief
```

## 2. .NET (`dotnet/MtlsDemo`)

Cały zestaw scenariuszy (serwer Kestrel na `127.0.0.1:18443` startuje i kończy
się w procesie):

```bash
dotnet run --project dotnet/MtlsDemo -- demo /tmp/prasowka-mtls-pki
```

Tryby ręczne (serwer w jednym terminalu, klient/`openssl s_client` w drugim):

```bash
# serve [pki] [port] [server|server-nosan] [full|leaf-only] [eku|no-eku] [debug]
dotnet run --project dotnet/MtlsDemo -- serve /tmp/prasowka-mtls-pki 18443 server full eku debug
# call [pki] [port] [nazwa-certu|none] [host]
dotnet run --project dotnet/MtlsDemo -- call /tmp/prasowka-mtls-pki 18443 client localhost
```

Serwer zatrzymajcie `Ctrl+C`. Oczekiwany output `demo`: patrz sekcje 4-5
artykułu (sprawdzone na .NET SDK 10.0.400; `dotnet build`: `0 Warning(s)`,
`0 Error(s)`).

Kod ładuje klucz przez `X509Certificate2.CreateFromPemFile` — na Windowsie
klucze efemeryczne bywają problematyczne dla SslStream; tam wyeksportujcie do
PFX (niesprawdzone w tym wydaniu).
