<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #22 — 15 października 2026

![CT consistency](https://img.shields.io/badge/CT_%C2%B7_consistency_proof_%C2%B7_RFC_6962_%C2%A72.1.2_%C2%B7_gossip-5B2C83?style=for-the-badge&logo=letsencrypt&logoColor=white)

## Dowód spójności logu CT: jak monitor łapie log, który pokazuje dwie historie

</div>

---

> _W #6 zbudowaliśmy log CT i dowód inkluzji („ten certyfikat jest w drzewie"),
> w #15 egzekwowaliśmy SCT w `SslStream`. Został kawałek, który czyni log
> **append-only**: skąd wiem, że drzewo, które widzę dziś, jest rozszerzeniem
> tego, które widziałem tydzień temu — i że nikt nie pokazuje mi innej
> historii niż sąsiadowi?_

**Dlaczego to ważne dla .NET deva?** Bo podpis na STH (Signed Tree Head) mówi
tylko „log powiedział to". Log, który **równolegle podpisuje dwa różne drzewa**
tej samej wielkości (jedno bez certyfikatu, który ma zostać ukryty), przechodzi
każdą kontrolę podpisu i każdy dowód inkluzji **względem swojego widoku**.
Przed tym chroni wyłącznie dowód spójności + porównywanie STH między
obserwatorami. Jeśli kiedyś piszesz monitor CT, klienta rejestru przejrzystości
(np. własny log w firmie, Sigstore-owy Rekor, Go sumdb działają na tej samej
matematyce — z wiedzy ogólnej, nie testowane tu) albo po prostu kod, który ufa
„podpisanemu stanowi append-only", ta funkcja jest sercem zaufania.

Środowisko: .NET SDK 10.0.400, OpenSSL 3.0.2, Python 3 (stdlib), Linux,
**bez sieci zewnętrznej i bez Dockera**. Kod: [`code/`](code/README.md).

| 🧪 Co | ✅ Status |
|---|---|
| Dowód spójności (generacja wg RFC 6962 §2.1.2, weryfikacja iteracyjna wg RFC 9162 §2.1.4.2) | działa; `0 Warning(s), 0 Error(s)` |
| Wszystkie pary (m,n), n ≤ 96 (4656 par) | **4656/4656 OK** |
| 632 692 mutacji dowodu (bity, usunięcie, dołożenie, zamiana, zły rozmiar) | **0 przyjętych** |
| Split-view (dwa podpisane drzewa) wykryty dowodem i porównaniem STH | tak |
| Niezależne kontrole: Python (inny algorytm), `openssl dgst -verify` | zgodne |
| Prawdziwy log CT, konsystencja dwóch prawdziwych STH, API `get-sth-consistency` | **NIE sprawdzone** (sekcja 6) |

---

## 1️⃣ Idea w trzech zdaniach

Drzewo Merkle nad `n` liśćmi ma korzeń `MTH(D[n])`. Dowód spójności dla
`m < n` to **najkrótszy zestaw haszy**, z którego da się odtworzyć *jednocześnie*
stary korzeń `MTH(D[m])` i nowy `MTH(D[n])`. Skoro oba korzenie wychodzą z tych
samych haszy, pierwsze `m` liści w nowym drzewie musi być tym samym, co w starym.

Definicja z RFC (rekurencyjna, tak jest w kodzie jako `SubProof`):

```
PROOF(m, D[n]) = SUBPROOF(m, D[n], true)
SUBPROOF(m, D[m], true)  = []
SUBPROOF(m, D[m], false) = [MTH(D[m])]
m < n, k = największa potęga 2 < n:
  m <= k:  SUBPROOF(m, D[0:k], b)     + [MTH(D[k:n])]
  m >  k:  SUBPROOF(m-k, D[k:n], false) + [MTH(D[0:k])]
```

Weryfikator **nie ma liści** — dostaje tylko dwa STH i listę haszy. Dowód 10→25
w naszym uruchomieniu to 5 elementów (160 B), a liści jest 25. Rośnie
logarytmicznie: dla n = 96 najdłuższy dowód ma 8 haszy.

---

## 2️⃣ Realny output (skrócony)

```
== 1. Jeden dowod 10 -> 25, krok po kroku ==
STH(10): root=65646a0b208eb6378978db5284004114...  sig_ok=True
STH(25): root=862f75a674e86fbb7e3b15f37fed6bd1...  sig_ok=True
dowod 10->25: 5 elementow (log2(25) ~ 4.6), zamiast 25 lisci
weryfikacja: OK
rozmiar dowodu: 160 B

== 2. Wyczerpujaco: wszystkie pary (m,n), n<=96, uczciwy log ==
par (m,n): 4656, zweryfikowanych OK: 4656, dowodow pustych (m==n): 96, najdluzszy dowod: 8 elem.
najdluzszy dowod dla wybranych n: n=2:1, n=8:4, n=9:5, n=16:5, n=17:6, n=33:7, n=64:7, n=65:8, n=96:8

== 3. Mutacje dowodu (n<=33) ==
mutacji: 632692, przyjetych jako poprawne: 0
```

Korzenie są deterministyczne (liście `cert-entry-i`); podpisy ECDSA nie.

---

## 3️⃣ Split-view: dwie historie, dwa poprawne podpisy

Log podpisuje STH dla wielkości 10 dwukrotnie: raz uczciwie (A), raz z liściem
#3 podmienionym (B). Różnią się tylko korzeniem.

```
A: size=10 root=65646a0b208eb637 sig_ok=True
B: size=10 root=92373c4da74b8246 sig_ok=True
oba podpisane PRAWIDLOWO tym samym kluczem; ... => equivocation: True
  monitor A (zna STH A/10) dostaje STH B/25 + dowod 10->25 z drzewa B: odtworzony stary korzen != STH(first)
  monitor B (zna STH B/10) dostaje to samo: OK
  monitor A z dowodem z drzewa A, ale z korzeniem B/25: odtworzony nowy korzen != STH(second)
```

Wniosek: **każdy monitor z osobna jest bezpieczny tylko wtedy, gdy ma spójną
historię w obrębie swojego widoku**. Monitor B jest szczęśliwy — jego widok jest
wewnętrznie spójny. Wyjście na jaw daje dopiero zderzenie widoków: dowód
spójności pomiędzy STH z widoku A i STH z widoku B nie istnieje, a dla tej
samej wielkości porównanie korzeni wystarcza.

---

## 4️⃣ Monitor jako maszyna stanów

Stan = ostatnie zaakceptowane STH. Reguły z kodu (`Accept`): podpis → rollback
(`size` mniejszy) → cofnięty timestamp → ten sam rozmiar: korzenie muszą być
równe → większy rozmiar: wymagany dowód spójności.

```
pierwsze STH(5), bez dowodu (trust on first use): ZAAKCEPTOWANO size=5
STH(10) + dowod 5->10 z uczciwego logu:           ZAAKCEPTOWANO size=10
STH(10) z zepsutym podpisem:                      ODRZUCONO (zly podpis STH)
STH(25) bez dowodu:                               ODRZUCONO (brak dowodu spojnosci)
STH(25) + dowod 10->25:                           ZAAKCEPTOWANO size=25
STH(10) ponownie (rollback):                      ODRZUCONO (rollback: rozmiar 10 < 25)
STH(25) widok B + dowod 10->25 z drzewa B:        ODRZUCONO (EQUIVOCATION: ten sam rozmiar, inny korzen)
gossip: monitor z B/10 widzi A/10:                ODRZUCONO (EQUIVOCATION: ten sam rozmiar, inny korzen)
```

---

## 5️⃣ Niezależna kontrola

- **Python** (`verify_consistency.py`, tylko stdlib): korzenie liczone
  *przyrostowo ze stosem*, dowód weryfikowany *odwróconą rekurencją
  SUBPROOF* — inny algorytm niż w C#. Wynik: 325 przypadków uczciwych OK,
  0 rozbieżności korzeni, przypadek fork poprawnie odrzucony.
- **OpenSSL**: `openssl dgst -sha256 -verify work/log-pub.pem` na STH w
  formacie `TreeHeadSignature` (RFC 6962 §3.5): oryginał `Verified OK`,
  jeden zmieniony bajt → `Verification failure`.

---

## 6️⃣ Haczyki — to, co naprawdę trzeba wiedzieć

### 🪤 Haczyk 1: `m == n` i `m` będące potęgą dwójki to przypadki brzegowe
Dla `m == n` dowód jest **pusty** (i korzenie muszą być równe — to nie jest
„brak dowodu = OK"). Gdy `m` jest potęgą 2, stary korzeń *jest* węzłem w nowym
drzewie, więc w dowodzie go nie ma — weryfikator dopisuje go z STH(first) na
początek ścieżki. Pominięcie tego to klasyczny błąd w implementacjach.

### 🪤 Haczyk 2: długość dowodu jest częścią weryfikacji
Zbyt długi dowód i zbyt krótki to osobne odrzucenia (`dowod za dlugi` /
`sn != 0`). Samo zgodne `fr` bez sprawdzenia `sn == 0` zaakceptuje obcięty lub
doklejony dowód.

### 🪤 Haczyk 3: dowód z uczciwego drzewa nie ratuje fałszywego STH
Przypadek 3 wyżej: stary korzeń A, dowód z drzewa A, nowy korzeń z B → odrzucone
na poziomie nowego korzenia. Dowód wiąże **trzy** rzeczy naraz: `first`, `second`
i ścieżkę.

### 🪤 Haczyk 4: dowód spójności nie wykryje fałszu, jeśli nikt nie porówna
Monitor B był „szczęśliwy". Zabezpieczenie jest **społeczne/sieciowe**:
potrzebna jest wymiana STH (gossip) albo niezależny monitor. W kodzie
„gossip" to jedno wywołanie `Accept` z cudzym STH — to nie jest protokół
gossip, tylko jego zasadnicza reguła.

### 🪤 Haczyk 5: sama `m < n` nie wystarcza — zegar i rollback
Log może „cofnąć się" do mniejszego STH, żeby ukryć wpisy. Reguła `rollback`
i monotoniczność timestampu są poza dowodem spójności; w kodzie to zwykłe
`if`-y. Tolerancji na dryf zegara nie ma (produkcyjnie jest potrzebna).

### 🪤 Haczyk 6: pułapki API w .NET
- `ECDsa.SignData` bez `DSASignatureFormat.Rfc3279DerSequence` zwraca `r‖s`
  (P1363), a `openssl dgst -verify` oczekuje DER.
- Rozmiar drzewa w `TreeHeadSignature` to `uint64` big-endian — tu
  `BinaryPrimitives.WriteInt64BigEndian`; dla wartości < 2^63 bajty te same,
  nie sprawdzałem większych.
- `[.. a, .. b]` na `byte[]` kopiuje — przy dużej liczbie węzłów to zbędny
  koszt; dla n ≤ 96 pomijalny, nie mierzony.

---

## 7️⃣ Co z tego dla .NET

- Weryfikator to funkcja czysta `(first, second, rootFirst, rootSecond, proof)
  → powód|OK` — testuj ją wyczerpująco (wszystkie `m ≤ n ≤ N`) i mutacjami;
  tu 4656 par i ~633 tys. mutacji bez jednego fałszywego przyjęcia.
- Monitor trzyma **minimalny stan** (ostatnie STH) i odrzuca z powodem —
  loguj powód (jak w #15: `AuthenticationException` nie powie ci niczego).
- Nie myl: **dowód inkluzji** (#6) mówi „wpis jest w drzewie o korzeniu R",
  **dowód spójności** mówi „drzewo R' to rozszerzenie drzewa R".

---

## 8️⃣ Czego NIE zweryfikowałem (wprost)

- **Prawdziwy log CT** (`get-sth-consistency`, JSON/base64, 6962 vs 9162
  `/ct/v2`) i prawdziwe STH — brak dostępu do sieci; wszystkie logi to
  klucz ECDSA w procesie.
- **Protokół gossip** (RFC 9162 nie ma pełnej specyfikacji; draft gossip) —
  tu tylko reguła porównania STH, nie transport ani prywatność.
- **Duże drzewa**: rekurencja liczy `MTH` od zera (O(n log n) per dowód);
  produkcyjne logi używają przechowywanych poddrzew. Maks. n = 96.
- **RFC 9162 vs 6962**: weryfikację wzięto z 9162 §2.1.4.2 (algorytm
  iteracyjny), generację z 6962; nie porównywałem bajt-w-bajt z cudzą
  biblioteką (np. certificate-transparency-go) — tylko z własnym drugim
  algorytmem w Pythonie.
- **Windows/macOS, inne wersje .NET/OpenSSL** — tylko Linux, .NET 10.0.400,
  OpenSSL 3.0.2.
- **Dowód spójności a rotacja klucza logu / sharding czasowy** — brak.

## 📎 Co dalej w tej rubryce

Must-Staple (`id-pe-tlsfeature`) razem ze staplingiem, CAA/DANE (TLSA
wyliczany z certu), Kestrel jako strona egzekwująca SCT/mTLS, Windows/macOS
store, ACME z `pebble` (jeśli da się lokalnie).

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #22 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
