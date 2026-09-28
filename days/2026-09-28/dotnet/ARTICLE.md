<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #5 — 28 września 2026

![.NET](https://img.shields.io/badge/.NET-10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![BCL](https://img.shields.io/badge/BCL-runtime-blue?style=for-the-badge)

## Kryptografia postkwantowa i generyczne uchwyty GC — .NET 10 schodzi głębiej w BCL

</div>

---

> _"Ktoś nagrywa dziś Twój zaszyfrowany ruch TLS. Nie żeby go teraz złamać — tylko żeby
> odszyfrować za 10 lat, gdy komputer kwantowy będzie już gotowy."_ — atak typu
> *harvest now, decrypt later*, główny powód, dla którego NIST w sierpniu 2024 wydał
> finalne standardy FIPS 203/204/205.

Kończymy przegląd nowości **języka** C# 14 (extension members, `field`, lambdy bez
typów, first-class Span — wydania #1–#4) i schodzimy w **BCL/runtime .NET 10**: dwie
funkcje, których jeszcze nie było w tej rubryce. Obie zweryfikowane empirycznie —
skompilowane, uruchomione, a tam gdzie się dało, porównane bezpośrednio z .NET 9 (SDK
9.0.316 zainstalowane obok 10.0.400, żeby faktycznie sprawdzić, co jest nowe, a nie
zgadywać). Kod w [`code/`](code/).

| # | Funkcja | Namespace | Status na tej maszynie |
|---|---------|-----------|----------|
| 1️⃣ | `MLDsa`, `MLKem` — kryptografia postkwantowa (FIPS 203/204) | `System.Security.Cryptography` | ⚠️ API obecne, ale `IsSupported=false` (patrz niżej) |
| 2️⃣ | `GCHandle<T>`, `PinnedGCHandle<T>`, `WeakGCHandle<T>` | `System.Runtime.InteropServices` | ✅ w pełni zweryfikowane |

---

## 1️⃣ Kryptografia postkwantowa: `MLDsa` i `MLKem`

### 😤 Problem
RSA, ECDSA i ECDH opierają bezpieczeństwo na tym, że faktoryzacja dużych liczb i
logarytm dyskretny na krzywych eliptycznych są dla klasycznego komputera praktycznie
nie do policzenia. Algorytm Shora na wystarczająco dużym komputerze kwantowym łamie
oba te problemy w czasie wielomianowym. Nikt dziś nie ma takiego komputera — ale to nie
znaczy, że problem jest odległy: przeciwnik może **already dziś nagrywać zaszyfrowany
ruch** i odszyfrować go, gdy sprzęt dojrzeje ("harvest now, decrypt later"). W sierpniu
2024 NIST opublikował finalne standardy: **FIPS 203 (ML-KEM)** — uzgadnianie kluczy,
**FIPS 204 (ML-DSA)** — podpis cyfrowy, **FIPS 205 (SLH-DSA)** — alternatywny podpis
oparty na funkcjach skrótu.

### ✨ Co się zmieniło
.NET 10 dodaje do `System.Security.Cryptography` nowe klasy `MLDsa` i `MLKem` (plus
eksperymentalny `SlhDsa`, wciąż oznaczony `[Experimental("SYSLIB5006")]` — nie
kompiluje się bez świadomego wyciszenia diagnostyki). Sprawdzone empirycznie: **żadna z
tych trzech klas nie istnieje w .NET 9** — na SDK 9.0.316 `MLDsa`/`MLKem` dają
`CS0103` (patrz `compat-check/`). Kształt API naśladuje istniejące klasy asymetryczne
(`RSA`, `ECDsa`) — jest nawet `CompositeMLDsa` do podpisów hybrydowych
(klasyczny + postkwantowy w jednym certyfikacie, na przejście migracyjne).

```csharp
Console.WriteLine(MLDsa.IsSupported);   // zależy od platformy - patrz niżej
Console.WriteLine(MLKem.IsSupported);

using MLDsa key = MLDsa.GenerateKey(MLDsaAlgorithm.MLDsa65);
byte[] signature = key.SignData(data, context: Array.Empty<byte>());
bool ok = key.VerifyData(data, signature, context: Array.Empty<byte>());

using MLKem kem = MLKem.GenerateKey(MLKemAlgorithm.MLKem768);
kem.Encapsulate(out byte[] ciphertext, out byte[] sharedSecretSender);
byte[] sharedSecretReceiver = kem.Decapsulate(ciphertext);
```

### 🖥️ Prawdziwy output (`dotnet run --project pq-crypto`, ta maszyna)
```
--- Wsparcie platformy dla kryptografii postkwantowej (.NET 10) ---
MLDsa.IsSupported = False
MLKem.IsSupported = False

--- ML-DSA (FIPS 204) - podpis cyfrowy odporny na atak kwantowy ---
MLDsa.GenerateKey rzucil: System.PlatformNotSupportedException
Komunikat: Algorithm 'MLDsa' is not supported on this platform.

--- ML-KEM (FIPS 203) - uzgadnianie kluczy odporne na atak kwantowy ---
MLKem.GenerateKey rzucil: System.PlatformNotSupportedException
Komunikat: Algorithm 'MLKem' is not supported on this platform.
```

### 🔬 Dowód „przed i po" (SDK 9.0.316, `net9.0`)
```
error CS0103: The name 'MLDsa' does not exist in the current context
```

### 💡 Co to zmienia w praktyce
- Nie trzeba już ciągnąć BouncyCastle czy innej biblioteki 3rd-party, żeby dostać
  zgodną ze standardem implementację ML-KEM/ML-DSA — API jest w BCL, w tym samym stylu
  co `RSA`/`ECDsa`, więc migracja istniejącego kodu podpisującego jest mechaniczna.
- `CompositeMLDsa` pozwala na okres przejściowy podpisywać **jednocześnie** kluczem
  klasycznym i postkwantowym — jeśli jeden algorytm okaże się złamany, drugi wciąż
  chroni.
- Są warianty `MLDsaOpenSsl`/`MLDsaCng`/`MLKemOpenSsl`/`MLKemCng` do jawnego wskazania
  backendu, jeśli nie chcesz polegać na automatycznym wyborze providera.

### ⚠️ Haczyk — dlaczego `IsSupported=False` u mnie
Na Linuksie ML-KEM/ML-DSA w .NET 10 są **wspierane przez OpenSSL 3.5+** (na Windows:
CNG od Windows 11 24H2 / Server 2025). Ta maszyna ma `OpenSSL 3.0.2 15 Mar 2022` —
za starą wersję, stąd `IsSupported=false` i realny `PlatformNotSupportedException`
pokazany wyżej. **Nie zweryfikowałem** więc faktycznego podpisywania/weryfikacji ani
encapsulate/decapsulate end-to-end — tylko że kod się kompiluje (sprawdzone sygnatury
z prawdziwej biblioteki referencyjnej przez refleksję) i że ścieżka „brak wsparcia"
działa i daje sensowny komunikat zamiast crasha. Jeśli aktualizujesz OpenSSL do 3.5+,
`if (MLDsa.IsSupported)` w kodzie przełączy się na pełną ścieżkę bez żadnej zmiany.

**Kod:** [`code/pq-crypto/`](code/pq-crypto/), dowód `CS0103`: [`code/compat-check/`](code/compat-check/)

---

## 2️⃣ Generyczne, typowane uchwyty GC: `GCHandle<T>`, `PinnedGCHandle<T>`, `WeakGCHandle<T>`

### 😤 Problem
Klasyczny `GCHandle` (od .NET Framework 1.1) jest **niegeneryczny** — `Target` ma typ
`object`. Dla typu wartościowego `GCHandle.Alloc(42)` **boksuje** `int` przy każdej
alokacji, a każdy odczyt `Target` wymaga rzutowania w miejscu użycia — łatwo o
`InvalidCastException` po refaktoryzacji, bo kompilator niczego tu nie sprawdza.
Do przypinania tablic pod wskaźnik trzeba było `GCHandleType.Pinned` +
`Marshal.UnsafeAddrOfPinnedArrayElement` — też bez udziału typu w sygnaturze.

### ✨ Co się zmieniło
.NET 10 dodaje w `System.Runtime.InteropServices` trzy nowe, generyczne typy —
sprawdzone empirycznie: **żaden nie istnieje w .NET 9** (`GCHandle<T>` na SDK 9.0.316
daje `CS0308`, bo `GCHandle` tam wciąż jest tylko niegeneryczny):

- `GCHandle<T>` — silny uchwyt, `Target` typu `T`, bez boksowania i bez rzutowania.
- `PinnedGCHandle<T>` — przypięty uchwyt + `GCHandleExtensions.GetAddressOfArrayData`/
  `GetAddressOfStringData`/`GetAddressOfObjectData` do surowego wskaźnika.
- `WeakGCHandle<T>` — typowany słaby uchwyt z `TryGetTarget(out T)`.

```csharp
GCHandle<StringBuilder> typedHandle = new(sb);
StringBuilder target = typedHandle.Target;      // brak rzutowania

PinnedGCHandle<int[]> pinned = new(buffer);
int* ptr = GCHandleExtensions.GetAddressOfArrayData(pinned);
ptr[0] = 999;                                    // zapis wprost do pamieci tablicy

var weak = new WeakGCHandle<object>(obj, trackResurrection: false);
weak.TryGetTarget(out object? maybeAlive);
```

### 🖥️ Prawdziwy output (`dotnet run --project typed-gchandle -c Release`)
```
--- 1. stary GCHandle (non-generic, boxing) ---
typ Target: System.Int32, wartosc: 42
--- 2. GCHandle<T> generyczny, bez boxingu, bez rzutowania ---
target.ToString() = hello
--- 3. PinnedGCHandle<T> - przypiecie tablicy i surowy wskaznik ---
buffer po zapisie przez wskaznik: 999,2,3,4,5
--- 4. WeakGCHandle<T> - typowany slaby uchwyt ---
przed GC: obiekt zyje = True
po GC: obiekt zyje = False
--- 5. Haczyk: PinnedGCHandle<T> na tablicy typow referencyjnych ---
Stary GCHandle.Alloc(string[], Pinned):
  rzucil: ArgumentException: Object contains references. (Parameter 'value')
Nowy PinnedGCHandle<string[]>:
  brak wyjatku; wskaznik = 128549423946240; ptr[0] == refArr2[0]: True
```
(Sekcja 4 uruchomiona w konfiguracji `Release` z `[MethodImpl(NoInlining)]` na
pomocniczych metodach — w `Debug` JIT potrafi sztucznie wydłużyć czas życia lokalnej
zmiennej i obiekt „przeżywa" GC mimo braku referencji; to znany efekt uboczny
niezoptymalizowanego kodu, nie błąd w `WeakGCHandle<T>`.)

### 🔬 Dowód „przed i po" (SDK 9.0.316, `net9.0`)
```
error CS0308: The non-generic type 'GCHandle' cannot be used with type arguments
```

### 💡 Co to zmienia w praktyce
- Kod interopu z typami wartościowymi (np. bufory do natywnych API) nie boksuje
  przy każdej alokacji uchwytu — mniej śmieci na stercie w gorących ścieżkach.
- `Target` jest typu `T` — błąd typu wykrywa kompilator, nie `InvalidCastException`
  w runtime po czyimś refaktorze.
- `PinnedGCHandle<T>` + `GetAddressOfArrayData` to prostszy zamiennik dla
  `fixed`/`Marshal.UnsafeAddrOfPinnedArrayElement` tam, gdzie uchwyt musi żyć dłużej
  niż jeden blok `fixed`.

### ⚠️ Haczyk — `PinnedGCHandle<T>` jest luźniejszy niż stary `GCHandleType.Pinned`
Sprawdzone realnie (sekcja 5 w kodzie): stary `GCHandle.Alloc(tablica_stringow,
GCHandleType.Pinned)` rzuca `ArgumentException: Object contains references` — CLR
jawnie blokuje pinowanie tablic z elementami referencyjnymi. **Nowy
`PinnedGCHandle<string[]>` tego nie robi** — konstrukcja się udaje, a
`GCHandleExtensions.GetAddressOfArrayData` (skompilowane z ostrzeżeniem `CS8500`,
bo `string*` to wskaźnik na typ zarządzany) zwraca działający wskaźnik, przez który
faktycznie widać ten sam obiekt co w tablicy (`ReferenceEquals` = `true`). To
realna, zmierzona różnica w zachowaniu — **nie zbadałem** dlaczego stara ścieżka wciąż
ma tę blokadę, a nowa nie (celowe rozluźnienie reguł czy po prostu inna implementacja
security-check), ani czy jest to bezpieczne przy kompaktującym GC na dłuższą metę.
Traktuj to jako obserwację do dalszej weryfikacji, nie jako rekomendację pinowania
dowolnych typów referencyjnych.

**Kod:** [`code/typed-gchandle/`](code/typed-gchandle/), dowód `CS0308`: [`code/compat-check/`](code/compat-check/)

---

## 📎 Jak uruchomić
Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #5 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
