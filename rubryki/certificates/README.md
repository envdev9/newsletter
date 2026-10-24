<div align="center">

# 🔐 Certyfikaty i TLS (X.509)

### TECH PRASÓWKA — wszystkie artykuły rubryki, najnowsze na górze

</div>

---

Każdy artykuł to osobny folder `<data>-<tytuł>/` z `ARTICLE.md` i pełnym, uruchamialnym
kodem w `code/`. Kolejne artykuły podnoszą poziom — postęp rubryki jest w
[`STATE.md`](../../STATE.md).

| Data | Artykuł | W skrócie | Kod |
|------|---------|-----------|-----|
| 2026-10-15 | [Dowód spójności logu CT: jak monitor łapie log, który pokazuje dwie historie](2026-10-15-dowod-spojnosci-logu-ct-jak-monitor-lapie-log-ktory/ARTICLE.md) | Dowód spójności logu Certificate Transparency (RFC 6962/9162) w C#: 4656/4656 par (m,n) OK, 632 692 mutacji dowodu — 0 przyjętych, a split-view wykryty, mimo że oba podpisane STH są poprawne. | [Kod](2026-10-15-dowod-spojnosci-logu-ct-jak-monitor-lapie-log-ktory/code/) |
| 2026-10-08 | [Brama SCT w `SslStream`: klient, który nie wierzy certyfikatom bez dowodu z logu CT](2026-10-08-brama-sct-w-sslstream-klient-ktory-nie-wierzy-certyfikatom/ARTICLE.md) | `SslStream` sam z siebie w ogóle nie sprawdza SCT — polityka Certificate Transparency musi siedzieć w callbacku, a jedno `return true` kasuje całe zabezpieczenie; 16 realnych handshake'ów TLS 1.3 to udowadnia. | [Kod](2026-10-08-brama-sct-w-sslstream-klient-ktory-nie-wierzy-certyfikatom/code/) |
| 2026-10-07 | [CA z kagańcem: Name Constraints od zera — 26 certyfikatów, dwa weryfikatory i kilka niespodzianek](2026-10-07-ca-z-kagancem-name-constraints-od-zera-26-certyfikatow-dwa/ARTICLE.md) | CA z kagańcem: Name Constraints od zera — 26 certyfikatów, dwa weryfikatory (.NET i openssl) i siedem haczyków, o których dokumentacja milczy. | [Kod](2026-10-07-ca-z-kagancem-name-constraints-od-zera-26-certyfikatow-dwa/code/) |
| 2026-10-06 | [ACME od zera: własny serwer w Pythonie, własny klient w .NET, challenge http-01 — i siedem sposobów, żeby go zepsuć](2026-10-06-acme-od-zera-wlasny-serwer-w-pythonie-wlasny-klient-w-net/ARTICLE.md) | ACME (RFC 8555) od zera: własny serwer i klient .NET z challenge http-01 — podpis ECDSA w DER (71 B) zamiast `r‖s` (64 B) i serwer odpowiada `malformed`, a pierwszy `badNonce` to normalna część protokołu. | [Kod](2026-10-06-acme-od-zera-wlasny-serwer-w-pythonie-wlasny-klient-w-net/code/) |
| 2026-09-29 | [Certificate Transparency od zera: piszemy własny log CT (Merkle tree, SCT, precert poison) i łamiemy go w .NET](2026-09-29-certificate-transparency-od-zera-piszemy-wlasny-log-ct/ARTICLE.md) | Certificate Transparency od zera: własny precertyfikat z rozszerzeniem poison, ręcznie liczony hash liścia drzewa Merkle i podpisany SCT — a potem dowód, że wklejenie cudzego SCT do innego certyfikatu natychmiast się wysypuje. | [Kod](2026-09-29-certificate-transparency-od-zera-piszemy-wlasny-log-ct/code/) |
| 2026-09-27 | [Certyfikat odwołany, a mimo to działa: CRL, OCSP, stapling, rotacja i pinning SPKI — co naprawdę robi .NET](2026-09-27-certyfikat-odwolany-a-mimo-to-dziala-crl-ocsp-stapling/ARTICLE.md) | Odwołany certyfikat nadal działa? Mierzymy CRL/OCSP w .NET, stapling i handshake TLS 1.3 na bajtach, rotację certu w Kestrelu bez restartu i pinning SPKI — z prawdziwym outputem. | [Kod](2026-09-27-certyfikat-odwolany-a-mimo-to-dziala-crl-ocsp-stapling/code/) |
| 2026-09-26 | [mTLS w Kestrelu: gdy serwer też chce zobaczyć dowód tożsamości klienta — i sześć sposobów, na jakie to się psuje](2026-09-26-mtls-w-kestrelu-gdy-serwer-tez-chce-zobaczyc-dowod/ARTICLE.md) | Odwołany certyfikat dostaje w .NET `HTTP 200`, jeśli nie włączysz sprawdzania — mTLS w Kestrelu z własnym PKI i katalog błędów zaufania z prawdziwymi komunikatami `dotnet` i `openssl`. | [Kod](2026-09-26-mtls-w-kestrelu-gdy-serwer-tez-chce-zobaczyc-dowod/code/) |
| 2026-09-24 | [Certyfikaty od zera: dlaczego przeglądarka ufa jednemu kluczowi, a drugiemu nie](2026-09-24-certyfikaty-od-zera-dlaczego-przegladarka-ufa-jednemu/ARTICLE.md) | Własne CA przez `openssl`, i .NET który poprawnie odrzuca self-signed certyfikat jako | [Kod](2026-09-24-certyfikaty-od-zera-dlaczego-przegladarka-ufa-jednemu/code/) |
<!-- kolejne wiersze dopisywane automatycznie, najnowsze na górze -->

---

<div align="center">

[← spis rubryk](../../README.md)

</div>
