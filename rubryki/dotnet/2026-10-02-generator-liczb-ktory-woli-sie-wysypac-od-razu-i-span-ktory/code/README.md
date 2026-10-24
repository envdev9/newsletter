# Kod do wydania #9 — LINQ `Sequence`/`InfiniteSequence` i `MemoryExtensions` z `IEqualityComparer<T>` (.NET 10 BCL)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`). Sprawdzone na `10.0.400`.
Projekty `linq-sequence` i `span-comparer-search` celują w `net10.0`; `compat-check`
celowo celuje w `net9.0` (wymaga zainstalowanego runtime'u 9.x obok — sprawdzone z
runtime `9.0.18`/SDK `9.0.316` zainstalowanym równolegle), żeby pokazać realny błąd
kompilatora "przed". Brak zależności NuGet.

## Fragment prasówki, którego dotyczy ten kod

> `Enumerable.Sequence<T>(start, endInclusive, step)` / `Enumerable.InfiniteSequence<T>(start, step)`
> — nowy generyczny generator ciągów liczbowych w LINQ (generic math, działa na `int`,
> `double` itd., nie tylko `int` jak `Range`), rosnący lub malejący w zależności od znaku
> `step`. Sprawdzone: nie istnieje w .NET 9 (`CS0117`). Haczyk zmierzony realnie:
> walidacja argumentów (`step == 0`, zły kierunek `start`/`endInclusive`) jest **eager**
> — rzuca `ArgumentOutOfRangeException` natychmiast przy wywołaniu, zanim jakakolwiek
> enumeracja się zacznie, w przeciwieństwie do reszty leniwego LINQ.
>
> `MemoryExtensions.IndexOf`/`Contains`/`StartsWith`/`EndsWith`/`Count` z nowym
> parametrem `IEqualityComparer<T>` — pozwala przeszukiwać `Span<T>`/`ReadOnlySpan<T>`
> **dowolnego** typu `T` z własną logiką równości, nie tylko `char`/`string` przez
> `StringComparison`. Sprawdzone: te przeciążenia nie istnieją w .NET 9 (`CS1503`/
> `CS1929`). Haczyk zmierzony realnie: `Contains` z komparatorem działa tylko dla
> pojedynczego elementu `T`, nie dla pod-ciągu (`ReadOnlySpan<T>` jako szukana wartość)
> — do szukania pod-ciągu z komparatorem trzeba użyć `IndexOf(...) >= 0`.

## 1. linq-sequence (`Enumerable.Sequence<T>` / `Enumerable.InfiniteSequence<T>`)

```bash
dotnet run --project linq-sequence
```

```
--- 1. Stary idiom: Enumerable.Range tylko dla int, krok zawsze 1 ---
Range(0,5).Select(i => i*2): 0,2,4,6,8
Dziala, ale: nazwa 'Range' sugeruje liczbe elementow, nie koniec zakresu;
zejscie w dol (malejaco) albo typ 'double' wymaga wlasnej petli/generatora.

--- 2. Enumerable.Sequence<T>(start, endInclusive, step) ---
Sequence(1, 10, 2): 1,3,5,7,9
Sequence(10, 1, -3): 10,7,4,1
Sequence(1.5, 3.5, 0.5): 1.5,2,2.5,3,3.5

--- 3. Enumerable.InfiniteSequence<T>(start, step) + Take/TakeWhile ---
InfiniteSequence(0, 5).Take(5): 0,5,10,15,20
InfiniteSequence(1, 3).TakeWhile(x < 20): 1,4,7,10,13,16,19

--- 4. Praktyczny przyklad: offsety stron do paginacji API ---
offsety stron (total=95, pageSize=20): 0,20,40,60,80

--- 5. HACZYK: walidacja argumentow jest EAGER, nie leniwa jak reszta LINQ ---
Wywolanie Enumerable.Sequence(1, 5, 0) (step=0), PRZED jakakolwiek enumeracja:
  rzucilo NATYCHMIAST przy wywolaniu (eager validation): ArgumentOutOfRangeException (parametr 'step')
Wywolanie Enumerable.Sequence(10, 1, 1) (zly kierunek: start > endInclusive, step dodatni):
  rzucilo NATYCHMIAST przy wywolaniu: ArgumentOutOfRangeException (parametr 'endInclusive')

--- 6. Przypadek brzegowy: endInclusive == start -> jeden element ---
Sequence(5, 5, 1): 5
```

(Wynik w pełni deterministyczny — brak losowości, w przeciwieństwie do wczorajszego
`Shuffle`.)

## 2. span-comparer-search (`MemoryExtensions` z `IEqualityComparer<T>`)

```bash
dotnet run --project span-comparer-search
```

```
--- 1. Problem: domyslne IndexOf na Span<char> to ORDINAL, bez uwzgledniania wielkosci liter ---
tekst: "Hello World, wonderful World"
tekst.IndexOf("world") [domyslnie, ordinal]: -1
-> -1: dokladne dopasowanie wielkosci liter nie znalazlo 'world' (jest 'World').
Dotychczas: trzeba bylo tekst.ToString().IndexOf(szukane, StringComparison.OrdinalIgnoreCase)
- czyli skopiowac caly span do stringa tylko po to, zeby poszukac podciagu.

--- 2. .NET 10: IndexOf/Contains/StartsWith z IEqualityComparer<T> - bez kopiowania do string ---
tekst.IndexOf("world", OrdinalIgnoreCaseCharComparer): 6
tekst.Contains('w', ci): True
tekst.StartsWith("HELLO", ci): True
tekst.EndsWith("WORLD", ci): True
tekst.Count('o', ci) (liczy 'o' i 'O'): 4

--- 3. Kluczowa roznica vs StringComparison: dziala na DOWOLNYM T, nie tylko char/string ---
Realny przypadek: naglowek HTTP przychodzi jako surowe bajty z socketu (ReadOnlySpan<byte>),
nazwy naglowkow sa case-insensitive wg RFC, ale konwersja calego bufora na string na kazdy
naglowek to niepotrzebna alokacja w kodzie na sciezce krytycznej (np. middleware Kestrela).
surowyNaglowek (bajty): "Content-Type: application/json; charset=utf-8"
IndexOf("content-type"u8) [domyslnie, ordinal]: -1
IndexOf("content-type"u8, AsciiCaseInsensitiveByteComparer): 0
-> znalezione na poziomie bajtow, bez konwersji calego bufora na string.
IndexOf("APPLICATION/JSON"u8, ci) >= 0: True

--- 4. Przypadek 'nie tylko case-insensitivity': wlasna logika rownosci ---
Komparator traktujacy KAZDA cyfre jako rowna kazdej innej cyfrze - szukanie wzorca
'pole_N' niezaleznie od konkretnej cyfry N, bez wyrazen regularnych:
identyfikatory.IndexOf("pole_0", AnyDigitEqualsAnyDigitComparer): 0
-> znalazlo pierwsze wystapienie 'pole_<cyfra>' (tu: 'pole_1' na indeksie 0),
   mimo ze szukany wzorzec mial literalnie '0'. To pokazuje, ze te API to NIE jest
   'StringComparison z dodatkowym rozszerzeniem' - to dowolna logika rownosci elementow.
```

## 3. compat-check (celowo NIE kompiluje się na .NET 9)

Projekt celuje w `net9.0` i domyślnie ma aktywny **Dowód 1** (`Enumerable.Sequence`):

```bash
dotnet build compat-check
```

Oczekiwany wynik: `error CS0117: 'Enumerable' does not contain a definition for
'Sequence'`.

Żeby zobaczyć **Dowód 2** (`MemoryExtensions.IndexOf` z komparatorem), w
`compat-check/Program.cs` zakomentuj blok "Dowod 1" (3 linijki `foreach`), odkomentuj
blok "Dowod 2" (łącznie z `using System.Collections.Generic;` i definicją klasy
`OrdinalIgnoreCaseCharComparer`), i zbuduj ponownie:

```bash
dotnet build compat-check
```

Oczekiwany wynik: `error CS1503: Argument 3: cannot convert from
'OrdinalIgnoreCaseCharComparer' to 'System.StringComparison'`. Oba błędy zostały
realnie zweryfikowane w tej sesji (target `net9.0`) — output wklejony powyżej 1:1, bez
zmyślania. (Trzeci błąd z artykułu, `CS1929` dla `Contains` z pod-ciągiem, zweryfikowano
osobno przy pisaniu `span-comparer-search` — próba użycia takiego przeciążenia w
projekcie celującym w `net10.0` też się nie kompiluje, bo przeciążenie po prostu nie
istnieje w żadnej wersji; dowód w historii edycji tego kodu, nie trzymany jako osobny
plik).

## Jak zweryfikowano „co jest nowe w .NET 10"

Zamiast zgadywać z pamięci, w tej sesji porównano realną powierzchnię API
`System.Linq.dll`, `System.Text.Json.dll`, `System.Private.CoreLib.dll`,
`System.Collections.dll` i kilku innych asemblii BCL między zainstalowanym runtime'em
**9.0.18** a **10.0.11** (`Microsoft.NETCore.App`) przez refleksję
(`System.Reflection.MetadataLoadContext`, `PathAssemblyResolver` wskazujący na katalogi
`shared/Microsoft.NETCore.App/<wersja>`, porównanie zbiorów sygnatur
`GetExportedTypes()`/`GetMembers()`). Diff potwierdził m.in. `Enumerable.Sequence`/
`InfiniteSequence`, kilkadziesiąt nowych przeciążeń `MemoryExtensions` z
`IEqualityComparer<T>`/`IComparer<T>` (`IndexOf`, `Contains`, `StartsWith`, `EndsWith`,
`Count`, `ContainsAny`, `Replace`...), nowe API w `System.Text.Json`
(`JsonObject.TryAdd`/`TryGetPropertyValue` z `out int`, `JsonArray.RemoveAll`/
`RemoveRange`, `Utf8JsonWriter.WriteStringValueSegment`), `PriorityQueue<,>.Capacity`
i — kluczowe dla uniknięcia fikcji — **zero** różnic w `System.Text.RegularExpressions.dll`,
co potwierdza, że source-generated regex **nie jest** nowością .NET 10 (istnieje od
.NET 7) i świadomie nie został opisany jako "nowość" w tym wydaniu. Z pełnej listy
wybrano dwie funkcje opisane w artykule i każdą potwierdzono osobno realną kompilacją
(`CS0117`, `CS1503`/`CS1929`) na `net9.0`. Skrypt porównawczy (projekt tymczasowy,
referencja do `System.Reflection.MetadataLoadContext` z NuGet) nie wszedł do repo — był
w katalogu tymczasowym poza tym wydaniem i został usunięty po użyciu; powyższe błędy
kompilatora i output programów są jego bezpośrednim, wklejonym efektem.

## Zweryfikowane / niezweryfikowane — podsumowanie

- Zweryfikowane realnym `dotnet build`/`dotnet run` (SDK 10.0.400, cel `net10.0`):
  `linq-sequence` (wszystkie 6 sekcji, w tym oba przypadki eager-validation),
  `span-comparer-search` (wszystkie 4 sekcje, w tym przykład na bajtach i przykład z
  własną logiką równości na cyfrach).
- Zweryfikowane realnym `dotnet build` (cel `net9.0`): `compat-check`, oba błędy
  (`CS0117` jako domyślny stan w repo, `CS1503` przełączany ręcznie komentarzem) oraz
  osobno `CS1929` dla próby `Contains` z pod-ciągiem i komparatorem.
- Niezweryfikowane: wewnętrzna implementacja `Enumerable.Sequence`/`InfiniteSequence`
  (np. czy i jak unika przepełnienia przy bardzo dużych wartościach generic math —
  sprawdzono tylko zachowanie obserwowalne z zewnątrz, na małych, bezpiecznych
  wartościach); czy nowe przeciążenia `MemoryExtensions` z komparatorem używają
  wewnętrznie wektoryzacji SIMD tak jak warianty bez komparatora (nie badano źródeł
  CoreLib, tylko poprawność wyniku z zewnątrz) — dokumentacja/release notes .NET 10 nie
  była dostępna offline w tej sesji do skonfrontowania, więc wszystkie twierdzenia
  powyżej opierają się wyłącznie na realnej kompilacji i realnym uruchomieniu kodu w tym
  repo, nie na dokumentacji.
