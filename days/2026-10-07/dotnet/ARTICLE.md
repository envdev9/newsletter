<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #14 — 7 października 2026

![.NET](https://img.shields.io/badge/.NET-10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![BCL](https://img.shields.io/badge/BCL-Span%20%2B%20LINQ-blue?style=for-the-badge)

## Sanityzacja bez alokacji i LINQ na `IAsyncEnumerable` — prosto z BCL, bez NuGeta

</div>

---

> _"Sequence contains no elements"_ — ten sam komunikat, co w klasycznym LINQ, wyrzuca
> `FirstAsync()` na pustym strumieniu asynchronicznym. Zmierzone realnie w tej sesji.
> Dziś LINQ dla `IAsyncEnumerable<T>` mieszka w samym .NET 10 — a dziewięć
> `string.Replace` pod rząd zjada 288 MB tam, gdzie jedno `ReplaceAny` zjada zero.

Wydanie #13 zostawiło otwarty trop: `MemoryExtensions.CountAny`/`ReplaceAny`/
`ReplaceAnyExcept` z `SearchValues<T>`. Domykamy go jako funkcję 1. Funkcję 2 znaleźliśmy
empirycznie, poza listą z `STATE.md`: **LINQ na `IAsyncEnumerable<T>`** (`Where`, `Select`,
`ToListAsync`, `CountAsync`...) — wcześniej wymagało to osobnego pakietu NuGet. SDK .NET 11
nadal nie ma na tej maszynie (`dotnet --list-sdks`: 8.0.422, 8.0.425, 9.0.316, 10.0.400),
więc zostajemy przy .NET 10. Kod w [`code/`](code/).

| # | Funkcja | Namespace | Status |
|---|---------|-----------|--------|
| 1️⃣ | `MemoryExtensions.CountAny` / `ReplaceAny` / `ReplaceAnyExcept` z `SearchValues<T>` | `System` | ✅ w pełni zweryfikowane |
| 2️⃣ | LINQ na `IAsyncEnumerable<T>` (`System.Linq.AsyncEnumerable`) | `System.Linq` | ✅ zweryfikowane (podzbiór operatorów) |

---

## 1️⃣ `CountAny` / `ReplaceAny` / `ReplaceAnyExcept` — operacje na zbiorze znaków bez pętli

### 😤 Problem
`SearchValues<T>` (od .NET 8) daje zwektoryzowane wyszukiwanie zbioru znaków:
`IndexOfAny`, `ContainsAny`, `IndexOfAnyExcept` (te trzy kompilują się na `net9.0` — dowód
niżej, to NIE nowość). Ale gdy chciałeś **policzyć** trafienia albo **podmienić** je na
jeden znak (sanityzacja nazwy pliku, maskowanie), zostawały: ręczna pętla z
`values.Contains(c)` albo łańcuch `string.Replace` — po jednym na każdy zabroniony znak,
z kopią całego stringa za każdym razem.

### ✨ Co się zmieniło
.NET 10 dodaje na `MemoryExtensions` (sprawdzone kompilacją):
- `CountAny(this ReadOnlySpan<T>, SearchValues<T>)` — liczba trafień,
- `ReplaceAny(this Span<T>, SearchValues<T>, T newValue)` — podmiana w miejscu,
- `ReplaceAny(this ReadOnlySpan<T>, Span<T> destination, SearchValues<T>, T newValue)` —
  źródło → bufor docelowy,
- `ReplaceAnyExcept` — to samo, ale dla elementów **spoza** zbioru (biała lista).

```csharp
SearchValues<char> zabronione = SearchValues.Create("\\/:*?\"<>|");
char[] nazwa = "raport: Q3/Q4 *final*?.txt".ToCharArray();
nazwa.AsSpan().ReplaceAny(zabronione, '_');          // "raport_ Q3_Q4 _final__.txt"

SearchValues<char> dozwolone = SearchValues.Create("abc...xyzABC...XYZ0123456789.-");
slug.AsSpan().ReplaceAnyExcept(dozwolone, '_');      // biała lista
```

### 🖥️ Prawdziwy output (`dotnet run -c Release --project searchvalues-any`, ta maszyna)
```
ReplaceAny (src->dst) : raport_ Q3_Q4 _final__.txt
ReplaceAny (w miejscu): raport_ Q3_Q4 _final__.txt
ReplaceAnyExcept       : za_____g__l__ja___2026_.txt

--- 3. Pomiar: 16M znakow, ReplaceAny vs petla vs lancuch string.Replace (Release) ---
CountAny          :   4195786 trafien, alokacje 0 B
petla + Contains  :   4195786 trafien, alokacje 0 B (wynik zgodny: True)
ReplaceAny        : alokacje 0 B
9x string.Replace : alokacje 288 MB (wynik zgodny: True)
```

### 🔬 Dowód „przed i po" (target `net9.0`, SDK 9.0.316)
```
error CS1061: 'Span<char>' does not contain a definition for 'CountAny' ...
error CS1061: 'Span<char>' does not contain a definition for 'ReplaceAny' ...
error CS1061: 'Span<char>' does not contain a definition for 'ReplaceAnyExcept' ...
error CS1061: 'ReadOnlySpan<char>' does not contain a definition for 'ReplaceAny' ...
```
W tym samym pliku `IndexOfAny`/`ContainsAny`/`IndexOfAnyExcept` z `SearchValues` kompilują
się bez błędu. Diffu refleksyjnego w tej sesji nie powtarzano — dowodem jest kompilacja.

### 💡 Co to zmienia w praktyce
- **Zero alokacji**: `ReplaceAny` na 16 M znaków — 0 B; dziewięć `string.Replace` —
  288 MB (zmierzone, wynik identyczny co do znaku).
- **Czas**: w tym pomiarze `ReplaceAny` ~99 ms vs ~609 ms dla łańcucha `Replace`.
  `CountAny` vs ręczna pętla z `Contains`: 132 vs 149 ms — różnica **mała**; pętla z
  `SearchValues.Contains` jest już szybka. Główna wartość `CountAny` to czytelność.
  Uwaga: dwa uruchomienia dały różne czasy bezwzględne (CountAny 70 vs 132 ms), więc
  traktuj je jako rząd wielkości, nie benchmark.
- Działa także na bajtach (`SearchValues<byte>`, np. surowy UTF-8) — zweryfikowane na
  prostym przykładzie z separatorami.
- Brak `CountAnyExcept`: liczbę „spoza zbioru" dostaniesz jako `Length - CountAny`.

### ⚠️ Haczyk A — `destination` krótszy niż `source` rzuca
```
RZUCILO ArgumentException: "Destination is too short. (Parameter 'destination')"
```
Wariant źródło → cel wymaga bufora o co najmniej tej samej długości.

### ⚠️ Haczyk B — działa na jednostkach UTF-16, nie na znakach
Emoji `😀` to dwie jednostki `char`. `ReplaceAnyExcept` z białą listą zamienia **każdą**
osobno: `"a😀b"` → `"a__b"` (dwa podkreślniki, zmierzone), a `Rune` jest tu jeden.
Podobnie `"zażółć"` → każda polska litera poza ASCII staje się `_`. Chcesz zachować
polskie litery — dodaj je do białej listy.

### ⚠️ Haczyk C — pusty zbiór i `ReplaceAnyExcept`
`CountAny` z pustym zbiorem = 0 (zmierzone), ale `ReplaceAnyExcept` z pustym zbiorem
zamienia **wszystko** (`"abc"` → `"###"`). Zbiór budowany z konfiguracji, który
przypadkiem wyszedł pusty, wyczyści cały tekst — bez wyjątku.

**Kod:** [`code/searchvalues-any/`](code/searchvalues-any/), dowód `CS1061`×4:
[`code/compat-check/`](code/compat-check/)

---

## 2️⃣ LINQ na `IAsyncEnumerable<T>` w BCL — bez `System.Linq.Async`

### 😤 Problem
`IAsyncEnumerable<T>` i `await foreach` są od C# 8, ale zapytania typu
`strumien.Where(...).Select(...).ToListAsync()` wymagały zewnętrznego pakietu
(`System.Linq.Async`). Bez niego: ręczna pętla `await foreach` z `List<T>`.

### ✨ Co się zmieniło
W .NET 10 operatory LINQ dla `IAsyncEnumerable<T>` są częścią platformy (`System.Linq`,
bez żadnego `PackageReference` w naszym `.csproj`). Zweryfikowane `dotnet run`:
`Where`, `Select`, `Take`, `Order`, `ToListAsync`, `CountAsync`, `SumAsync`, `MaxAsync`,
`FirstAsync`, `FirstOrDefaultAsync`, `ToAsyncEnumerable` (z `IEnumerable<T>`) oraz
`Where` z asynchronicznym predykatem `Func<T, CancellationToken, ValueTask<bool>>`.
Pełnej listy operatorów nie sprawdzano.

```csharp
var wynik = await Zrodlo(10)
    .Where(x => x % 2 == 0)
    .Select(x => x * x)
    .ToListAsync();                       // [4, 16, 36, 64, 100]

var dostepne = await Zrodlo(6).Where(CzyDostepny).ToListAsync();  // async predykat
```

### 🖥️ Prawdziwy output (`dotnet run --project asyncenum-linq`, ta maszyna)
```
Where+Select+ToListAsync: [4, 16, 36, 64, 100]
CountAsync = 3
SumAsync   = 15
MaxAsync   = 5
zapytanie zbudowane - nic sie jeszcze nie wykonalo (brak logu 'start' powyzej)
   [E] start
   [E] dispose (finally), oddanych elementow: 2
wynik: [1, 2]
dostepne: [1, 2, 4, 5]
Order: [1, 2, 3]
```

### 🔬 Dowód „przed i po" (target `net9.0`)
```
error CS0411: The type arguments for method 'ImmutableArrayExtensions.Where<T>(ImmutableArray<T>, Func<T, bool>)' cannot be inferred ...
error CS1061: 'IAsyncEnumerable<int>' does not contain a definition for 'CountAsync' ...
```
Uwaga na mylący błąd: `Where` na `net9.0` nie daje `CS1061`, tylko `CS0411` — kompilator
próbuje dopasować jedyny `Where` w zasięgu (z `System.Collections.Immutable`), więc
komunikat sugeruje problem z wnioskowaniem typów, a nie brak metody.

### 💡 Co to zmienia w praktyce
- Przetwarzanie strumieni z bazy/HTTP/kolejki (`IAsyncEnumerable` z EF Core, `await foreach`)
  w stylu LINQ bez dodatkowej zależności.
- `Take(2)` na generatorze, który mógłby dać 100 elementów, zatrzymał go po **2** i
  uruchomił jego `finally` (zmierzone: „oddanych elementow: 2").
- Wyjątek z `Select` (na elemencie 3) wyszedł bez opakowania, a `finally` źródła
  wykonało się po drodze (zmierzone: „oddanych elementow: 3").

### ⚠️ Haczyk A — każda enumeracja startuje źródło od nowa
`var q = Zrodlo(2).Select(...)`; dwa `await q.CountAsync()` → dwa pełne przebiegi
(dwa logi `start`/`dispose`). Zapytanie jest leniwe i nie cachuje wyników; jeśli źródłem
jest zapytanie do bazy, zapłacisz dwa razy.

### ⚠️ Haczyk B — anulowanie: token z `ToListAsync(ct)` dociera do generatora
Z `CancellationTokenSource(5 ms)` na 1000-elementowym generatorze: wyjątek
`TaskCanceledException` (podklasa `OperationCanceledException`), a generator zdążył
oddać 1 element i wykonał `finally`. Liczba oddanych elementów zależy od czasu — w
kodzie jest niedeterministyczna. Jeśli łapiesz `OperationCanceledException`, łapiesz też to.

### ⚠️ Haczyk C — semantyka `First`/`FirstOrDefault` jak w klasycznym LINQ
`FirstAsync()` na pustym: `InvalidOperationException: "Sequence contains no elements"`;
`FirstOrDefaultAsync()` zwraca `0` (`default(int)`) — przy typach wartościowych nie
odróżnisz „pusto" od „zero".

**Kod:** [`code/asyncenum-linq/`](code/asyncenum-linq/), dowód `CS0411`/`CS1061`:
[`code/compat-check/`](code/compat-check/)

---

## 📎 Jak zweryfikowano
- `compat-check` na `net9.0` (SDK 9.0.316): dokładnie **6 błędów** (`CS1061`×5, `CS0411`×1);
  linie ze starym API (`IndexOfAny`, `ContainsAny`, `IndexOfAnyExcept`) kompilują się.
- Oba programy uruchomione `dotnet run` na SDK 10.0.400 (`searchvalues-any` w Release;
  alokacje z `GC.GetAllocatedBytesForCurrentThread`). Czasy zmierzone dwukrotnie wahały
  się ~2x między uruchomieniami (maszyna współdzielona) — wnioski o czasie tylko jakościowe.
- Funkcja 2 znaleziona przez przegląd kandydatów i potwierdzona kompilacją, **nie** przez
  pełny diff refleksyjny; w kodzie jest prawdziwy kod z BCL (żadnego `PackageReference`).
- **Niezweryfikowane:** pełna lista operatorów `System.Linq.AsyncEnumerable` (np. `GroupBy`,
  `Join`, `Chunk`), współpraca z EF Core `IAsyncEnumerable`, zachowanie `ReplaceAny` na
  nakładających się spanach, inne typy `T` niż `char`/`byte`, .NET 11 (brak SDK), wnętrze
  implementacji (wektoryzacja). Nie korzystano z dokumentacji online.
- Zostaje: kolejne nowości .NET 10 (inne API BCL) → .NET 11 gdy pojawi się SDK.

---

## 📎 Jak uruchomić
Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #14 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
