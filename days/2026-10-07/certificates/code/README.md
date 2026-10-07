# Kod do wydania #14 — Name Constraints (RFC 5280 §4.2.1.10): CA z kagańcem

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (sprawdzone na 10.0.400), `openssl` (sprawdzone na 3.0.2), Linux.
Opcjonalnie Python 3 + `cryptography` (sprawdzone: 3.10.4 / 50.0.1) jako niezależny parser rozszerzenia.
**Bez sieci i bez Dockera.**

> **Bezpieczeństwo:** program buduje całe PKI (dwa rooty, siedem intermediate, 26 liści; ECDSA P-256) **w pamięci**.
> Na dysk (`work/`, ignorowane przez git) trafiają **wyłącznie certyfikaty publiczne** `*.pem`.
> **Żaden klucz prywatny nie jest nigdzie zapisywany**, więc nie ma czego wyciec — ale też nie da się
> z tych certów postawić handshake'u TLS (to eksperyment o walidacji łańcucha, nie o transporcie).
> Domeny to `*.example.test` / `example.org`, adresy IP to zakresy dokumentacyjne (RFC 5737).

## Fragment prasówki, którego dotyczy ten kod

> Name Constraints to rozszerzenie X.509, które pozwala **ograniczyć, dla jakich nazw podległy CA może
> wystawiać certyfikaty** — firmowy intermediate dostaje „tylko `*.corp.example.test`" i nawet jego pełne
> przejęcie nie pozwala sfałszować `bank.example.org`. Kodujemy rozszerzenie ręcznie w DER (`.NET` nie ma
> dla niego klasy), budujemy 7 intermediate z różnymi wariantami i walidujemy 26 certyfikatów liści **dwoma
> weryfikatorami naraz** (`X509Chain` i `openssl verify`), porównując odpowiedzi.

## Struktura

```
code/
├── dotnet/NameConstraintsLab/   # Program.cs + csproj: PKI w pamięci, DER NameConstraints, 26 przypadków
└── work/                        # generowane (gitignored): root-*.pem, inter-*.pem, leaf-*.pem (tylko publiczne)
```

## Uruchomienie (każde polecenie osobno, z katalogu `code/`)

```bash
dotnet build dotnet/NameConstraintsLab/NameConstraintsLab.csproj -c Release
dotnet run --no-build -c Release --project dotnet/NameConstraintsLab -- work
```

Program wypisuje tabelę `id | oczekiwane | .NET | openssl | opis` (+ powód odrzucenia) i liczbę
rozbieżności `.NET` vs `openssl` (u nas: `0`). Potem inspekcja niezależnymi narzędziami:

```bash
openssl x509 -noout -text -in work/inter-A.pem
openssl asn1parse -in work/inter-A.pem
openssl asn1parse -in work/inter-A.pem -strparse 269     # offset 269 z poprzedniego wyjścia = treść rozszerzenia
openssl verify -CAfile work/root-plain.pem -untrusted work/inter-A.pem -verify_hostname evil.example.org work/leaf-A13.pem
```

```bash
python3 -c "import sys; from cryptography import x509; c=x509.load_pem_x509_certificate(open(sys.argv[1],'rb').read()); e=c.extensions.get_extension_for_class(x509.NameConstraints); print(e.critical, e.value.permitted_subtrees, e.value.excluded_subtrees)" work/inter-A.pem
```

Uwaga: offset `269` zależy od długości certyfikatu — jeśli zmienisz nazwy w `Program.cs`, odczytaj nowy
offset z pełnego `asn1parse` (wiersz `X509v3 Name Constraints` → następny `OCTET STRING`).

## Warianty intermediate

| Litera | Constraints |
|---|---|
| `A` | permit DNS `.corp.example.test`, email `corp.example.test`, IP `192.0.2.0/24`; exclude DNS `secret.corp.example.test`; **critical** |
| `B` | jak `A`, ale rozszerzenie **NIE** krytyczne |
| `C` | permit DNS `corp.example.test` (bez kropki) |
| `D` | tylko exclude DNS `example.org` |
| `E` | permit tylko DNS `.corp.example.test` (bez żadnego ograniczenia IP) |
| `N` | brak Name Constraints (kontrola) |
| `R` | brak constraints, ale **root** (trust anchor) ma permit `.corp.example.test` |

## Uwaga o środowisku

Żadnych skryptów `.sh` — komendy wykonywane pojedynczo. Przy pierwszym uruchomieniu CN-y z nawiasami
zostały odrzucone przez `X500DistinguishedName` (poprawione na proste nazwy `NC Sub CA A`…).
