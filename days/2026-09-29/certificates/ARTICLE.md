<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #6 — 29 września 2026

![Certificate Transparency / RFC 6962](https://img.shields.io/badge/Certificate_Transparency_%C2%B7_RFC_6962-1E3A5F?style=for-the-badge&logo=letsencrypt&logoColor=white)

## Certificate Transparency od zera: piszemy własny log CT (Merkle tree, SCT, precert poison) i łamiemy go w .NET

</div>

---

> _"Sign, send, and forget" nigdy nie było bezpieczne dla CA. Certificate
> Transparency zamienia "zaufajcie nam" w "sprawdźcie sami" — pod warunkiem,
> że ktoś rozumie, co faktycznie jest podpisywane._

W #1–#4 zbudowaliśmy i złamaliśmy łańcuch zaufania, mTLS-a i mechanizmy
odwołań. Dziś temat, który **prawie żaden .NET developer nie zna od strony
bajtów**, a który od lat 2018+ jest twardym wymogiem każdej przeglądarki:
**Certificate Transparency** (RFC 6962). Zamiast czytać cudzy log CT (nie mamy
stąd dostępu do sieci — patrz sekcja 8), **budujemy własny, od zera**: własne
demo-CA, własny "operator logu CT" z kluczem EC, ręcznie kodowany precert z
rozszerzeniem *poison*, ręcznie policzony hash liścia drzewa Merkle, ręcznie
podpisany SCT (Signed Certificate Timestamp), dowód inkluzji (audit path) i
podpisany Signed Tree Head. Żadnej biblioteki CT — cała logika RFC 6962 to
~250 linii C#, które sami napisaliśmy i przetestowaliśmy.

Środowisko: .NET SDK 10.0.400, OpenSSL 3.0.2, Linux, **bez dostępu do sieci
zewnętrznej** (potwierdzone empirycznie — próba połączenia z `google.com`
została odrzucona przez sandbox). Kod: [`code/`](code/README.md).

| 🧪 Co | ✅ Status |
|---|---|
| Precert z rozszerzeniem `CT Precertificate Poison` (krytyczne) | wystawiony `openssl ca`, zdekodowany przez `openssl x509 -text` |
| RFC 6962 §2.1: `MerkleTreeLeaf` / leaf hash, ręczna implementacja | policzone, self-check ECDSA OK |
| SCT (`SignedCertificateTimestamp`) podpisany kluczem własnego "logu" | zbudowany, podpis zweryfikowany |
| Osadzenie SCT w certyfikacie finalnym (`1.3.6.1.4.1.11129.2.4.2`) | wystawiony `openssl ca`, bajty potwierdzone przez `openssl asn1parse` |
| Rekonstrukcja precertu z certyfikatu finalnego + weryfikacja podpisu SCT | zrobione w .NET, wynik: **OK** |
| Negatywny test: ten sam SCT wklejony do innego certyfikatu | zrobione, wynik: **FAILED** (tak ma być) |
| Drzewo Merkle: `audit path` (dowód inkluzji) + weryfikacja | policzone i zweryfikowane dla 10 rozmiarów drzewa × wszystkie indeksy |
| Signed Tree Head (STH): budowa, podpis, weryfikacja, wykrycie manipulacji roota | zrobione |
| Realny log CT (Google/Cloudflare/DigiCert), TLS-extension SCT, OCSP-stapled SCT, `consistency proof` między dwoma STH | **NIE sprawdzone** (patrz sekcja 8) |

---

## 1️⃣ Po co to komu: jeden certyfikat, dwa CA, zero CT

CA może się pomylić albo zostać złamane. Realny przypadek z 2011: DigiNotar
(holenderskie CA) zostało włamane i wystawiło fałszywe certyfikaty dla
`*.google.com`, które przez tygodnie nikt nie zauważył — bo nic nie
*publikowało* faktu wystawienia certyfikatu. CT (RFC 6962, Google 2013)
rozwiązuje to brutalnie prosto: **każdy certyfikat, żeby przeglądarki go
zaakceptowały, musi trafić do publicznego, tylko-dopisywalnego
(append-only) logu, i nieść dowód na to** (SCT). Log jest publiczny —
każdy, łącznie z ofiarą mis-issuance, może go monitorować i zauważyć
certyfikat na swoją domenę, którego nie zamawiał.

To NIE jest odwołanie (#4) — CT nie blokuje niczego w czasie rzeczywistym.
To detekcja post-factum, ale kluczowa: bez CT DigiNotar-style atak jest
niewidoczny; z CT jest kwestią czasu, aż monitor go złapie.

**Trzy sposoby dostarczenia SCT do klienta** (RFC 6962 §3.3):
1. **Rozszerzenie X.509** w samym certyfikacie (`1.3.6.1.4.1.11129.2.4.2`) —
   wymaga mechanizmu *precertyfikatu* (sekcja 2). **To jedyny sposób, który
   testujemy** — jedyny, który da się w pełni zbudować samym `openssl`.
2. Rozszerzenie w TLS (`ServerHello`) — wymaga wsparcia serwera TLS po stronie
   protokołu; `openssl s_server` tego nie oferuje. **Niesprawdzone.**
3. OCSP stapling z SCT w rozszerzeniu odpowiedzi OCSP. **Niesprawdzone.**

---

## 2️⃣ Precertyfikat i "poison": jak CA loguje coś, zanim to istnieje

Problem z kurczaka i jajka: SCT musi być **wewnątrz** certyfikatu (metoda 1
wyżej), ale żeby log podpisał SCT, musi już **znać treść** certyfikatu. CA
rozwiązuje to, wystawiając najpierw **precertyfikat** — identyczny co do
bajtów przyszły certyfikat, ale z dodanym **krytycznym** rozszerzeniem
"poison" (`1.3.6.1.4.1.11129.2.4.3`, wartość `NULL`). Krytyczne rozszerzenie,
którego żaden klient nie rozumie, gwarantuje (przez samą definicję RFC 5280),
że **żaden zgodny z normą klient nigdy nie zaakceptuje precertu** — nawet
przez pomyłkę.

Precert idzie do logu → log liczy hash i odsyła SCT → CA **wystawia
certyfikat finalny**: te same dane, ten sam serial, te same daty, ale
rozszerzenie poison zastąpione realną listą SCT.

Wystawiamy precert (`openssl ca`, pełne polecenie w [`code/README.md`](code/README.md)):

```
$ openssl x509 -in precert.pem -noout -text
...
        X509v3 extensions:
            X509v3 Basic Constraints: critical
                CA:FALSE
            X509v3 Key Usage: critical
                Digital Signature, Key Encipherment
            X509v3 Extended Key Usage:
                TLS Web Server Authentication
            X509v3 Subject Alternative Name:
                DNS:ct-demo.local
            CT Precertificate Poison: critical
                NULL
            X509v3 Subject Key Identifier:
                66:65:32:F6:D2:04:28:54:6F:7A:FD:49:F2:0A:D3:59:07:35:39:52
            X509v3 Authority Key Identifier:
                F9:CE:C7:99:35:E8:7C:4A:01:11:69:AF:02:F2:68:46:23:12:72:D2
```

`openssl` **rozpoznaje i nazywa** to rozszerzenie po OID (`ct_precert_poison`
jest w jego wbudowanej tablicy obiektów — `openssl list -objects | grep
11129`), co samo w sobie potwierdza, że kodujemy właściwy, prawdziwy OID
używany przez realne CA, nie coś zmyślonego.

> ⚠️ **Pułapka nr 1, na którą trafiłem po drodze:** żeby precert i finalny
> certyfikat miały identyczny `serial`/`notBefore`/`notAfter` (wymóg CA/Browser
> Forum, bo inaczej rekonstrukcja w sekcji 5 się nie zgadza), `openssl ca`
> musi dostać **ten sam** numer seryjny z pliku `serial` przy obu wywołaniach.
> Ponieważ `openssl ca` raz użyty numer zapisuje do `index.txt` i przy
> ponownym użyciu tego samego numeru **w tej samej bazie** narzeka, trzymamy
> precert i finalny certyfikat w **dwóch niezależnych bazach** (`precertdb/`,
> `finaldb/`) z tym samym CA, ale osobnym `index.txt`/`serial`. To obejście
> jest jawnie opisane w [`code/README.md`](code/README.md) — realne CA robią
> to inaczej (własna baza bez tego ograniczenia), ale efekt końcowy (identyczne
> serial+daty) jest ten sam i to jedyne, co ma znaczenie dla CT.

---

## 3️⃣ Ręcznie liczymy hash liścia drzewa Merkle (RFC 6962 §2.1, §3.4)

Zanim log cokolwiek podpisze, musi policzyć **hash liścia** dla naszego
precertu. Struktura `MerkleTreeLeaf` (uproszczona do naszego przypadku,
`precert_entry`):

```
version(1B)=0 | leaf_type(1B)=0 | timestamp(8B, ms) | entry_type(2B)=1(precert) |
issuer_key_hash(32B, SHA-256 SPKI CA) | tbs_len(3B) | tbs_certificate(TBS BEZ poison) |
extensions_len(2B)=0
```

`tbs_certificate` to TBSCertificate precertu **z fizycznie usuniętym**
rozszerzeniem poison — nie zamienionym na nic, usuniętym. Zaimplementowałem
to jako chirurgię DER na surowych bajtach ([`Asn1Surgery.cs`](code/dotnet/CtLab/Asn1Surgery.cs),
`System.Formats.Asn1`, żadnej biblioteki CT):

```csharp
public static byte[] RemoveExtension(byte[] certDer, string oidToRemove)
{
    var tbs = ExtractTbsCertificate(certDer);
    var seq = new AsnReader(tbs, AsnEncodingRules.DER).ReadSequence();
    var writer = new AsnWriter(AsnEncodingRules.DER);
    using (writer.PushSequence())
    {
        while (seq.HasData)
        {
            var tag = seq.PeekTag();
            if (tag.TagClass == TagClass.ContextSpecific && tag.TagValue == 3 && tag.IsConstructed)
            {
                // extensions [3] EXPLICIT SEQUENCE OF Extension — jedyne pole, które
                // dotykamy; wszystko inne kopiujemy bit-w-bit przez ReadEncodedValue/
                // WriteEncodedValue bez ponownej interpretacji.
                var extWrapper = seq.ReadSequence(ExplicitExtensionsTag);
                var extList = extWrapper.ReadSequence();
                using (writer.PushSequence(ExplicitExtensionsTag))
                using (writer.PushSequence())
                {
                    while (extList.HasData)
                    {
                        var extRaw = extList.ReadEncodedValue();
                        var oid = new AsnReader(extRaw, AsnEncodingRules.DER).ReadSequence().ReadObjectIdentifier();
                        if (oid == oidToRemove) continue;      // <- tu znika poison
                        writer.WriteEncodedValue(extRaw.Span);
                    }
                }
            }
            else { writer.WriteEncodedValue(seq.ReadEncodedValue().Span); }
        }
    }
    return writer.Encode();
}
```

Realny output (`dotnet run -- strip precert.pem 1.3.6.1.4.1.11129.2.4.3 out.bin`):

```
tbs-without-1.3.6.1.4.1.11129.2.4.3: 401 bytes, sha256=E4B5C9213B427D0C328C29E7F1726E5C41B6E1A3061E043822933509F8CC8A31
```

I `issuer_key_hash` (SHA-256 z `SubjectPublicKeyInfo` naszego demo-CA,
wyciągniętego tą samą chirurgią ASN.1):

```
issuer_key_hash = 4719211B9789601352663038412BACDAD844116195517EFB757821C659DF65D1
```

Złożony `timestampedEntry` (450 bajtów = 1+1+8+2+32+3+401+2 — suma pól zgadza
się co do bajta z sumą kontrolną narzędzia), realny output:

```
timestampedEntry (450 bytes) = 0000000001A0EAC99AA000014719211B9789601352663038412BACDAD844116195517EFB757821C659DF65D10001913082018DA00302010202021001300A06082A8648CE3D040302303631163014060355040A0C0D507261736F776B612044656D6F311C301A06035504030C13507261736F776B612043542044656D6F204341301E170D3236303932393030303030305A170D3237303932393030303030305A303031163014060355040A0C0D507261736F776B612044656D6F3116301406035504030C0D63742D64656D6F2E6C6F63616C3059301306072A8648CE3D020106082A8648CE3D03010703420004B455F724290858A40F75A58E79221D39E37ED960BCF202FD8066E024B933E2D3F020D7D44976C8BA1EB8BF34950684B7EA0B039E3295AB4BB930A8386C44C983A3819030818D300C0603551D130101FF04023000300E0603551D0F0101FF0404030205A030130603551D25040C300A06082B0601050507030130180603551D110411300F820D63742D64656D6F2E6C6F63616C301D0603551D0E04160414666532F6D20428546F7AFD49F20AD35907353952301F0603551D23041830168014F9CEC79935E87C4A011169AF02F26846231272D20000
leaf_hash = 13699F6EAAD1C56DFEFD5BCC517549433A5BECEDA80EFC30FDB21BF0DA03F0B3
```

`leaf_hash = SHA-256(0x00 || timestampedEntry)` — ten pojedynczy `0x00` na
początku to cała różnica między "hash liścia" a "dane do podpisu" w kroku
niżej.

> 💡 **Nieoczywisty fakt, który ułatwia implementację:** pole, które RFC 6962
> podpisuje bezpośrednio w SCT (§3.2, `signature_type=certificate_timestamp`),
> i pole które wchodzi do `MerkleTreeLeaf` (§3.4, `leaf_type=timestamped_entry`)
> to **te same bajty** — bo `v1=0`, `certificate_timestamp=0` i
> `timestamped_entry=0` mają identyczną wartość. Nie jest to przypadek naszej
> implementacji, to własność samego RFC: jedna metoda (`BuildPrecertTimestampedEntry`
> w [`Rfc6962.cs`](code/dotnet/CtLab/Rfc6962.cs)) obsługuje oba przypadki.

---

## 4️⃣ Log podpisuje: SCT

Log ma swój klucz EC P-256 (`ctlog.key`/`ctlog.pub` — **wyłącznie demo**,
nigdy nie był i nie będzie użyty do niczego poza tym artykułem).
`log_id = SHA-256(SubjectPublicKeyInfo klucza logu)`:

```
log_id = 15CCCC1758D5544979AF9DEC931E3E61C4C136213EF2E7315DF79C3C628678BA
```

Log podpisuje `timestampedEntry` (ECDSA/SHA-256) i pakuje strukturę SCT
(`sct_version|log_id|timestamp|extensions|hash_algo|sig_algo|signature`):

```
sct (117 bytes) = 0015CCCC1758D5544979AF9DEC931E3E61C4C136213EF2E7315DF79C3C628678BA000001A0EAC99AA0000004030046304402206931C5EE58D96227410CC348108EED2F97B8362140B700AE0901671CD431375E02205A52751920B61A4FD1E31CCF4639748B42AC7EE3A8CE518FF2BF850759559ABF
self-check: parse SCT + verify signature with log public key -> OK
```

`self-check` w kodzie parsuje własny SCT z powrotem i weryfikuje podpis
kluczem publicznym logu — od razu w tym samym procesie, więc gdyby kodowanie
było złe (zła kolejność pól, zła długość), ECDSA po prostu by nie zweryfikował.
Owija się to w `SignedCertificateTimestampList` (RFC 6962 §3.3) — dokładnie
taka struktura ląduje jako **wartość** rozszerzenia X.509:

```
sct-list extension value (121 bytes) hex = 007700750015CCCC1758D5544979AF9DEC931E3E61C4C136213EF2E7315DF79C3C628678BA000001A0EAC99AA0000004030046304402206931C5EE58D96227410CC348108EED2F97B8362140B700AE0901671CD431375E02205A52751920B61A4FD1E31CCF4639748B42AC7EE3A8CE518FF2BF850759559ABF
```

---

## 5️⃣ Finalny certyfikat + niezależna weryfikacja przez `openssl`

Wstawiamy tę wartość jako rozszerzenie `1.3.6.1.4.1.11129.2.4.2` (niekrytyczne
— zgodnie z RFC, w przeciwieństwie do poison) przez `openssl ca -extfile` z
linią `1.3.6.1.4.1.11129.2.4.2=DER:<hex>`, i wystawiamy finalny certyfikat z
**tym samym** serialem/datami co precert.

`openssl x509 -text` **zna nazwę** rozszerzenia (`CT Precertificate SCTs`),
ale w tej wersji (3.0.2, build Debiana) **nie ma** dedykowanego printera dla
jego zawartości — dostajemy surowy zrzut bajtów zamiast ładnie sformatowanej
struktury SCT, jaką dają nowsze/inaczej skonfigurowane buildy OpenSSL. To
sama w sobie ciekawa, realna obserwacja o przenośności narzędzi — więc
sięgnąłem po **generyczny** (nie-CT-specyficzny) `openssl asn1parse`, który
weryfikuje samą strukturę DER niezależnie od tego, czy rozumie CT:

```
$ openssl asn1parse -in final.pem
...
  343:d=4  hl=3 l= 135 cons: SEQUENCE
  346:d=5  hl=2 l=  10 prim: OBJECT            :CT Precertificate SCTs
  358:d=5  hl=2 l= 121 prim: OCTET STRING      [HEX DUMP]:007700750015CCCC1758D5544979AF9DEC931E3E61C4C136213EF2E7315DF79C3C628678BA000001A0EAC99AA0000004030046304402206931C5EE58D96227410CC348108EED2F97B8362140B700AE0901671CD431375E02205A52751920B61A4FD1E31CCF4639748B42AC7EE3A8CE518FF2BF850759559ABF
```

**121-bajtowy `OCTET STRING`, bez `BOOLEAN` critical (czyli `FALSE`, zgodnie z
RFC) — bajt w bajt to, co wypluł nasz kod w kroku 4.** To jest niezależne od
naszej implementacji potwierdzenie: `openssl asn1parse` to zupełnie inny
parser ASN.1 niż `System.Formats.Asn1` w .NET, napisany w C, i widzi
identyczne bajty na identycznej pozycji w poprawnej strukturze `Extension`.

Prawdziwy test to jednak kryptografia, nie zgodność bajtów. `verify-final`
robi to, co zrobiłby **monitor CT**: nie ma dostępu do `precert.pem` (który
z definicji nigdy nie powinien istnieć poza CA i logiem) — dostaje **tylko
finalny certyfikat**, wyciąga zeń SCT (`X509Certificate2.Extensions`, czyli
trzeci, znowu inny parser — .NET, nie OpenSSL), **sam rekonstruuje** precert
(usuwa rozszerzenie SCT tą samą funkcją `RemoveExtension`, która wcześniej
usuwała poison) i weryfikuje podpis ECDSA logu nad tak odtworzonymi danymi:

```
final certificate carries 1 SCT(s) in extension 1.3.6.1.4.1.11129.2.4.2 (critical=False)
reconstructed precert TBS from final cert: 401 bytes, sha256=E4B5C9213B427D0C328C29E7F1726E5C41B6E1A3061E043822933509F8CC8A31
original precert TBS (poison removed):    401 bytes, sha256=E4B5C9213B427D0C328C29E7F1726E5C41B6E1A3061E043822933509F8CC8A31
TBS reconstruction: OK - byte-identical to what was actually logged
SCT: version=0 log_id=15CCCC1758D5544979AF9DEC931E3E61C4C136213EF2E7315DF79C3C628678BA timestamp_ms=1790645476000 hash_algo=4 sig_algo=3 signature_len=70 -> verify: OK
```

Dwie niezależne ścieżki (precert→poison-usunięty vs finalny cert→SCT-usunięty)
dają **identyczny SHA-256**, mimo że powstały z dwóch osobnych wywołań
`openssl ca`. To nie przypadek — to właśnie mechanizm, który CT wymusza, i
dowód, że nasze demo-CA zrobiło to poprawnie.

---

## 6️⃣ Dlaczego to naprawdę coś wykrywa: negatywny test

Cała siła CT leży w tym, że SCT **nie jest pieczątką na certyfikacie** — jest
podpisem nad **konkretnymi bajtami**. Sklejmy więc **ten sam** SCT (skopiowany
1:1) do certyfikatu z **inną** nazwą domeny (`evil-ct-demo.local` zamiast
`ct-demo.local`), tym samym serialem/datami, podpisanego tym samym CA:

```
$ openssl ca ... -extfile tampered.ext ...   # tampered.ext ma inny SAN, ten sam SCT
```

Realny output `verify-final` na takim certyfikacie:

```
final certificate carries 1 SCT(s) in extension 1.3.6.1.4.1.11129.2.4.2 (critical=False)
reconstructed precert TBS from final cert: 406 bytes, sha256=9009621784D84067778FB89E54EFF1983986907717FE98D8E3C74C71D2A46C28
original precert TBS (poison removed):    401 bytes, sha256=E4B5C9213B427D0C328C29E7F1726E5C41B6E1A3061E043822933509F8CC8A31
TBS reconstruction: MISMATCH
SCT: version=0 log_id=15CCCC1758D5544979AF9DEC931E3E61C4C136213EF2E7315DF79C3C628678BA timestamp_ms=1790645476000 hash_algo=4 sig_algo=3 signature_len=70 -> verify: FAILED
```

`FAILED` to **exit code 6** procesu — narzędzie samo sygnalizuje błąd, nie
trzeba parsować tekstu. Zwróćcie uwagę: nawet długość TBS się zmieniła
(401→406 bajtów, bo `evil-ct-demo.local` jest dłuższy niż `ct-demo.local`) —
widać to gołym okiem zanim jeszcze podpis padnie. **To jest dokładnie ten
scenariusz, który złapałby monitor CT po realnym mis-issuance**: ktoś
(złośliwe/złamane CA, albo błąd w automatyzacji) wystawił certyfikat inny niż
ten zalogowany, i podpis SCT natychmiast to zdradza.

---

## 7️⃣ Drzewo Merkle: dowód inkluzji i Signed Tree Head

SCT to **obietnica** ("zaloguję to w ciągu `MMD`" — maximum merge delay).
Dowodem, że log **dotrzymał** obietnicy, jest **audit path** (dowód inkluzji)
w opublikowanym drzewie Merkle. RFC 6962 §2.1 definiuje hash drzewa
rekurencyjnie:

```
MTH({}) = SHA-256()
MTH({d0}) = SHA-256(0x00 || d0)                                    // = leaf hash
MTH(D[n]) = SHA-256(0x01 || MTH(D[0:k]) || MTH(D[k:n]))             // k = największa potęga 2 < n
```

Zaimplementowałem to (i dowód inkluzji, i jego weryfikację) rekurencyjnie
1:1 wg tej definicji ([`Rfc6962.MerkleTree`](code/dotnet/CtLab/Rfc6962.cs)) —
bez sztuczek bitowych z artykułów o Trillian, bo przy małym drzewie
rekurencja jest równie poprawna i dużo łatwiejsza do zweryfikowania. Test
własności (nie self-fikcja — to sprawdzenie matematycznej niezmienniczości):
zbuduj drzewo, weź dowód inkluzji dla **każdego** liścia, sprawdź że
rekonstrukcja z dowodu daje ten sam korzeń co bezpośrednie liczenie z całego
drzewa. Realny output dla 10 rozmiarów drzewa (1, 2, 3, 4, 5, 6, 7, 8, 13, 17
liści) × wszystkie indeksy w każdym — **każda** kombinacja:

```
n=  1 idx=  0 path_len= 0 -> OK
n=  2 idx=  0 path_len= 1 -> OK
n=  2 idx=  1 path_len= 1 -> OK
...
n= 17 idx= 16 path_len= 1 -> OK
selftest-merkle: ALL OK
```

(pełne 70 linii w [`code/README.md`](code/README.md) i w konsoli po
uruchomieniu — celowo wybrałem rozmiary **nie będące** potęgami 2, np. 13 i
17, bo to one najbardziej testują "nierówny" podział drzewa).

Teraz naszego prawdziwego liścia (`leaf_hash` z sekcji 3) wstawiamy do drzewa
z 5 syntetycznymi "wypełniaczami" (jawnie oznaczonymi w kodzie jako fikcyjne —
to nie są prawdziwe certyfikaty, tylko `SHA-256` etykiety, żeby drzewo miało
więcej niż jeden wpis):

```
tree_size = 6, our_index = 3
root = 34BBDFE5803D99C5E922AE0AAED1F13776C95921931CE514C67037D1355F861A
audit_path (3 entries, leaf->root):
  right sibling DEE4B4980B9D498657D1D8508D6101D7A4EE142A2B00A2BB32CF8083B360EF3A
  left  sibling 4F78F97C7A148C77FA89942F9E94BDE4B79AD8BAE8E57BD97CD940C296496EE2
  left  sibling CA586B9C00B58F77331FE5C73E1DADA49D00DE68FA1733682A0EFC120C953E56
recomputed root from leaf+audit_path = 34BBDFE5803D99C5E922AE0AAED1F13776C95921931CE514C67037D1355F861A
inclusion proof verification: OK (recomputed root == published root)
```

Na koniec log podpisuje **stan całego drzewa** — Signed Tree Head
(`digitally-signed` nad `version|signature_type=tree_hash|timestamp|tree_size|root_hash`):

```
STH: tree_size=6 timestamp=1790645500000 root=34BBDFE5803D99C5E922AE0AAED1F13776C95921931CE514C67037D1355F861A
verify(signature, log public key) -> OK
verify same signature against a tampered root -> rejected, as expected
```

Ten ostatni wiersz to test negatywny wprost w kodzie: bierzemy ten sam
podpis i podstawiamy root ze zmienionym jednym bajtem — weryfikacja **musi**
odpaść, i odpada. Gdyby nie odpadła, mielibyśmy błąd w implementacji podpisu,
nie w koncepcji CT.

---

## 8️⃣ Ściągawka

| Sytuacja | Co sprawdzić |
|---|---|
| Certyfikat ma "CT Precertificate SCTs" | `openssl x509 -text` (nazwa) lub `openssl asn1parse` (bajty), jeśli print nie działa |
| Ile SCT niesie certyfikat / z jakich logów | policz wpisy w `SignedCertificateTimestampList`, sekcja 4-5 |
| Czy SCT faktycznie pasuje do TEGO certyfikatu | usuń rozszerzenie SCT, dołóż `issuer_key_hash`, policz `timestampedEntry`, zweryfikuj ECDSA kluczem logu — sekcja 5/6 |
| Czy log dotrzymał obietnicy (nie tylko podpisał SCT, ale wpisał do drzewa) | dowód inkluzji względem opublikowanego STH — sekcja 7 |
| Precert "uciekł" na produkcję | rozszerzenie poison jest **krytyczne** — zgodny klient i tak go odrzuci (RFC 5280) |

---

## 📎 Czego NIE zweryfikowałem (wprost) i dlaczego

- **Realny log CT** (Google Argon/Xenon, Cloudflare Nimbus, DigiCert Yeti czy
  jakikolwiek inny) — środowisko nie ma dostępu do sieci zewnętrznej;
  potwierdziłem to empirycznie (próba `openssl s_client -connect
  www.google.com:443` i `curl` do `google.com` zostały odrzucone przez
  sandbox, zanim zdążyły wyjść w sieć). Cały log w tym artykule jest **nasz
  własny, demo, offline** — dokładnie tak, jak wymagały tego zasady tego
  zadania (żadnego prawdziwego Let's Encrypt/ACME/CT bez wyraźnej zgody i bez
  ryzyka rate-limitów na cudzej infrastrukturze).
- **SCT dostarczany przez rozszerzenie TLS albo OCSP stapling** — `openssl
  s_server`/`s_client` nie dają API do wstrzyknięcia SCT w te miejsca bez
  patchowania OpenSSL; przetestowałem tylko metodę 1 (rozszerzenie X.509).
- **`consistency proof`** (dowód, że drzewo o rozmiarze N jest rozszerzeniem
  drzewa o rozmiarze M<N, RFC 6962 §2.1.2) — zaimplementowałem tylko dowód
  inkluzji (audit path) dla ustalonego rozmiaru drzewa; consistency proof to
  osobna struktura, świadomie zostawiona na "następny poziom" (patrz niżej).
- **Wiele SCT / wiele logów jednocześnie** (Chrome CT Policy historycznie
  wymagał 2–3 SCT z niezależnych logów, zależnie od okresu ważności
  certyfikatu) — `BuildSctListExtensionValue` w kodzie obsługuje jeden SCT;
  parser (`ParseSctListExtensionValue`) obsługuje dowolną liczbę. Dokładne,
  aktualne na 2026 rok wymagania Chrome/CT Policy to wiedza ogólna, **nie
  sprawdzona eksperymentalnie tutaj** — mogły się zmienić.
- **Dlaczego `openssl x509 -text` w tej wersji (3.0.2, Debian) nie
  pretty-printuje zawartości SCT**, mimo że rozpoznaje OID — nie badałem
  źródeł OpenSSL, to obserwacja empiryczna, nie potwierdzona przyczyna.
- Windows/macOS (inne przeglądarki certyfikatów, inne API CT) — środowisko
  to wyłącznie Linux.

## 📎 Co dalej w tej rubryce

`consistency proof` między dwoma STH (dowód, że log nie robi "split-view"),
gossip protocol (wymiana STH między klientami jako obrona przed split-view),
Must-Staple + SCT razem, weryfikacja SCT w `SslStream`/Kestrelu "na żywo"
(callback, który faktycznie odrzuca połączenie bez ważnego SCT — dziś tylko
offline), ACME/`pebble` jeśli uda się postawić bez sieci zewnętrznej,
DANE/CAA.

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #6 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
