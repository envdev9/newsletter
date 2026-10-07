<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #14 — 7 października 2026

![X.509 Name Constraints](https://img.shields.io/badge/X.509_%C2%B7_Name_Constraints_%C2%B7_RFC_5280_4.2.1.10-1E3A5F?style=for-the-badge&logo=letsencrypt&logoColor=white)

## CA z kagańcem: Name Constraints od zera — 26 certyfikatów, dwa weryfikatory i kilka niespodzianek

</div>

---

> _Zaufanie do CA jest wszystko-albo-nic: root, któremu ufasz, może podpisać
> `bank.example.org` tak samo łatwo jak `intranet.corp`. Name Constraints to
> rozszerzenie X.509, w którym CA dostaje listę „tu wolno, tam nie"._

W #1–#13 budowaliśmy PKI, mTLS, odwołania, CT i ACME. Za każdym razem
**podległy CA mógł wystawić certyfikat na dowolną nazwę** — pathlen:0 ograniczał
tylko głębokość łańcucha, nie to, *dla kogo* wolno podpisywać. Dziś zamykamy tę
lukę: rozszerzenie **Name Constraints** (RFC 5280 §4.2.1.10).

**Dlaczego to ważne dla .NET deva?** Bo to rozszerzenie, które pozwala
bezpiecznie powiedzieć „ufam temu firmowemu intermediate, ale **tylko** dla
`*.corp.example.test`". Przejęty klucz takiego CA nie pozwala sfałszować
zewnętrznych domen. A jednocześnie `X509Chain` z .NET **nie ma żadnej klasy**
dla tego rozszerzenia — trzeba je zakodować ręcznie w DER.

Środowisko: .NET SDK 10.0.400, OpenSSL 3.0.2, Python 3.10.4 + `cryptography`
50.0.1, Linux, bez sieci i bez Dockera. Kod: [`code/`](code/README.md).

| 🧪 Co | ✅ Status |
|---|---|
| Ręczne kodowanie `NameConstraints` w DER (`System.Formats.Asn1`) | działa; parsery `openssl asn1parse`, `openssl x509 -text` i Python `cryptography` odczytały to samo |
| 7 wariantów intermediate, 2 rooty, 26 certyfikatów liści | zbudowane w pamięci, `0 Warning(s), 0 Error(s)` |
| Walidacja każdego liścia: `X509Chain` (.NET) i `openssl verify` | **0 rozbieżności** (ale patrz uwaga o niezależności w sekcji 7) |
| Klucze prywatne na dysku | **żadnych** — na dysk trafiają tylko publiczne `*.pem` |
| Inne stosy TLS (Windows CryptoAPI, macOS, NSS, Go, Java), constraints w prawdziwych CA | **NIE sprawdzone** (sekcja 7) |

---

## 1️⃣ Anatomia rozszerzenia

```
NameConstraints ::= SEQUENCE {
   permittedSubtrees [0] GeneralSubtrees OPTIONAL,
   excludedSubtrees  [1] GeneralSubtrees OPTIONAL }
GeneralSubtree  ::= SEQUENCE { base GeneralName, minimum [0] DEFAULT 0, maximum [1] OPTIONAL }
```

Dwie listy: **permitted** (jeśli jest — nazwa danego typu MUSI się w którymś
poddrzewie mieścić) i **excluded** (nazwa NIE może się w żadnym mieścić;
excluded wygrywa z permitted). Typy nazw: `dNSName` `[2]`, `rfc822Name` `[1]`,
`iPAddress` `[7]` (adres + maska, 8 bajtów dla IPv4), URI, directoryName.

W .NET kodujemy to na `AsnWriter` — tagi `[0]`/`[1]` to konstruowane tagi
kontekstowe z IMPLICIT, a nazwy to prymitywne IA5String z tagiem kontekstowym:

```csharp
using (w.PushSequence(new Asn1Tag(TagClass.ContextSpecific, tagNo)))  // [0] permitted / [1] excluded
{
    foreach (var d in s.Dns)
        using (w.PushSequence())
            w.WriteCharacterString(UniversalTagNumber.IA5String, d, new Asn1Tag(TagClass.ContextSpecific, 2));
    ...
}
req.CertificateExtensions.Add(new X509Extension(new Oid("2.5.29.30"), der, critical: true));
```

Wynik zmierzony `openssl x509 -text` na intermediate „A”:

```
X509v3 Name Constraints: critical
    Permitted:
      DNS:.corp.example.test
      email:corp.example.test
      IP:192.0.2.0/255.255.255.0
    Excluded:
      DNS:secret.corp.example.test
```

A tak ten sam blob widzi `openssl asn1parse -strparse` (dowód, że tagi
`[0]`, `[2]`, `[1]`, `[7]`, `[1]` stoją tam, gdzie powinny) — i niezależny parser
w Pythonie:

```
critical= True
permitted= [DNSName('.corp.example.test'), RFC822Name('corp.example.test'), IPAddress(192.0.2.0/24)]
excluded= [DNSName('secret.corp.example.test')]
```

---

## 2️⃣ Plan eksperymentu

Siedem intermediate pod jednym rootem (plus drugi root z constraints), każdy z
innym wariantem; każdy z 26 liści walidowany **dwa razy**: `X509Chain` z
`CustomRootTrust` i `RevocationMode.NoCheck`, oraz `openssl verify -CAfile -untrusted`.
Kolumna „oczek.” to **moja predykcja przed uruchomieniem** (`?` = nie byłem pewien).

| Intermediate | Constraints |
|---|---|
| A | permit DNS `.corp.example.test`, email `corp.example.test`, IP `192.0.2.0/24`; exclude DNS `secret.corp.example.test`; critical |
| B | jak A, ale rozszerzenie **NIE** krytyczne |
| C | permit DNS `corp.example.test` (bez kropki) |
| D | tylko exclude `example.org` |
| E | permit tylko DNS (brak ograniczeń IP) |
| N | kontrola: brak constraints |
| R | brak constraints, ale constraints siedzą na **roocie** |

---

## 3️⃣ Wynik — realny output (skrócony o puste wiersze „powodu”)

```
id   oczek. dotnet openssl opis
A1   OK     OK     OK      SAN ok.corp.example.test
A2   FAIL   FAIL   FAIL    SAN evil.example.org
                          .NET: HasNotPermittedNameConstraint | openssl: 47@0 permitted subtree violation
A3   FAIL   FAIL   FAIL    SAN secret.corp.example.test (excluded)
                          .NET: HasExcludedNameConstraint | openssl: 48@0 excluded subtree violation
A4   FAIL   FAIL   FAIL    SAN a.secret.corp.example.test (pod-domena excl)
A5   FAIL   FAIL   FAIL    2 SAN: ok.corp... + evil.example.org
A6   FAIL   FAIL   FAIL    SAN corp.example.test (apex vs '.corp...')
A7   OK     OK     OK      SAN *.corp.example.test (wildcard)
A8   FAIL   FAIL   FAIL    SAN *.example.test (wildcard szerszy)
A9   OK     OK     OK      SAN OK.CORP.EXAMPLE.TEST (wielkie litery)
A10  OK     OK     OK      SAN dns ok + IP 192.0.2.5 (w puli)
A11  FAIL   FAIL   FAIL    SAN dns ok + IP 198.51.100.7 (poza pula)
A12  FAIL   FAIL   FAIL    BRAK SAN, CN=evil.example.org
A13  OK     OK     OK      SAN ok.corp... + CN=evil.example.org
A14  OK     OK     OK      SAN email alice@corp.example.test
A15  FAIL   FAIL   FAIL    SAN email bob@evil.example.org
A16  OK?    OK     OK      SAN URI https://evil.example.org/ (brak constraint na URI)
B1   FAIL?  FAIL   FAIL    constraints NON-critical, SAN evil.example.org
C1   OK     OK     OK      permit 'corp.example.test', SAN corp.example.test
C2   OK     OK     OK      permit 'corp.example.test', SAN ok.corp.example.test
C3   FAIL   FAIL   FAIL    permit 'corp.example.test', SAN notcorp.example.test
D1   OK     OK     OK      tylko excluded example.org, SAN foo.example.test
D2   FAIL   FAIL   FAIL    tylko excluded example.org, SAN foo.example.org
E1   OK     OK     OK      constraint tylko DNS, leaf z SAN tylko-IP 203.0.113.9
N1   OK     OK     OK      intermediate BEZ constraints, SAN evil.example.org
R1   FAIL?  FAIL   FAIL    constraints na ROOCIE (trust anchor), SAN evil.example.org
R2   OK     OK     OK      constraints na ROOCIE, SAN ok.corp.example.test
rozbieznosci .NET vs openssl: 0
```

Wszystkie moje predykcje się sprawdziły (także te z `?`). Kody OpenSSL:
`47 permitted subtree violation` i `48 excluded subtree violation`; w .NET
`X509ChainStatusFlags.HasNotPermittedNameConstraint` / `HasExcludedNameConstraint`.
Błąd jest zawsze na `depth 0` — czyli **liść jest odrzucany, nie CA**.

---

## 4️⃣ Haczyki — to, co naprawdę trzeba wiedzieć

### 🪤 Haczyk 1: `.corp.example.test` ≠ `corp.example.test`

| Constraint | `corp.example.test` | `ok.corp.example.test` | `notcorp.example.test` |
|---|---|---|---|
| `.corp.example.test` (z kropką) — A | **FAIL** (A6) | OK | FAIL |
| `corp.example.test` (bez kropki) — C | OK (C1) | OK (C2) | FAIL (C3) |

Z kropką = tylko poddomeny, bez samej domeny. Bez kropki = domena i jej
poddomeny, ale **nie** `notcorp.example.test` (granica etykiet, nie sufiks
tekstowy). Jeśli chcesz pokryć także apex, użyj zapisu bez kropki. To
zmierzone na OpenSSL 3.0.2 (i .NET jadącym na nim, patrz sekcja 7); inne stosy
mogą interpretować zapis z kropką inaczej — **tego nie sprawdzałem**.

### 🪤 Haczyk 2: wszystkie nazwy są sprawdzane, nie „pierwsza” (A5)

Leaf z `SAN: ok.corp.example.test, evil.example.org` pada. Jedna nazwa poza
zakresem zabija cały certyfikat — dobrze, bo inaczej wystarczyłoby dopisać
legalną nazwę „dla przykrywki”.

### 🪤 Haczyk 3: CN bywa nazwą — dopóki nie ma SAN (A12 vs A13)

- A12: **brak SAN**, `CN=evil.example.org` → odrzucony. Zarówno OpenSSL jak i
  .NET traktują CN jako nazwę DNS do sprawdzenia constraints, gdy SAN nie
  ma. To zamyka znaną lukę: bez tego „stary” certyfikat bez SAN omijałby
  ograniczenia.
- A13: SAN zawiera nazwę z puli, `CN=evil.example.org` → **łańcuch przechodzi**.
  Constraints nie sprawdzają CN, gdy SAN istnieje. To nie dziura: dopasowanie
  nazwy hosta też ignoruje wtedy CN. Zmierzone:

```
$ openssl verify -CAfile root-plain.pem -untrusted inter-A.pem -verify_hostname evil.example.org leaf-A13.pem
CN = evil.example.org
error 62 at 0 depth lookup: hostname mismatch
```

Łańcuch jest zaakceptowany, ale `evil.example.org` jako host — nie. Pamiętaj:
**walidacja łańcucha i walidacja nazwy hosta to dwa osobne kroki** (w .NET:
`X509Chain.Build` nie sprawdza hosta; robi to `SslStream`/`SslPolicyErrors`).

### 🪤 Haczyk 4: constraint działa tylko na typy, które wymienia (A16, E1)

- A16: URI `https://evil.example.org/` w SAN przechodzi, bo żaden constraint
  nie dotyczy URI. 
- E1: intermediate z ograniczeniem tylko DNS **nie ogranicza** IP — leaf z
  SAN-em `203.0.113.9` przechodzi.

Wniosek projektowy: jeśli chcesz zamknąć CA w korporacyjnej przestrzeni, musisz
**jawnie** wymienić każdy typ nazw, jaki może się pojawić (DNS, IP, email, URI) —
albo zabronić pozostałych przez excluded (w RFC pełny zakaz typu zapisuje się
pustym poddrzewem, np. `0.0.0.0/0`; tego wariantu nie testowałem).

### 🪤 Haczyk 5: critical vs non-critical (B1)

RFC 5280 mówi, że CA **MUSI** oznaczyć to rozszerzenie jako krytyczne.
Eksperyment B1: wersja **niekrytyczna** i tak została wyegzekwowana — i przez
OpenSSL, i przez .NET (`HasNotPermittedNameConstraint`). Na tym stosie
oznaczenie `critical` nie decyduje o egzekwowaniu. Ale **klient, który nie
rozumie rozszerzenia**, może je zignorować dokładnie wtedy, gdy nie jest
krytyczne (to cały sens flagi `critical`) — takich klientów nie testowałem.
Zawsze wystawiaj z `critical: true`.

### 🪤 Haczyk 6: constraints na trust anchorze (R1/R2)

Constraints umieszczone na **roocie** (certyfikat zaufania) też zostały
wyegzekwowane (R1 FAIL) zarówno przez OpenSSL, jak i .NET, mimo że
intermediate pod nim nie miał żadnych (R). Uwaga: to zachowanie *tego* stosu;
inne implementacje różnie traktują rozszerzenia kotwicy zaufania (z wiedzy
ogólnej — niezmierzone tutaj).

### 🪤 Haczyk 7: constraint nie chroni przed samym sobą

N1 jest kontrolą: ten sam leaf `evil.example.org` pod intermediate **bez**
constraints przechodzi, mimo że root jest ten sam co w A. Ograniczenie działa
tylko w gałęzi, w której leży certyfikat z rozszerzeniem — **każdy
intermediate trzeba ograniczyć osobno** (albo ograniczyć root, patrz R).

---

## 5️⃣ Co z tego dla .NET

- `X509Chain` z Linuxa zwraca konkretne flagi statusu (`HasNotPermittedNameConstraint`,
  `HasExcludedNameConstraint`; w enumie są też `HasNotSupportedNameConstraint`,
  `HasNotDefinedNameConstraint`, `InvalidNameConstraints` — tych nie
  wywołałem). Loguj `ChainStatus`, nie samo `Build() == false`.
- .NET **nie ma** typu dla tego rozszerzenia — do wystawiania: `X509Extension`
  z surowym DER (OID `2.5.29.30`); do odczytu: `System.Formats.Asn1`.
- Pomysł na wdrożenie: wewnętrzne CA (np. dla `*.corp.internal`) podpisz
  intermediate z `permitted` na swoją strefę. Wtedy zainstalowanie roota firmowego
  na stacjach nie daje temu CA mocy fałszowania `google.com`. (Z wiedzy ogólnej:
  tak właśnie skłania się do tego praktyka dla prywatnych CA; w tym wydaniu
  nie sprawdzałem żadnego realnego wdrożenia.)

---

## 6️⃣ Ściągawka

| Pojęcie | Jedno zdanie |
|---|---|
| OID | `2.5.29.30` (`id-ce-nameConstraints`) |
| permitted/excluded | excluded wygrywa; permitted, jeśli istnieje dla danego typu, jest „białą listą” |
| `.x.test` vs `x.test` | z kropką: tylko poddomeny; bez: domena + poddomeny (OpenSSL 3.0.2) |
| Granica etykiet | `notcorp.example.test` nie pasuje do `corp.example.test` |
| Typ bez constraints | nie jest ograniczany (URI, IP przy samym DNS) |
| CN | sprawdzany jako DNS tylko gdy brak SAN |
| Krytyczność | RFC: MUSI być critical; stos OpenSSL egzekwuje też niekrytyczne |
| Łańcuch ≠ host | Name Constraints ≠ dopasowanie nazwy hosta |

---

## 7️⃣ Czego NIE zweryfikowałem (wprost)

- **Niezależność weryfikatorów jest ograniczona.** .NET na Linuksie liczy
  łańcuchy przez systemowy OpenSSL (z wiedzy o implementacji; nie sprawdzałem
  linkowania na tej maszynie). Dlatego „0 rozbieżności .NET vs openssl”
  oznacza głównie **spójność mapowania statusów**, a nie dwie niezależne
  implementacje algorytmu. Prawdziwie niezależne stosy (Windows CryptoAPI,
  macOS Security.framework, Go `crypto/x509`, Java PKIX, NSS/Firefox,
  BoringSSL/Chrome) — **niesprawdzone**.
- Różnice w interpretacji zapisu z kropką, CN fallback, krytyczności i
  constraints na kotwicy — dotyczą **tylko OpenSSL 3.0.2 / .NET 10.0.400 na Linuksie**.
- Typy `directoryName`, `uriName`, `otherName`; pola `minimum`/`maximum`
  (RFC zabrania ich użycia poza 0/brak); IPv6; nazwy IDN/punycode; puste
  poddrzewo jako zakaz typu — **nie testowane**.
- Constraints w łańcuchu 3+ CA (zagnieżdżone) — nie testowane; tylko root → intermediate → leaf.
- **Prawdziwy handshake TLS** — celowo brak: nie zapisujemy kluczy prywatnych,
  więc nie ma czym podpisać handshake'u. `SslStream`/Kestrel z takim łańcuchem
  — niesprawdzone.
- Publiczne CA i realne wdrożenia constraints (np. w Web PKI) — wiedza ogólna, niezmierzona.
- Windows/macOS — wyłącznie Linux.

## 📎 Co dalej w tej rubryce

`consistency proof` (RFC 6962 §2.1.2) między dwoma STH, Must-Staple + SCT,
weryfikacja SCT w `SslStream`/Kestrelu, CAA/DANE, Windows/macOS store,
`pebble` lokalnie, a także **drugi, niezależny weryfikator** (Go/Java, gdy będą
dostępne) do porównania z wynikami z dzisiaj.

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #14 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
