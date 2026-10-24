<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #24 — 17 października 2026

![.NET](https://img.shields.io/badge/.NET-10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![BCL](https://img.shields.io/badge/BCL-OrderedDictionary%20out%20int%20index%20%2B%20SlhDsa-blue?style=for-the-badge)

## Jedno wyszukiwanie zamiast dwóch w `OrderedDictionary`, a postkwantowy `SlhDsa` — tylko do obejrzenia

</div>

---

> _"Algorithm 'SlhDsa' is not supported on this platform."_ — tyle wyciągnęliśmy z podpisu
> postkwantowego na tej maszynie (OpenSSL 3.0.2). Uczciwie: z `SlhDsa` zweryfikowaliśmy
> **tylko API i brak wsparcia**, nie żaden podpis. Za to `OrderedDictionary` pokazaliśmy w pełni.

Z listy „zostało z diffu" bierzemy dwie rzeczy: **`OrderedDictionary<TKey,TValue>.TryAdd/TryGetValue`
z `out int index`** oraz **`SlhDsa`** (FIPS 205). SDK .NET 11 nadal nie ma na tej maszynie
(`dotnet --list-sdks`: 8.0.422, 8.0.425, 9.0.316, 10.0.400), więc zostajemy przy .NET 10.
Kod w [`code/`](code/).

| # | Funkcja | Namespace | Status |
|---|---------|-----------|--------|
| 1️⃣ | `OrderedDictionary.TryAdd(k, v, out int index)` / `TryGetValue(k, out v, out int index)` | `System.Collections.Generic` | ✅ zweryfikowane `dotnet run -c Release` |
| 2️⃣ | `SlhDsa` / `SlhDsaAlgorithm` (podpis hash-based, FIPS 205) | `System.Security.Cryptography` | ⚠️ tylko API + `IsSupported=false`; **sign/verify niezweryfikowane** |

---

## 1️⃣ `OrderedDictionary` — indeks za darmo przy `TryAdd` i `TryGetValue`

### 😤 Problem
`OrderedDictionary<TKey,TValue>` (od .NET 9) łączy słownik z listą: wartości trzymają kolejność
wstawienia, a `GetAt(i)`/`SetAt(i, v)` pozwalają działać po indeksie. Tyle że żeby przejść od
klucza do indeksu, trzeba było zapłacić drugie wyszukiwanie przez `IndexOf(key)`. Typowy wzorzec
„licznik w kolejności pierwszego wystąpienia" kosztował więc dwa hashowania na element.

### ✨ Co się zmieniło
Dwa nowe przeciążenia (wiemy na pewno — patrz dowód niżej):
```csharp
bool TryAdd(TKey key, TValue value, out int index);
bool TryGetValue(TKey key, out TValue value, out int index);
```
Przy sukcesie `TryAdd` indeks to pozycja nowego wpisu; przy porażce — **indeks już istniejącego**
wpisu. `TryGetValue` zwraca `-1` na pudle. Cały wzorzec upsert w jednym wyszukiwaniu:
```csharp
if (!counts.TryAdd(word, 1, out int idx))
    counts.SetAt(idx, counts.GetAt(idx).Value + 1);
```

### 🔬 Dowód „przed i po"
Refleksja po publicznych metodach (`dotnet run -f net9.0` i `-f net10.0`, runtime 9.0.18 vs 10.0.11):
```
.NET 9.0.18:                          .NET 10.0.11:
TryAdd(TKey key, TValue value)        TryAdd(TKey key, TValue value)
TryGetValue(TKey key, out TValue)     TryAdd(TKey key, TValue value, out int index)
                                      TryGetValue(TKey key, out TValue value)
                                      TryGetValue(TKey key, out TValue value, out int index)
```
A prawdziwy błąd kompilatora — **tym razem naprawdę SDK 9.0.316** (przypięte `global.json`
z `rollForward: disable`), target `net9.0`, projekt `compat-check-ordered`:
```
Program.cs(8,16): error CS1501: No overload for method 'TryAdd' takes 3 arguments
Program.cs(9,16): error CS1501: No overload for method 'TryGetValue' takes 3 arguments
```
Dwuargumentowe `TryAdd`/`TryGetValue` w tym samym pliku kompilują się — więc to faktycznie
nowość .NET 10, nie .NET 9.

### 🖥️ Prawdziwy output (`dotnet run -c Release --project ordered-dictionary-index`)
```
--- 1. Podstawy: co dokladnie zwraca 'index' ---
TryAdd(alfa)   -> True, index=0
TryAdd(beta)   -> True, index=1
TryAdd(alfa*)  -> False, index=0  (indeks ISTNIEJACEGO wpisu), wartosc nadal 10
TryGetValue(beta) -> True, value=20, index=1
TryGetValue(brak) -> False, value=0, index=-1  (pudlo: -1)
--- 2. Po co: ile razy kolekcja liczy klucz (komparator-licznik, 1000 kluczy) ---
A) TryGetValue + IndexOf + SetAt : hash/klucz = 2.0, equals/klucz = 2.0
B) TryGetValue + indexer set     : hash/klucz = 2.0, equals/klucz = 2.0
C) TryGetValue(out, out) + SetAt : hash/klucz = 1.0, equals/klucz = 1.0
   wynik identyczny? A=1000, B=1000, C=1000 (oczekiwane 1000)
D) licznik slow, 3000 wejsc/500 unikalnych: stary hash=6000, nowy hash=3000; te same wyniki? True
```
Mierzymy **wywołania komparatora** (własny `IEqualityComparer<string>` z licznikami), nie czas —
liczba hashowań jest deterministyczna, czas nie. Połowa roboty znika: istotne przy drogich
kluczach (długie stringi, klucze złożone, komparator z normalizacją Unicode).

### 💡 Co to zmienia w praktyce
- Deduplikacja z zachowaniem kolejności + liczniki + „na której pozycji pierwszy raz" — jedno
  wyszukiwanie na element (sekcja 6 programu: `login x2`, `view x3`, `buy x2`, `logout x1`).
- Aktualizacja wartości po kluczu bez drugiego hashowania: `TryGetValue(k, out v, out i)` + `SetAt(i, f(v))`.

### ⚠️ Haczyk A — indeks to MIGAWKA, a nie uchwyt
Każde `RemoveAt`, `Remove` i `Insert` przesuwa indeksy. Zmierzone:
```
--- 3. Haczyk: indeks to MIGAWKA - po RemoveAt/Insert wskazuje inny wpis ---
indeks 'c' = 2
po RemoveAt(0) (z 3 wpisow zostaly 2, stary indeks wyszedl poza zakres):
  SetAt(2) -> ArgumentOutOfRangeException
po Insert(0): SetAt(1, 777) -> z=0, a=777, b=2, c=3
  klucz pod indeksem 1 to teraz 'a', nie 'b' (indeks 'b' = 2)
```
Groźniejszy jest drugi przypadek: po `Insert` indeks nadal mieści się w zakresie, więc
**`SetAt` cicho nadpisuje zły wpis** (`a=777`, a chcieliśmy `b`). Używaj indeksu natychmiast,
w tej samej „chwili" co wyszukiwanie; trzymanie go w polu/liście na później to bug.

### ⚠️ Haczyk B — `TKey = int`: indexer to klucz, `GetAt` to indeks
```
d[10]=dziesiec  GetAt(1)=dziesiec  TryGetValue(10) -> value=dziesiec, index=1
d[0] -> KeyNotFoundException (to klucz 0, nie pierwszy element)
d.GetAt(0)=30 (pierwszy element wg kolejnosci wstawienia)
```
Dla kluczy `int` łatwo pomylić `out int index` z wartością klucza — oba to `int`.

### ⚠️ Haczyk C — brzegi (wszystkie zmierzone)
- Klucz `null` → `ArgumentNullException` w obu przeciążeniach.
- Pusty słownik: `TryGetValue` → `False`, `value = default`, `index = -1`.
- Nieudany `TryAdd` nie zmienia kolejności (`x, y, z`) i nie nadpisuje wartości.
- Po `Remove` ostatniego i `TryAdd` nowego klucza dostaje on ten sam indeks (`b:1` → `c:1`).

### ⚠️ Haczyk D — `RemoveAt(0)` jest O(n), a indeks nie robi go tańszym
Rotacja 2000× `RemoveAt(0)` + `Add` na 50 000 elementach: **1185–1353 ms** w dwóch
uruchomieniach; to samo z końca (`RemoveAt(last)`): **0 ms**. Czasy orientacyjne (jedna maszyna,
`Stopwatch`, bez rozgrzewki ani BenchmarkDotNet), ale rząd wielkości jest jednoznaczny: usuwanie
z przodu przesuwa elementy **i** poprawia tablicę haszującą. `OrderedDictionary` to nie kolejka.

**Kod:** [`code/ordered-dictionary-index/`](code/ordered-dictionary-index/),
[`code/reflect-overloads/`](code/reflect-overloads/), dowód `CS1501`:
[`code/compat-check-ordered/`](code/compat-check-ordered/)

---

## 2️⃣ `SlhDsa` — podpisy oparte na hashach (FIPS 205), w .NET 10 jako eksperyment

### 😤 Problem
Podpisy RSA/ECDSA padną przed komputerem kwantowym. NIST ustandaryzował m.in. dwa schematy podpisu; w wydaniu #5
omówiliśmy `MLDsa` (kraty, FIPS 204). `SLH-DSA` (FIPS 205) to konserwatywna alternatywa:
bezpieczeństwo opiera się wyłącznie na odporności funkcji skrótu (SHA-2/SHAKE), nie na problemach
kratowych — płacisz za to wielkim podpisem.

### ✨ Co jest w .NET 10 (zweryfikowane refleksją)
Typy `SlhDsa`, `SlhDsaAlgorithm`, `SlhDsaCng`, `SlhDsaOpenSsl` w `System.Security.Cryptography`; na
`net9.0` brak (`SlhDsa` → w refleksji `(brak typow SlhDsa*)`). Metody m.in. `GenerateKey`,
`SignData`/`VerifyData` (z opcjonalnym `context`), `SignPreHash`/`VerifyPreHash`, eksport/import
PKCS#8, SPKI, PEM. Rozmiary z `SlhDsaAlgorithm` (odczytane programem):
```
SlhDsaSha2_128s    SLH-DSA-SHA2-128s      podpis=  7856 B  klucz publ.=32 B  klucz pryw.=64 B
SlhDsaSha2_128f    SLH-DSA-SHA2-128f      podpis= 17088 B  klucz publ.=32 B  klucz pryw.=64 B
SlhDsaSha2_256s    SLH-DSA-SHA2-256s      podpis= 29792 B  klucz publ.=64 B  klucz pryw.=128 B
SlhDsaSha2_256f    SLH-DSA-SHA2-256f      podpis= 49856 B  klucz publ.=64 B  klucz pryw.=128 B
```
(Pełna lista: 12 wariantów SHA2/SHAKE × 128/192/256 × `s`/`f` w README kodu.) Wariant `s` = małe
podpisy, wolne podpisywanie; `f` = szybkie podpisywanie, ~2× większy podpis. Dla porównania
podpis ECDSA P-256 to ok. 64–72 B — różnica to ponad 100×.

### 🖥️ Prawdziwy output — to, co udało się zweryfikować
```
--- 3. Wsparcie platformy ---
SlhDsa.IsSupported = False
MLDsa.IsSupported  = False
MLKem.IsSupported  = False
--- 4. Proba GenerateKey ---
RZUCILO PlatformNotSupportedException: Algorithm 'SlhDsa' is not supported on this platform.
```
Maszyna ma OpenSSL 3.0.2; wsparcie wymaga nowszego (w wydaniu #5 ustaliliśmy 3.5+ dla ML-DSA;
dla SLH-DSA **nie sprawdzaliśmy** progu osobno).

### 🔬 Dowód „przed i po" (SDK 9.0.316, `net9.0`, `compat-check-slhdsa`)
```
error CS0103: The name 'SlhDsa' does not exist in the current context
error CS0103: The name 'SlhDsaAlgorithm' does not exist in the current context
```

### ⚠️ Haczyk A — API jest `[Experimental]`: bez wyciszenia kod się nie skompiluje
Pierwsze `dotnet run` dało **`error SYSLIB5006: 'System.Security.Cryptography.SlhDsa' is for
evaluation purposes only and is subject to change or removal in future updates`**. Trzeba
`<NoWarn>$(NoWarn);SYSLIB5006</NoWarn>` w csproj (jest w naszym projekcie). Czyli: w .NET 10
`SlhDsa` jest świadomie niestabilny — nie wypuszczaj go do produkcji.

### ⚠️ Haczyk B — `IsSupported` to jedyny uczciwy test; reszta rzuca
Bez wsparcia platformy `GenerateKey` rzuca `PlatformNotSupportedException`. Zawsze sprawdzaj
`SlhDsa.IsSupported` (kod w sekcji 4 programu ma już gałąź sign/verify na maszynę z OpenSSL 3.5+ —
**nie została nigdy uruchomiona**, skompilowana owszem).

### ⚠️ Czego NIE wiemy
Nie podpisaliśmy ani nie zweryfikowaliśmy żadnej wiadomości, nie zmierzyliśmy czasu ani realnego
rozmiaru podpisu z `SignData` (rozmiary wyżej to stałe z `SlhDsaAlgorithm`), nie sprawdziliśmy
`SlhDsaCng` (Windows) ani interoperacyjności z innymi bibliotekami. `CompositeMLDsa` pominięte.

**Kod:** [`code/slhdsa-probe/`](code/slhdsa-probe/), dowód niekompilacji:
[`code/compat-check-slhdsa/`](code/compat-check-slhdsa/)

---

## 📎 Jak zweryfikowano
- `compat-check-ordered` (2× `CS1501`) i `compat-check-slhdsa` (`CS0103`×3) na `net9.0` z **prawdziwym SDK 9.0.316**
  (`global.json` z `rollForward: disable`); zawierają też stare, poprawne wywołania, które się kompilują.
- `reflect-overloads` uruchomione na runtime 9.0.18 i 10.0.11 (`dotnet run -f ...`).
- `ordered-dictionary-index` (`-c Release`, dwa przebiegi, liczniki identyczne, czasy z sekcji 7: 1185 i 1353 ms) i `slhdsa-probe` — `dotnet run` na SDK 10.0.400.
- **Niezweryfikowane:** realny sign/verify `SlhDsa` (brak OpenSSL 3.5+), próg wersji OpenSSL dla SLH-DSA,
  `SlhDsaCng`, `CompositeMLDsa`, wydajność `OrderedDictionary` w BenchmarkDotNet, indeksy przy
  współbieżnych modyfikacjach, `OrderedDictionary<,>` z własnym `TKey` o kosztownym `GetHashCode`
  (zasymulowany tylko licznikiem wywołań), .NET 11 (brak SDK), dokumentacja online (nie korzystano).

---

## 📎 Jak uruchomić
Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wszystkie artykuły: 🔷 .NET — nowości w wersji](../README.md) · [spis rubryk](../../../README.md)

</div>
