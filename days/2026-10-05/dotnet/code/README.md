# Kod do wydania #12 — `MemoryExtensions.SequenceCompareTo` z `IComparer<T>` i `JsonArray.RemoveAll`/`RemoveRange` (.NET 10 BCL)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`). Sprawdzone na `10.0.400`.
Projekty `span-ordering-compare` i `jsonarray-bulk-ops` celują w `net10.0`;
`compat-check` celowo celuje w `net9.0` (wymaga zainstalowanego SDK/runtime'u 9.x
obok — sprawdzone z SDK `9.0.316`/runtime `9.0.18` zainstalowanym równolegle), żeby
pokazać realny błąd kompilatora "przed". Brak zależności NuGet w projektach
demonstracyjnych.

## Fragment prasówki, którego dotyczy ten kod

> `MemoryExtensions.SequenceCompareTo<T>(ReadOnlySpan<T>, ReadOnlySpan<T>, IComparer<T>)`
> — nowy, **jedyny** nowy overload `IComparer<T>` w `MemoryExtensions` między .NET 9 a
> 10 (reszta nowości w tej klasie to `IEqualityComparer<T>`, opisane w poprzednim
> wydaniu). Pozwala porównywać/porządkować `Span<T>`/`ReadOnlySpan<T>` **dowolnego** `T`
> z własną logiką porządku, bez kopiowania do `string`/tablicy. Sprawdzone: nie istnieje
> w .NET 9 (`CS1501`). Haczyk zmierzony realnie: wynik to nie zawsze -1/0/1 (liczy się
> tylko znak), a różna długość sekwencji ma regułę prefiksu (krótszy ciąg będący
> prefiksem dłuższego jest "mniejszy"), tak jak w `string.CompareOrdinal`.
>
> `JsonArray.RemoveAll(predicate)` / `JsonArray.RemoveRange(index, count)` — masowe
> usuwanie elementów z mutowalnego DOM-u JSON-a (`System.Text.Json.Nodes.JsonArray`), z
> tą samą sygnaturą/ergonomią co `List<T>`. Wcześniej trzeba było pisać ręczną pętlę "od
> tyłu" z `RemoveAt(int)`. Sprawdzone: obie metody nie istnieją w .NET 9 (`CS1061`×2).
> Haczyki zmierzone realnie: (A) `RemoveAll` NIE jest null-safe — predykat bez
> `x is null` rzuca `NullReferenceException`, mimo że `JsonArray` może zawierać JSON
> `null`; (B) `RemoveRange` z `count` poza granicami rzuca `ArgumentException` (nie
> `ArgumentOutOfRangeException`), tak jak `List<T>.RemoveRange`.

## 1. span-ordering-compare (`MemoryExtensions.SequenceCompareTo<T>` z `IComparer<T>`)

```bash
dotnet run --project span-ordering-compare
```

```
--- 1. Problem: stary SequenceCompareTo ma TYLKO porzadek domyslny (ordinal dla byte) ---
"Header".SequenceCompareTo("header") [domyslnie, ordinal]: -32
-> wartosc != 0, bo 'H' (72) i 'h' (104) to dla bajtow/ordinal dwie rozne wartosci.
Dotychczas: zeby posortowac/porownac case-insensitive, trzeba bylo skopiowac do string.

--- 2. .NET 10: SequenceCompareTo<T> z IComparer<T> - wlasny porzadek, bez kopiowania ---
"Header".SequenceCompareTo("header", ci): 0
-> 0: wedlug wlasnego porzadku (ignorujac wielkosc liter) te dwa ciagi sa ROWNE.

--- 3. Praktyczny przyklad: sortowanie nazw naglowkow HTTP (surowe bajty) alfabetycznie, case-insensitive ---
Przed sortowaniem: content-type, Accept, AUTHORIZATION, accept-encoding
Po Array.Sort z komparatorem opartym na SequenceCompareTo: Accept, accept-encoding, AUTHORIZATION, content-type
-> alfabetycznie, ignorujac wielkosc liter, bez ani jednej konwersji na string do porownania.

--- 4. HACZYK A: rozna dlugosc -> regula prefiksu, jak w string.CompareOrdinal ---
"Head".SequenceCompareTo("Header"): -2
-> wartosc ujemna: krotszy ciag, bedacy prefiksem dluzszego, jest 'mniejszy' (tak jak w string).

--- 5. HACZYK B: wynik to NIE zawsze -1/0/1, liczy sie tylko ZNAK (umowa jak w IComparable) ---
Zmierzona realnie wartosc z sekcji 1 to -32, nie -1. To zgodne z kontraktem IComparer<T>/
IComparable<T> - liczy sie TYLKO znak (< 0, == 0, > 0), nigdy konkretna wartosc liczbowa.
```

(Wynik w pełni deterministyczny — bez losowości, bez zależności od kultury/locale,
czyste porównanie bajtowe wg własnego `IComparer<byte>`.)

## 2. jsonarray-bulk-ops (`JsonArray.RemoveAll` / `JsonArray.RemoveRange`)

```bash
dotnet run --project jsonarray-bulk-ops
```

```
--- 1. Problem: dotychczas JsonArray nie mial RemoveAll/RemoveRange, tylko RemoveAt(int) ---
Przed: [1,2,3,4,5,6]
Po recznej petli 'od tylu' (usun parzyste): [1,3,5]
-> dziala, ale latwo o blad (iteracja w przod + RemoveAt = pomijanie elementow).

--- 2. .NET 10: JsonArray.RemoveAll(predicate) - jedna linia, bez recznej petli ---
RemoveAll(parzyste) usunieto: 3, zostalo: [1,3,5]

--- 3. .NET 10: JsonArray.RemoveRange(index, count) - usuwanie SPOJNEGO wycinka ---
Przed: [10,20,30,40,50,60,70]
Po RemoveRange(2, 3): [10,20,60,70]

--- 4. Praktyczny przyklad: odfiltrowanie nieprawidlowych wpisow z JSON-a zewnetrznego API ---
Surowa odpowiedz: [{"id":1,"status":"ok"},null,{"id":2,"status":"error"},{"id":3,"status":"ok"},null]
RemoveAll (null-safe predicate) usunieto: 3, zostalo: [{"id":1,"status":"ok"},{"id":3,"status":"ok"}]

--- 5. HACZYK A: RemoveAll NIE jest null-safe - predicate bez sprawdzenia 'x is null' rzuca NRE ---
Zmierzone realnie: RZUCILO NullReferenceException: "Object reference not set to an instance of an object."

--- 6. HACZYK B: RemoveRange z count wychodzacym poza granice rzuca ArgumentException ---
Zmierzone realnie: RZUCILO ArgumentException: "Offset and length were out of bounds for the array or count is greater than the number of elements from index to the end of the source collection."
```

## 3. compat-check (celowo NIE kompiluje się na .NET 9)

Projekt celuje w `net9.0` i domyślnie ma aktywny **Dowód 1**
(`MemoryExtensions.SequenceCompareTo` z `IComparer<T>`):

```bash
dotnet build compat-check
```

Oczekiwany wynik: `error CS1501: No overload for method 'SequenceCompareTo' takes 2
arguments`.

Żeby zobaczyć **Dowód 2** (`JsonArray.RemoveAll`/`RemoveRange`), w
`compat-check/Program.cs` zakomentuj blok "DOWOD 1" (4 linijki), odkomentuj blok
"DOWOD 2" (4 linijki, łącznie z `using System.Text.Json.Nodes;` już obecnym na górze
pliku), i zbuduj ponownie:

```bash
dotnet build compat-check
```

Oczekiwany wynik: dwa błędy `error CS1061` — jeden dla `RemoveAll`, jeden dla
`RemoveRange`. Oba błędy (Dowód 1 i Dowód 2) zostały realnie zweryfikowane w tej sesji
(target `net9.0`) — output wklejony powyżej 1:1, bez zmyślania.

## Jak zweryfikowano „co jest nowe w .NET 10"

Zamiast zgadywać z pamięci, w tej sesji porównano realną powierzchnię API klas
`System.MemoryExtensions`, `System.Text.Json.Nodes.JsonObject`,
`System.Text.Json.Nodes.JsonArray`, `System.Text.Json.Nodes.JsonNode` i
`System.Text.Json.Utf8JsonWriter` między zainstalowanym runtime'em **9.0.18** a
**10.0.11** (`Microsoft.NETCore.App`) przez refleksję
(`System.Reflection.MetadataLoadContext`, `PathAssemblyResolver` wskazujący na katalogi
`shared/Microsoft.NETCore.App/<wersja>`, porównanie zbiorów sygnatur z
`GetMethods(Public | Static | Instance | DeclaredOnly)` — w odróżnieniu od wydania #9,
tym razem **z** metodami instancyjnymi, inaczej `JsonObject.TryAdd`/
`JsonArray.RemoveAll` nie trafiłyby na listę jako "nowe", bo to metody instancyjne, nie
statyczne extension methods).

Wynik diffu `MemoryExtensions`: 42 nowe sygnatury (9.0.18 → 10.0.11), z czego:
- 1 z `IComparer<T>`: `SequenceCompareTo<T>(ReadOnlySpan<T>, ReadOnlySpan<T>, IComparer<T>)`
  — opisana w tym wydaniu.
- ~40 z `IEqualityComparer<T>` (`IndexOf`, `Contains`, `ContainsAny`, `ContainsAnyExcept`,
  `Count`, `CountAny`, `EndsWith`, `IndexOfAny`, `IndexOfAnyExcept`, `LastIndexOf`,
  `LastIndexOfAny`, `LastIndexOfAnyExcept`, `Replace`, `StartsWith`) — opisane częściowo w
  wydaniu #9 (`IndexOf`/`Contains`/`StartsWith`/`EndsWith`/`Count` dla pojedynczego
  elementu i pod-ciągu).
- Kilka z `SearchValues<T>` bez komparatora (`CountAny`, `ReplaceAny`, `ReplaceAnyExcept`)
  — niepowiązane z tematem komparatorów, nieopisane w żadnym wydaniu jak dotąd.

Wynik diffu `System.Text.Json`:
- `JsonObject`: `TryAdd(string, JsonNode?)` i `TryAdd(string, JsonNode?, out int)` (jako
  deklarowane metody instancyjne — wcześniej `TryAdd` działał tylko przez extension
  method `CollectionExtensions.TryAdd` z interfejsu `IDictionary<,>`, bez wariantu z
  indeksem), `TryGetPropertyValue(string, out JsonNode?, out int)` — **nieopisane** w
  tym wydaniu.
- `JsonArray`: `RemoveAll(Func<JsonNode?, bool>)`, `RemoveRange(int, int)` — **opisane w
  tym wydaniu**.
- `Utf8JsonWriter`: `WriteStringValueSegment` (dla `ReadOnlySpan<byte>` i
  `ReadOnlySpan<char>`), `WriteBase64StringSegment` — **nieopisane** w tym wydaniu.
- `JsonNode`: 0 różnic.

Z pełnej listy wybrano dwie funkcje opisane w artykule i każdą potwierdzono osobno
realną kompilacją (`CS1501`, `CS1061`×2) na `net9.0`. Skrypt porównawczy (projekt
tymczasowy, referencja do `System.Reflection.MetadataLoadContext` z NuGet) nie wszedł do
repo — był w katalogu tymczasowym poza tym wydaniem (`/tmp/...../.verify-tmp/diff`,
usunięty po użyciu); powyższe liczby i błędy kompilatora są jego bezpośrednim,
wklejonym efektem.

## Zweryfikowane / niezweryfikowane — podsumowanie

- Zweryfikowane realnym `dotnet build`/`dotnet run` (SDK 10.0.400, cel `net10.0`):
  `span-ordering-compare` (wszystkie 5 sekcji, w tym `Array.Sort` z komparatorem
  opakowującym `SequenceCompareTo` i oba haczyki), `jsonarray-bulk-ops` (wszystkie 6
  sekcji, w tym oba haczyki z realnie rzuconymi wyjątkami).
- Zweryfikowane realnym `dotnet build` (cel `net9.0`): `compat-check`, oba dowody
  (`CS1501` jako domyślny stan w repo, `CS1061`×2 przełączane ręcznie komentarzem w
  kodzie).
- Niezweryfikowane: wewnętrzna implementacja `SequenceCompareTo`/`RemoveAll`/
  `RemoveRange` (np. czy `SequenceCompareTo` z komparatorem korzysta z wektoryzacji SIMD
  tak jak warianty bez komparatora, czy `RemoveAll`/`RemoveRange` realokują wewnętrzną
  tablicę czy przesuwają elementy w miejscu) — nie badano źródeł CoreLib/
  System.Text.Json, tylko poprawność i zachowanie obserwowalne z zewnątrz. Dokumentacja/
  release notes .NET 10 nie była dostępna offline w tej sesji do skonfrontowania, więc
  wszystkie twierdzenia powyżej opierają się wyłącznie na realnej kompilacji i realnym
  uruchomieniu kodu w tym repo, nie na dokumentacji.
