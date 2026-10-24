<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #9 — 2 października 2026

![.NET](https://img.shields.io/badge/.NET-10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![BCL](https://img.shields.io/badge/BCL-runtime-blue?style=for-the-badge)

## Generator liczb, który woli się wysypać od razu, i Span, który wreszcie umie porównywać po swojemu

</div>

---

> _"Specified argument was out of the range of valid values. (Parameter 'step')"_
> — `System.ArgumentOutOfRangeException`, rzucony przez `Enumerable.Sequence(1, 5, 0)`
> **zanim program w ogóle wszedł w pętlę `foreach`**. Nie jest to literacki cytat dnia,
> tylko dosłowny, zmierzony w tej sesji dowód na to, że ta jedna metoda LINQ łamie
> przyzwyczajenie, które reszta LINQ przez 15 lat uczyła nas mieć: "LINQ jest leniwe,
> więc błędne argumenty wyjdą dopiero przy enumeracji". Szczegóły w sekcji 1️⃣ niżej.

Ostatnie wydanie rubryki .NET (#7, 30 września — wydanie #8 tego dnia nie miało odcinka
.NET) zostawiło otwarty trop: przy okazji przeglądu `System.Linq.dll` znaleziono też
`Enumerable.Sequence`/`InfiniteSequence`, ale nie opisano ich, żeby nie rozwadniać
wydania o `Shuffle`. Dziś domykamy ten trop — i dokładamy drugą, osobną nowość: BCL w
.NET 10 w końcu pozwala przeszukiwać `Span<T>`/`ReadOnlySpan<T>` z **własną** logiką
równości (`IEqualityComparer<T>`), a nie tylko z wbudowanym `StringComparison` dla
`char`. Obie funkcje znalezione **empirycznie** tą samą metodą co poprzednio: refleksja
(`MetadataLoadContext`) porównująca publiczne API zainstalowanych runtime'ów **9.0.18**
i **10.0.11** (`Microsoft.NETCore.App`), każda kandydatka potwierdzona osobno realnym
błędem kompilatora na `net9.0`. Kod w [`code/`](code/).

| # | Funkcja | Namespace | Status |
|---|---------|-----------|--------|
| 1️⃣ | `Enumerable.Sequence<T>` / `Enumerable.InfiniteSequence<T>` | `System.Linq` | ✅ w pełni zweryfikowane |
| 2️⃣ | `MemoryExtensions.IndexOf`/`Contains`/`StartsWith`/`EndsWith`/`Count` z `IEqualityComparer<T>` | `System` (`System.Private.CoreLib`) | ✅ w pełni zweryfikowane |

---

## 1️⃣ `Enumerable.Sequence<T>` / `Enumerable.InfiniteSequence<T>` — generator ciągów, który nie czeka z walidacją

### 😤 Problem
LINQ od dawna ma `Enumerable.Range(start, count)`, ale to narzędzie ma dwa poważne
ograniczenia: działa tylko na `int` i liczy **liczbę elementów**, nie punkt końcowy, więc
nie umie zejść w dół (malejąco) ani zrobić kroku innego niż 1 bez doklejania
`.Select(i => ...)`. Chcesz ciąg `double` co 0.5, albo ciąg malejący co 3 — piszesz
własną pętlę `for` albo generator `IEnumerable<T>` ręcznie.

### ✨ Co się zmieniło
.NET 10 dodaje do `System.Linq.Enumerable`:
- `Sequence<T>(T start, T endInclusive, T step)` — ciąg **skończony**, od `start` do
  `endInclusive` **włącznie**, z krokiem `step` (może być ujemny — wtedy ciąg maleje).
- `InfiniteSequence<T>(T start, T step)` — ciąg **nieskończony**, do użycia zawsze z
  `Take`/`TakeWhile` (w przeciwnym razie program zawiśnie, enumerując w nieskończoność).

Obie metody są generyczne przez **generic math** (`INumber<T>` i pokrewne interfejsy z
`System.Numerics`), więc działają nie tylko na `int`, ale też na `double`, `decimal`,
własnych typach liczbowych itd. — nie tylko na typach wspieranych explicite jak w
`Range`. Sprawdzone empirycznie: **nie istnieją w .NET 9** — na `net9.0`
`Enumerable.Sequence(...)` daje `CS0117` (dowód niżej).

```csharp
// Rosnąco, krok 2:
IEnumerable<int> rosnaco = Enumerable.Sequence(1, 10, 2);     // 1,3,5,7,9

// Malejąco (krok ujemny):
IEnumerable<int> malejaco = Enumerable.Sequence(10, 1, -3);   // 10,7,4,1

// Generic math - double, nie tylko int:
IEnumerable<double> ulamkowy = Enumerable.Sequence(1.5, 3.5, 0.5); // 1.5,2,2.5,3,3.5

// Nieskończony, zawsze z Take/TakeWhile:
IEnumerable<int> co5 = Enumerable.InfiniteSequence(0, 5).Take(5);  // 0,5,10,15,20
```

### 🖥️ Prawdziwy output (`dotnet run --project linq-sequence`, ta maszyna)
```
--- 2. Enumerable.Sequence<T>(start, endInclusive, step) ---
Sequence(1, 10, 2): 1,3,5,7,9
Sequence(10, 1, -3): 10,7,4,1
Sequence(1.5, 3.5, 0.5): 1.5,2,2.5,3,3.5

--- 3. Enumerable.InfiniteSequence<T>(start, step) + Take/TakeWhile ---
InfiniteSequence(0, 5).Take(5): 0,5,10,15,20
InfiniteSequence(1, 3).TakeWhile(x < 20): 1,4,7,10,13,16,19

--- 4. Praktyczny przyklad: offsety stron do paginacji API ---
offsety stron (total=95, pageSize=20): 0,20,40,60,80
```

### 🔬 Dowód „przed i po" (target `net9.0`)
```
error CS0117: 'Enumerable' does not contain a definition for 'Sequence'
```

### 💡 Co to zmienia w praktyce
- Generowanie offsetów do paginacji (`Sequence(0, total - 1, pageSize)`), siatek liczb do
  testów parametryzowanych, dat co N dni (po skonwertowaniu na typ liczbowy) — wszystko
  to bez ręcznej pętli `for` albo `Range().Select(...)`.
- Jedna metoda obsługuje zarówno rosnące, jak i malejące ciągi — kierunek wynika z
  **znaku** `step`, nie z osobnego parametru czy przeciążenia.
- `InfiniteSequence` to czytelniejszy odpowiednik ręcznie pisanego
  `while (true) { yield return x; x += step; }` — z tym samym ryzykiem (nieskończona
  pętla), jeśli zapomnisz `Take`/`TakeWhile`.

### ⚠️ Haczyk — walidacja argumentów jest EAGER, nie leniwa jak reszta LINQ
Zmierzone realnie (sekcja 5 w kodzie): większość LINQ (`Select`, `Where`, a nawet
wczorajszy-w-tej-rubryce `Shuffle`) sprawdza argumenty w locie, ale **treść** generowana
jest leniwie — dopiero przy `MoveNext()`. `Enumerable.Sequence` jest inne: **samo
wywołanie** `Enumerable.Sequence(1, 5, 0)` (krok zero) rzuca
`ArgumentOutOfRangeException` **natychmiast**, zanim jakikolwiek `foreach` czy `.Take()`
dotknie wyniku — nie trzeba nawet zacząć enumerować. To samo dotyczy złego kierunku:
`Enumerable.Sequence(10, 1, 1)` (start większy od `endInclusive`, ale krok dodatni) też
rzuca eagerly, zamiast po cichu zwrócić pusty ciąg. Dla kogoś, kto przyzwyczaił się, że
"LINQ nigdy nic nie robi, dopóki go nie zapytasz" (patrz wydanie #7: `Shuffle` losuje na
nowo przy **każdej** enumeracji, bo jest leniwe) — `Sequence` jest wyjątkiem od tej
reguły i warto to mieć w głowie przy `try/catch` wokół kodu, który go woła.

**Kod:** [`code/linq-sequence/`](code/linq-sequence/), dowód `CS0117`:
[`code/compat-check/`](code/compat-check/)

---

## 2️⃣ `MemoryExtensions` z `IEqualityComparer<T>` — Span przeszukiwany po SWOICH zasadach

### 😤 Problem
`ReadOnlySpan<char>`/`ReadOnlySpan<byte>` od `.NET 2.1`/`.NET 6` mają `IndexOf`,
`Contains`, `StartsWith` itd., ale do tej pory jedyny sposób na "wyszukiwanie
niewrażliwe na wielkość liter" ograniczał się do `char`/`string` z parametrem
`StringComparison` (np. `span.IndexOf(inny, StringComparison.OrdinalIgnoreCase)`). Jeśli
Twój span to `ReadOnlySpan<byte>` (surowe dane z socketu, bufora sieciowego) albo
`ReadOnlySpan<T>` jakiegokolwiek innego typu z własną logiką porównania — nie miałeś
opcji. Jedynym wyjściem było skopiowanie danych do `string`/tablicy i porównywanie tam,
tracąc cały sens używania `Span<T>` (zero alokacji, operowanie na buforze "na miejscu").

### ✨ Co się zmieniło
.NET 10 dodaje w `System.MemoryExtensions` nowe przeciążenia generyczne po `T`:
`IndexOf`, `Contains` (dla pojedynczego elementu), `StartsWith`, `EndsWith`, `Count` —
każde z dodatkowym parametrem `IEqualityComparer<T>`. To nie jest to samo co
`StringComparison`: `StringComparison` działa tylko dla `char`, a nowe przeciążenia
działają dla **dowolnego** `T` — `byte`, własny `struct`, cokolwiek, z dowolną logiką
równości, jaką sam zdefiniujesz. Sprawdzone empirycznie: **nie istnieją w .NET 9** — na
`net9.0` próba użycia komparatora w `IndexOf` na `ReadOnlySpan<char>` daje `CS1503`
(kompilator próbuje dopasować go do starego parametru `StringComparison` i się myli —
dowód niżej).

```csharp
// Case-insensitive bez kopiowania do string:
ReadOnlySpan<char> tekst = "Hello World, wonderful World";
int idx = tekst.IndexOf("world", OrdinalIgnoreCaseCharComparer.Instance); // 6

// Ten sam mechanizm na BAJTACH - np. naglowek HTTP prosto z bufora sieciowego:
ReadOnlySpan<byte> naglowek = "Content-Type: application/json"u8;
int idxBajty = naglowek.IndexOf("content-type"u8, AsciiCaseInsensitiveByteComparer.Instance); // 0

class OrdinalIgnoreCaseCharComparer : IEqualityComparer<char>
{
    public static readonly OrdinalIgnoreCaseCharComparer Instance = new();
    public bool Equals(char x, char y) => char.ToUpperInvariant(x) == char.ToUpperInvariant(y);
    public int GetHashCode(char obj) => char.ToUpperInvariant(obj).GetHashCode();
}
```

### 🖥️ Prawdziwy output (`dotnet run --project span-comparer-search`, ta maszyna)
```
--- 1. Problem: domyslne IndexOf na Span<char> to ORDINAL, bez uwzgledniania wielkosci liter ---
tekst.IndexOf("world") [domyslnie, ordinal]: -1

--- 2. .NET 10: IndexOf/Contains/StartsWith z IEqualityComparer<T> - bez kopiowania do string ---
tekst.IndexOf("world", OrdinalIgnoreCaseCharComparer): 6
tekst.Contains('w', ci): True
tekst.StartsWith("HELLO", ci): True
tekst.EndsWith("WORLD", ci): True
tekst.Count('o', ci) (liczy 'o' i 'O'): 4

--- 3. Kluczowa roznica vs StringComparison: dziala na DOWOLNYM T, nie tylko char/string ---
surowyNaglowek (bajty): "Content-Type: application/json; charset=utf-8"
IndexOf("content-type"u8) [domyslnie, ordinal]: -1
IndexOf("content-type"u8, AsciiCaseInsensitiveByteComparer): 0
IndexOf("APPLICATION/JSON"u8, ci) >= 0: True

--- 4. Przypadek 'nie tylko case-insensitivity': wlasna logika rownosci ---
identyfikatory.IndexOf("pole_0", AnyDigitEqualsAnyDigitComparer): 0
```

### 🔬 Dowód „przed i po" (target `net9.0`)
```
error CS1503: Argument 3: cannot convert from 'OrdinalIgnoreCaseCharComparer' to 'System.StringComparison'
```

### 💡 Co to zmienia w praktyce
- Parsowanie protokołów tekstowych/binarnych (nagłówki HTTP, komendy, surowe bufory z
  sieci) może teraz robić dopasowanie niewrażliwe na wielkość liter **bezpośrednio na
  bajtach**, bez alokowania `string` tylko po to, żeby skorzystać ze `StringComparison`.
- Komparator może implementować **dowolną** logikę, nie tylko różne warianty "ignoruj
  wielkość liter" — w kodzie demo komparator traktujący każdą cyfrę jako równą każdej
  innej cyfrze pozwala znaleźć wzorzec `"pole_<dowolna cyfra>"` jednym `IndexOf`, bez
  wyrażenia regularnego.
- To domyka temat ze starszego wydania (#4: first-class Span) — Span przestaje być
  "tablica, która tylko czyta i kopiuje", a staje się pełnoprawnym miejscem do
  przeszukiwania z logiką biznesową, nie tylko porównaniem bajt-po-bajcie.

### ⚠️ Haczyk — `Contains` z komparatorem działa tylko dla POJEDYNCZEGO elementu, nie dla pod-ciągu
Zmierzone realnie przy pisaniu kodu (patrz komentarz w `span-comparer-search/Program.cs`):
intuicyjnie można by oczekiwać, że skoro `IndexOf(ReadOnlySpan<T>, ReadOnlySpan<T>,
IEqualityComparer<T>)` istnieje (szukanie pod-ciągu z komparatorem), to analogiczny
`Contains(ReadOnlySpan<T>, ReadOnlySpan<T>, IEqualityComparer<T>)` też będzie dostępny.
Nie jest — próba kompilacji takiego wywołania daje realny błąd kompilatora: `CS1929:
'ReadOnlySpan<byte>' does not contain a definition for 'Contains' and the best extension
method overload 'MemoryExtensions.Contains(ReadOnlySpan<char>, ReadOnlySpan<char>,
StringComparison)' requires a receiver of type 'System.ReadOnlySpan<char>'`.
Przeciążenie `Contains` z komparatorem istnieje **tylko** dla pojedynczego elementu `T`
(`Contains(ReadOnlySpan<T>, T, IEqualityComparer<T>)`). Żeby sprawdzić "czy pod-ciąg
występuje" z własnym komparatorem, trzeba użyć `IndexOf(...) >= 0` zamiast `Contains`.

**Kod:** [`code/span-comparer-search/`](code/span-comparer-search/), dowód `CS1503`/`CS1929`:
[`code/compat-check/`](code/compat-check/)

---

## 📎 Jak zweryfikowano „co jest nowe w .NET 10"

Tak jak w wydaniu #7: zamiast polegać na pamięci, w tej sesji porównano realną
powierzchnię API zainstalowanych runtime'ów `Microsoft.NETCore.App` **9.0.18** i
**10.0.11** przez refleksję (`System.Reflection.MetadataLoadContext`,
`PathAssemblyResolver` wskazujący katalogi `shared/Microsoft.NETCore.App/<wersja>`,
różnica zbiorów `GetExportedTypes()`/`GetMembers()` dla `System.Linq.dll`,
`System.Text.Json.dll`, `System.Private.CoreLib.dll`, `System.Collections.dll` i kilku
innych). Diff potwierdził m.in. `Enumerable.Sequence`/`InfiniteSequence`, kilkadziesiąt
nowych przeciążeń `MemoryExtensions` z `IEqualityComparer<T>`/`IComparer<T>`, a także —
co ważne dla uniknięcia fikcji — **zero** nowych publicznych sygnatur w
`System.Text.RegularExpressions.dll` między .NET 9 a .NET 10: source-generated regex
(`GeneratedRegexAttribute`) **nie jest** nowością .NET 10 (istnieje od .NET 7), więc
świadomie pominięto ten temat, mimo że sugerowała go pierwotna lista tematów do
wydania. Każda z dwóch opisanych dziś funkcji została potwierdzona osobno realnym
błędem kompilatora na `net9.0` (`CS0117`, `CS1503`/`CS1929`). Skrypt porównawczy
(projekt tymczasowy z pakietem `System.Reflection.MetadataLoadContext`) nie wszedł do
repo — uruchamiany poza katalogiem tego wydania, potem usunięty.

---

## 📎 Jak uruchomić
Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #9 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
