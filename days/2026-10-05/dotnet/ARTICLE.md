<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #12 — 5 października 2026

![.NET](https://img.shields.io/badge/.NET-10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![BCL](https://img.shields.io/badge/BCL-runtime-blue?style=for-the-badge)

## Span, który wie co jest "mniejsze", i JsonArray, który wreszcie umie czyścić się sam

</div>

---

> _"Object reference not set to an instance of an object."_
> — `System.NullReferenceException`, zmierzone realnie w tej sesji, rzucone przez
> `JsonArray.RemoveAll(x => x!.GetValue<int>() % 2 == 0)` na tablicy zawierającej JSON
> `null`. Nowe API bywa wygodne, ale "wygodne" nie znaczy "bezpieczne domyślnie" —
> szczegóły w sekcji 2️⃣ niżej.

Wydanie #9 (2 października) zostawiło dwa otwarte tropy ze swojej sekcji "jak
zweryfikowano": (1) **resztę** nowych przeciążeń `MemoryExtensions` — tamto wydanie
opisało tylko te z `IEqualityComparer<T>` (`IndexOf`, `Contains`, `StartsWith`,
`EndsWith`, `Count`), a diff refleksyjny `System.Private.CoreLib.dll` znalazł też
przeciążenia z `IComparer<T>`, nieopisane; (2) nowe API w `System.Text.Json.dll`
(`JsonObject.TryAdd`/`TryGetPropertyValue`, `JsonArray.RemoveAll`/`RemoveRange`,
`Utf8JsonWriter.WriteStringValueSegment`), też znalezione, ale nie opisane. Dziś
domykamy **oba** tropy — po jednej funkcji z każdego. Diff refleksyjny powtórzony w tej
sesji (`System.Reflection.MetadataLoadContext`, runtime'y **9.0.18** i **10.0.11**)
pokazał, że z całej "reszty" `IComparer<T>` w `MemoryExtensions` jest dokładnie
**jedna** nowa metoda — `SequenceCompareTo` — nie dziesiątki jak przy
`IEqualityComparer<T>`. Każda z dwóch funkcji opisanych dziś potwierdzona osobno realnym
błędem kompilatora na `net9.0`. Kod w [`code/`](code/).

| # | Funkcja | Namespace | Status |
|---|---------|-----------|--------|
| 1️⃣ | `MemoryExtensions.SequenceCompareTo<T>` z `IComparer<T>` | `System` (`System.Private.CoreLib`) | ✅ w pełni zweryfikowane |
| 2️⃣ | `JsonArray.RemoveAll` / `JsonArray.RemoveRange` | `System.Text.Json.Nodes` | ✅ w pełni zweryfikowane |

---

## 1️⃣ `MemoryExtensions.SequenceCompareTo<T>` z `IComparer<T>` — porządek Spanów według WŁASNYCH zasad

### 😤 Problem
`ReadOnlySpan<T>`/`Span<T>` mają `SequenceCompareTo` od dawna (.NET 6), ale tamten
overload wymaga `T : IComparable<T>` i zawsze porównuje w **domyślnym** porządku —
dla `byte` to porządek ordinal (liczbowa wartość bajtu), bez możliwości wstrzyknięcia
własnej logiki. Chcesz posortować/porównać bufory bajtów (np. surowe nazwy nagłówków
HTTP z sieci) **ignorując wielkość liter** albo w jakimkolwiek innym niestandardowym
porządku? Jedyną drogą było skopiowanie do `string`/tablicy i porównanie tam — ten sam
problem co z `IndexOf`/`Contains` opisany w wydaniu #9, tylko dla **porządkowania**,
nie wyszukiwania.

### ✨ Co się zmieniło
.NET 10 dodaje w `System.MemoryExtensions` jeden nowy overload:
`SequenceCompareTo<T>(ReadOnlySpan<T>, ReadOnlySpan<T>, IComparer<T>)`. Działa dla
dowolnego `T` (nie tylko tych, które implementują `IComparable<T>`), z dowolną logiką
porządkowania, jaką sam zdefiniujesz w komparatorze — bez kopiowania danych. Sprawdzone
empirycznie: **nie istnieje w .NET 9** — na `net9.0` to samo wywołanie daje `CS1501`
(dowód niżej). To jedyna nowa metoda `IComparer<T>` w `MemoryExtensions` między .NET 9 a
10 — reszta nowości w tej klasie (kilkadziesiąt metod, patrz wydanie #9) to
`IEqualityComparer<T>`, nie `IComparer<T>`.

```csharp
ReadOnlySpan<byte> naglowekA = "Header"u8;
ReadOnlySpan<byte> naglowekB = "header"u8;

// Domyslnie (ordinal) - rozne wartosci bajtow 'H' i 'h':
int ordinal = naglowekA.SequenceCompareTo(naglowekB);               // != 0

// .NET 10: wlasny porzadek przez IComparer<T> - bez kopiowania do string:
int ci = naglowekA.SequenceCompareTo(naglowekB, AsciiCi.Instance);  // == 0

class AsciiCi : IComparer<byte>
{
    public static readonly AsciiCi Instance = new();
    public int Compare(byte x, byte y) => Upper(x).CompareTo(Upper(y));
    static byte Upper(byte b) => (b >= (byte)'a' && b <= (byte)'z') ? (byte)(b - 32) : b;
}
```

### 🖥️ Prawdziwy output (`dotnet run --project span-ordering-compare`, ta maszyna)
```
--- 1. Problem: stary SequenceCompareTo ma TYLKO porzadek domyslny (ordinal dla byte) ---
"Header".SequenceCompareTo("header") [domyslnie, ordinal]: -32

--- 2. .NET 10: SequenceCompareTo<T> z IComparer<T> - wlasny porzadek, bez kopiowania ---
"Header".SequenceCompareTo("header", ci): 0

--- 3. Praktyczny przyklad: sortowanie nazw naglowkow HTTP (surowe bajty) alfabetycznie, case-insensitive ---
Przed sortowaniem: content-type, Accept, AUTHORIZATION, accept-encoding
Po Array.Sort z komparatorem opartym na SequenceCompareTo: Accept, accept-encoding, AUTHORIZATION, content-type
```

### 🔬 Dowód „przed i po" (target `net9.0`)
```
error CS1501: No overload for method 'SequenceCompareTo' takes 2 arguments
```
(wywołanie z trzecim argumentem — komparatorem — w ogóle nie znajduje dopasowania;
kompilator liczy argumenty, bo nie ma żadnego przeciążenia z trzema parametrami).

### 💡 Co to zmienia w praktyce
- Opakuj to w `IComparer<byte[]>`/`IComparer<ReadOnlyMemory<byte>>` (jak w przykładzie 3
  w kodzie) i `Array.Sort`/`List<T>.Sort` zaczyna sortować surowe bufory bajtów
  (nagłówki, klucze binarne, identyfikatory z protokołu sieciowego) **bez** konwersji na
  `string` tylko po to, żeby skorzystać z `string.Compare` z `StringComparison`.
- To domyka parę z wydania #9: tam `IndexOf`/`Contains` z `IEqualityComparer<T>`
  pozwoliły **szukać** w Spanie własną logiką równości; dziś `SequenceCompareTo` z
  `IComparer<T>` pozwala **porządkować** Spany własną logiką porządku. Razem to pełny
  komplet: szukanie + sortowanie na surowych buforach, bez alokacji.
- Działa dla **każdego** `T`, nie tylko typów, które już implementują `IComparable<T>` —
  np. własny `struct` bez `IComparable<T>` nagle można porównywać sekwencyjnie, wystarczy
  dostarczyć `IComparer<T>`.

### ⚠️ Haczyk — wynik to NIE zawsze -1/0/1, i rozna długość ma regułę prefiksu
Zmierzone realnie (sekcje 4-5 w kodzie): `"Header".SequenceCompareTo("header")` dało
**-32**, nie -1 — kontrakt `IComparer<T>`/`IComparable<T>` gwarantuje tylko **znak**
wyniku (`< 0`, `== 0`, `> 0`), nigdy konkretną wartość liczbową; kod, który sprawdza
`result == -1` zamiast `result < 0`, jest błędny i może się wysypać przy zmianie
implementacji w przyszłej wersji runtime'u. Druga pułapka: różna długość sekwencji nie
jest błędem — `"Head".SequenceCompareTo("Header")` dało wartość ujemną, bo krótszy ciąg
będący **prefiksem** dłuższego jest uznawany za "mniejszy", tak jak w
`string.CompareOrdinal`. Jeśli oczekujesz wyjątku albo specjalnej obsługi różnych
długości — nie ma takiej, to zwykłe porównanie leksykograficzne.

**Kod:** [`code/span-ordering-compare/`](code/span-ordering-compare/), dowód `CS1501`:
[`code/compat-check/`](code/compat-check/)

---

## 2️⃣ `JsonArray.RemoveAll` / `JsonArray.RemoveRange` — masowe usuwanie bez ręcznej pętli "od tyłu"

### 😤 Problem
`JsonArray` (z `System.Text.Json.Nodes`, czyli DOM-owy, mutowalny model JSON-a — w
odróżnieniu od `JsonDocument`, który jest tylko do odczytu) od .NET 6 miał `Add`,
`Insert`, `RemoveAt(int)` — ale **nie** miał odpowiednika `List<T>.RemoveAll(predicate)`
ani `List<T>.RemoveRange(index, count)`. Żeby usunąć z `JsonArray` wszystkie elementy
spełniające warunek, trzeba było pisać ręczną pętlę **od tyłu** (bo `RemoveAt` przesuwa
indeksy elementów za usuwanym w dół, więc iteracja w przód + `RemoveAt` pomija
elementy) — klasyczny, dobrze znany idiom-pułapka z `List<T>`, tylko odtwarzany ręcznie
dla `JsonArray` przy każdej okazji.

### ✨ Co się zmieniło
.NET 10 dodaje na `JsonArray` dwie metody instancyjne, z tą samą sygnaturą/ergonomią co
`List<T>`:
- `RemoveAll(Func<JsonNode?, bool> predicate)` — usuwa wszystkie elementy spełniające
  warunek, zwraca **liczbę** usuniętych.
- `RemoveRange(int index, int count)` — usuwa spójny wycinek `count` elementów od
  `index`.

Sprawdzone empirycznie: **żadna z nich nie istnieje w .NET 9** — na `net9.0` obie dają
`CS1061` (dowód niżej). Dla porównania: `JsonObject` (odpowiednik dla obiektów JSON)
dostał w tej samej wersji analogiczne usprawnienie — `TryAdd`/`TryGetPropertyValue` z
dodatkowym `out int` (indeks właściwości) — ale to osobny temat na kolejne wydanie.

```csharp
var dane = new JsonArray(1, 2, 3, 4, 5, 6);
int usuniete = dane.RemoveAll(x => x!.GetValue<int>() % 2 == 0);
// usuniete == 3, dane == [1, 3, 5]

var strona = new JsonArray(10, 20, 30, 40, 50, 60, 70);
strona.RemoveRange(2, 3); // usuwa indeksy 2,3,4
// strona == [10, 20, 60, 70]
```

### 🖥️ Prawdziwy output (`dotnet run --project jsonarray-bulk-ops`, ta maszyna)
```
--- 1. Problem: dotychczas JsonArray nie mial RemoveAll/RemoveRange, tylko RemoveAt(int) ---
Przed: [1,2,3,4,5,6]
Po recznej petli 'od tylu' (usun parzyste): [1,3,5]

--- 2. .NET 10: JsonArray.RemoveAll(predicate) - jedna linia, bez recznej petli ---
RemoveAll(parzyste) usunieto: 3, zostalo: [1,3,5]

--- 3. .NET 10: JsonArray.RemoveRange(index, count) - usuwanie SPOJNEGO wycinka ---
Po RemoveRange(2, 3): [10,20,60,70]

--- 4. Praktyczny przyklad: odfiltrowanie nieprawidlowych wpisow z JSON-a zewnetrznego API ---
Surowa odpowiedz: [{"id":1,"status":"ok"},null,{"id":2,"status":"error"},{"id":3,"status":"ok"},null]
RemoveAll (null-safe predicate) usunieto: 3, zostalo: [{"id":1,"status":"ok"},{"id":3,"status":"ok"}]
```

### 🔬 Dowód „przed i po" (target `net9.0`)
```
error CS1061: 'JsonArray' does not contain a definition for 'RemoveAll' and no accessible
extension method 'RemoveAll' accepting a first argument of type 'JsonArray' could be found
error CS1061: 'JsonArray' does not contain a definition for 'RemoveRange' and no accessible
extension method 'RemoveRange' accepting a first argument of type 'JsonArray' could be found
```

### 💡 Co to zmienia w praktyce
- Filtrowanie odpowiedzi zewnętrznych API przed dalszym przetwarzaniem (odrzucanie
  `null`-i, błędnych wpisów, duplikatów) to jedna linia zamiast pętli z licznikiem i
  iterowaniem od tyłu — mniej miejsca na klasyczny błąd "pominięty element przy
  usuwaniu w pętli w przód".
- `RemoveRange` nadaje się do przycinania tablic JSON do limitu (np. "zostaw tylko 10
  pierwszych wyników po sortowaniu") bez pisania `while (arr.Count > limit) arr.RemoveAt(arr.Count - 1)`.
- `JsonArray` dogania ergonomię `List<T>` — dla kogoś, kto już znał `RemoveAll`/
  `RemoveRange` z `List<T>`, nie trzeba uczyć się nowego idiomu, nazwy i sygnatury są
  tożsame.

### ⚠️ Haczyk A — `RemoveAll` NIE jest null-safe, mimo że `JsonArray` może zawierać JSON `null`
Zmierzone realnie (sekcja 5 w kodzie): `JsonArray` **może** zawierać element, który jest
dosłownie JSON-owym `null` (`arr[i]` zwraca `null` z C#, nie specjalny obiekt
"JsonNull"). Predykat w `RemoveAll`, który odwołuje się do `x!.GetValue<int>()` bez
sprawdzenia `x is null`, rzuca `NullReferenceException` **w trakcie** wywołania
`RemoveAll` — nie jest to wyjątek walidacyjny z ładnym komunikatem, tylko gołe NRE.
Trzeba samemu pisać `x is null || ...` w predykacie, tak jak w przykładzie 4 wyżej —
.NET nie robi tego za Ciebie, mimo że `JsonArray.Parse` może swobodnie wyprodukować
elementy `null` z każdego poprawnego JSON-a z wartością `null` w tablicy.

### ⚠️ Haczyk B — `RemoveRange` z `count` wychodzącym poza granice rzuca `ArgumentException`, nie `ArgumentOutOfRangeException`
Zmierzone realnie (sekcja 6 w kodzie): `arr.RemoveRange(1, 10)` na trzyelementowej
tablicy rzuca `ArgumentException` z komunikatem o "Offset and length were out of
bounds..." — nie `ArgumentOutOfRangeException`, czego można by się intuicyjnie
spodziewać po analogii do `List<T>.RemoveRange` (który też rzuca `ArgumentException` w
tym przypadku, więc zachowanie jest konsekwentne z `List<T>` — ale warto to mieć w
`catch`, jeśli łapiesz wyjątki po typie).

**Kod:** [`code/jsonarray-bulk-ops/`](code/jsonarray-bulk-ops/), dowód `CS1061`×2:
[`code/compat-check/`](code/compat-check/)

---

## 📎 Jak zweryfikowano „co jest nowe w .NET 10"

Jak w wydaniach #7 i #9: zamiast polegać na pamięci, w tej sesji ponownie porównano
realną powierzchnię API zainstalowanych runtime'ów `Microsoft.NETCore.App` **9.0.18** i
**10.0.11** przez refleksję (`System.Reflection.MetadataLoadContext`,
`PathAssemblyResolver` na katalogi `shared/Microsoft.NETCore.App/<wersja>`), tym razem z
poprawką względem wydania #9: metody **instancyjne** (nie tylko statyczne/extension) też
zostały objęte diffem, bo inaczej `JsonObject.TryAdd`/`JsonArray.RemoveAll` (metody
instancyjne) w ogóle nie trafiłyby na listę. Diff `System.MemoryExtensions` dał 42 nowe
sygnatury między 9.0.18 i 10.0.11 — z tego dokładnie **jedna** z `IComparer<T>`
(`SequenceCompareTo`), reszta to `IEqualityComparer<T>` (opisane w wydaniu #9) albo
`SearchValues<T>` bez komparatora (`CountAny`, `ReplaceAny`, `ReplaceAnyExcept` —
niepowiązane z tematem komparatorów, do rozważenia w przyszłym wydaniu). Diff
`JsonObject`/`JsonArray`/`Utf8JsonWriter` potwierdził też `JsonObject.TryAdd`/
`TryGetPropertyValue` z dodatkowym `out int` (indeks właściwości) i
`Utf8JsonWriter.WriteStringValueSegment`/`WriteBase64StringSegment` (zapis dużych
wartości string/base64 w kawałkach, bez buforowania całości) — oba **nieopisane** w
tym wydaniu (żeby nie rozwadniać artykułu o 4 funkcje naraz), zostają jako trop na
następne wydanie .NET w rotacji. Każda z dwóch funkcji opisanych dziś potwierdzona
osobno realną kompilacją (`CS1501`, `CS1061`×2) na `net9.0`. Skrypt porównawczy
(projekt tymczasowy z pakietem `System.Reflection.MetadataLoadContext`) nie wszedł do
repo — uruchamiany w `/tmp` poza katalogiem tego wydania, usunięty po użyciu.

---

## 📎 Jak uruchomić
Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #12 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
