# Kod do wydania #6 — Certificate Transparency od zera (RFC 6962)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: `openssl` (sprawdzone na 3.0.2), **.NET 10 SDK** (sprawdzone na
10.0.400), `bash`, Linux. **Bez dostępu do sieci** — cały log CT jest nasz
własny, offline demo.

> **Bezpieczeństwo:** wszystkie klucze i certyfikaty (demo-CA, "log CT", leaf)
> są wyłącznie **DEMO** i powstają w `code/work/` (ignorowane przez git — patrz
> `.gitignore`). Nic tu nie łączy się z żadnym prawdziwym CA, logiem CT, ani
> systemem odbiorcy. Nie są dotykane żadne magazyny certyfikatów systemowe.

## Fragment prasówki, którego dotyczy ten kod

> Zamiast czytać cudzy log CT (brak dostępu do sieci), budujemy własny, od
> zera: własne demo-CA, własny "operator logu CT" z kluczem EC, ręcznie
> kodowany precert z rozszerzeniem *poison*, ręcznie policzony hash liścia
> drzewa Merkle, ręcznie podpisany SCT (Signed Certificate Timestamp), dowód
> inkluzji (audit path) i podpisany Signed Tree Head. Żadnej biblioteki CT —
> cała logika RFC 6962 to ~250 linii C#, które sami napisaliśmy i
> przetestowaliśmy. Certyfikat finalny z osadzonym SCT jest weryfikowany
> DWIEMA niezależnymi ścieżkami: generycznym `openssl asn1parse` (bajty się
> zgadzają) i naszym kodem .NET, który rekonstruuje precert z samego
> finalnego certyfikatu i kryptograficznie weryfikuje podpis ECDSA logu.
> Test negatywny — ten sam SCT wklejony do certyfikatu z innym SAN — jak
> należy, **nie przechodzi weryfikacji**.

## Struktura

```
code/
├── openssl/
│   └── setup-pki.sh          # cały pipeline: CA, log CT, precert, final cert, testy
├── dotnet/CtLab/              # cała logika RFC 6962 (bez żadnej biblioteki CT)
│   ├── Asn1Surgery.cs         # chirurgia DER: usuwanie jednego rozszerzenia z TBSCertificate
│   ├── Rfc6962.cs             # leaf hash, SCT, drzewo Merkle, audit path, STH
│   └── Program.cs             # CLI: strip / spki-hash / issue-sct / merkle-demo / sth / verify-final / selftest-merkle
└── work/                       # generowane demo-PKI (gitignored)
```

## Uwaga o uruchomieniu w środowisku, w którym powstał ten artykuł

Dokładnie jak w wydaniu #4: uruchomienie `bash setup-pki.sh` **jako całości**
zostało odrzucone przez sandbox tego środowiska (podobnie jak `mkdir` czy
podstawienia `$(...)` w pojedynczych poleceniach powłoki). Skrypt **nie był
uruchomiony jako całość** — każde polecenie z niego (te same `openssl`/`dotnet
run`, z tymi samymi argumentami) zostało wykonane **ręcznie, pojedynczo**, a
realne outputy z tych przebiegów są wklejone w [`../ARTICLE.md`](../ARTICLE.md).
`setup-pki.sh` jest więc w pełni **funkcjonalnym, ale niesprawdzonym-jako-
-całość** skryptem — poza sandboxem (zwykły `bash` na Linuksie z `openssl`
i `dotnet` w PATH) powinien przejść bez przeszkód.

## Jak uruchomić od zera (poza sandboxem)

```bash
cd code
bash openssl/setup-pki.sh          # -> code/work/, cały pipeline + testy na końcu
```

Skrypt: generuje demo-CA i klucz "logu CT" (oba EC P-256), leaf CSR, wystawia
precert z rozszerzeniem poison, buduje `dotnet/CtLab`, "wysyła" precert do
naszego logu (liczy leaf hash, podpisuje SCT), wystawia finalny certyfikat z
osadzonym SCT, weryfikuje go dwiema niezależnymi ścieżkami, pokazuje test
negatywny (ten sam SCT na certyfikacie z innym SAN — musi się nie zweryfikować),
buduje dowód inkluzji Merkle, podpisuje Signed Tree Head, i na końcu odpala
`selftest-merkle` (weryfikacja audit path dla 10 rozmiarów drzewa × wszystkie
indeksy).

### Ręczne kroki (dokładnie to, co faktycznie uruchomiono przy tworzeniu wydania)

Zakładając `WORK=code/work` i że jesteś w katalogu `code/`:

```bash
# 1. Demo-CA i klucz logu CT
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 \
  -keyout work/ca.key -out work/ca.pem -days 3650 -nodes -sha256 \
  -subj "/O=Prasowka Demo/CN=Prasowka CT Demo CA"
openssl ecparam -genkey -name prime256v1 -noout -out work/ctlog.key
openssl ec -in work/ctlog.key -pubout -out work/ctlog.pub

# 2. Leaf key + CSR
openssl ecparam -genkey -name prime256v1 -noout -out work/leaf.key
openssl req -new -key work/leaf.key -out work/leaf.csr -sha256 \
  -subj "/O=Prasowka Demo/CN=ct-demo.local"

# 3. Dwie niezależne "bazy" openssl ca (patrz artykuł, sekcja 2, pułapka nr 1)
#    z ca-precertdb.cnf / ca-finaldb.cnf / ca-finaldb2.cnf (treść w setup-pki.sh),
#    index.txt puste, plik serial zawierający "1001" w każdej.

# 4. Precert z poison (treść work/precert.ext - patrz artykuł sekcja 2, albo setup-pki.sh)
openssl ca -config work/ca-precertdb.cnf -in work/leaf.csr -out work/precert.pem \
  -extfile work/precert.ext -startdate 20260929000000Z -enddate 20270929000000Z \
  -batch -notext
openssl x509 -in work/precert.pem -noout -ext 1.3.6.1.4.1.11129.2.4.3

# 5. Build .NET
dotnet build dotnet/CtLab/CtLab.csproj -c Release

# 6. "Wyślij" do logu -> SCT + gotowa linia dla openssl -extfile
dotnet run --project dotnet/CtLab -c Release -- issue-sct \
  work/ca.pem work/precert.pem work/ctlog.key work/ctlog.pub 1790645476000 \
  work/sctlist-extvalue.bin work/leafhash.bin work/sct.extfile.txt

# 7. Finalny certyfikat (poison -> SCT list), extfile = te same 4 linie + zawartość sct.extfile.txt
openssl ca -config work/ca-finaldb.cnf -in work/leaf.csr -out work/final.pem \
  -extfile work/final.ext -startdate 20260929000000Z -enddate 20270929000000Z \
  -batch -notext

# 8. Niezależna weryfikacja bajtów (openssl) i podpisu (dotnet)
openssl asn1parse -in work/final.pem | grep -A1 "CT Precertificate SCTs"
dotnet run --project dotnet/CtLab -c Release -- strip work/precert.pem \
  1.3.6.1.4.1.11129.2.4.3 work/precert-tbs-nopoison.bin
dotnet run --project dotnet/CtLab -c Release -- verify-final \
  work/final.pem work/ctlog.pub work/ca.pem work/precert-tbs-nopoison.bin

# 9. Merkle + STH + selftest
dotnet run --project dotnet/CtLab -c Release -- merkle-demo work/leafhash.bin 5 3
dotnet run --project dotnet/CtLab -c Release -- sth work/tree-root.bin 6 1790645500000 \
  work/ctlog.key work/ctlog.pub
dotnet run --project dotnet/CtLab -c Release -- selftest-merkle
```

Oczekiwany output każdego kroku: sekcje 2–7 artykułu (skopiowane 1:1 z
rzeczywistych przebiegów; `dotnet build`: `0 Warning(s)`, `0 Error(s)` na
.NET SDK 10.0.400). Dokładne wartości hex/hash będą identyczne przy powtórnym
uruchomieniu z tymi samymi kluczami/wejściami (deterministyczne poza samym
podpisem ECDSA, który jest losowy z natury — stąd `sct`/`signature` będą
inne przy każdym uruchomieniu `issue-sct`, ale zawsze przejdą swój własny
`self-check`).

## Narzędzie `CtLab` — polecenia

```
dotnet run --project dotnet/CtLab -- <polecenie> [argumenty]

selftest-merkle
strip <cert.pem> <oid> <out.bin>
spki-hash <ca.pem>
issue-sct <ca.pem> <precert.pem> <logkey.pem> <logpub.pem> <timestampMsEpoch> <out-sctlist-extvalue.bin> <out-leafhash.bin> [out-extfile-fragment.txt]
merkle-demo <our-leafhash.bin> <fillerCount> <ourIndex>
sth <treeroot.bin> <treeSize> <timestampMsEpoch> <logkey.pem> <logpub.pem>
verify-final <final.pem> <logpub.pem> <ca.pem> <precert-stripped-tbs.bin>
```

Cała implementacja RFC 6962 (hash liścia, SCT, drzewo Merkle, STH) jest w
[`Rfc6962.cs`](dotnet/CtLab/Rfc6962.cs) — bez żadnej biblioteki CT, licząc na
`System.Security.Cryptography` (ECDSA, SHA-256). Chirurgia ASN.1 (usuwanie
jednego rozszerzenia z `TBSCertificate`, użyta i do poison, i do SCT list) jest
w [`Asn1Surgery.cs`](dotnet/CtLab/Asn1Surgery.cs), na `System.Formats.Asn1`
(w zestawie SDK, żadnego dodatkowego pakietu NuGet).
