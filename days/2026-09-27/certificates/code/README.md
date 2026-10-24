# Kod do wydania #4 — odwołania (CRL/OCSP), stapling, TLS 1.3, X509Store, rotacja, pinning

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: `openssl` (sprawdzone na 3.0.2), **.NET 10 SDK** (sprawdzone na 10.0.400), Linux.

> **Bezpieczeństwo:** klucze i certyfikaty są wyłącznie **DEMO** i powstają w
> `code/work/` (ignorowane przez git: `*.key`, `*.pem`, `*.crl`, `work/`). Program .NET
> przekierowuje `HOME` do `work/home`, więc cache CRL i magazyn `CurrentUser\PrasowkaDemo`
> nie dotykają Twojego profilu ani magazynu systemowego. Responder `openssl ocsp -port`
> (3.0.2) nasłuchuje na wszystkich interfejsach — uruchamiaj tylko na czas prób.

## Fragment prasówki, którego dotyczy ten kod

> Włączone `X509RevocationMode.Online` pobiera CRL z adresu w CDP i cache'uje go na
> dysku; `Offline` nic nie pobiera, tylko czyta cache (pusty = `RevocationStatusUnknown`,
> `Build` = `false`); martwy CDP to "nie wiem", nie "dobry". W naszym układzie (cert z CDP
> **i** AIA) .NET nie odpytał responderu OCSP. Stapling działa w `openssl s_server/s_client`,
> a TLS 1.3 w `-trace` pokazuje zaszyfrowane `Certificate`. Rotacja bez restartu: Kestrel
> `ServerCertificateSelector` + `X509Store`; pinning SPKI przetrwa odnowienie na tym samym
> kluczu, ale nie zmianę klucza bez pinu zapasowego.

## 1. PKI (`openssl`)

```bash
bash openssl/setup-pki.sh          # -> code/work/
```

> Uwaga: w środowisku, w którym powstało wydanie, uruchomienie tego skryptu jako całości
> było odrzucone, więc **skrypt nie był uruchomiony w całości**; identyczne komendy
> `openssl` wykonano ręcznie (z `openssl/ca.cnf` po podstawieniu ścieżki `@PKI@`).
> Numery seriali w artykule (2000-2005) pochodzą z tego ręcznego przebiegu; skrypt
> zaczyna oba CA od 1000.

Powstają: root → issuing CA → `srv-good`, `srv-revoked` (odwołany), `srv-deadcdp` (CDP na
martwym porcie), `srv-renewed-samekey`, `srv-rekeyed`, `ocsp`, `inter.crl`, `inter-stale.crl`.

## 2. OCSP i stapling (`openssl`)

```bash
# terminal 1: responder
openssl ocsp -index work/inter/index.txt -port 18481 -rsigner work/ocsp.pem -rkey work/ocsp.key -CA work/inter/ca.pem -text -ndays 1
# terminal 2: zapytanie
openssl ocsp -issuer work/inter/ca.pem -cert work/srv-good.pem -cert work/srv-revoked.pem \
  -url http://127.0.0.1:18481 -CAfile work/root/ca.pem -VAfile work/ocsp.pem
# odpowiedź do staplingu
openssl ocsp -issuer work/inter/ca.pem -cert work/srv-good.pem -url http://127.0.0.1:18481 \
  -CAfile work/root/ca.pem -respout work/srv-good.ocsp
# stapling + TLS 1.3 (terminal 1, potem 2)
openssl s_server -accept 18482 -cert work/srv-good.pem -key work/srv-good.key -cert_chain work/inter/ca.pem \
  -status_file work/srv-good.ocsp -tls1_3 -www
openssl s_client -connect 127.0.0.1:18482 -servername localhost -tls1_3 -status -CAfile work/root/ca.pem \
  -verify_hostname localhost -verify_return_error < /dev/null
openssl s_client -connect 127.0.0.1:18482 -servername localhost -tls1_3 -trace -CAfile work/root/ca.pem < /dev/null
```

`s_client` bez `< /dev/null` czeka na stdin i nie kończy się sam.

## 3. .NET (`dotnet/RevLab`)

```bash
# macierz RevocationMode x certyfikat; serwer CDP (HTTP :18480) startuje w procesie
dotnet run --project dotnet/RevLab -- revocation work
# ten sam eksperyment z przeterminowanym CRL
dotnet run --project dotnet/RevLab -- revocation work work/inter-stale.crl
# X509Store + rotacja bez restartu + pinning SPKI (Kestrel na :18490)
dotnet run --project dotnet/RevLab -- pinning work
```

Oczekiwany output: sekcje 2, 6 i 7 artykułu (sprawdzone na .NET SDK 10.0.400;
`dotnet build`: `0 Error(s)`). Czasy w ms będą się różnić.

Kod ładuje klucz przez `X509Certificate2.CreateFromPemFile` i utrwala go w magazynie
przez eksport/import PFX; na Windowsie/macOS magazyny działają inaczej — niesprawdzone.
