# Kod do wydania #14 — `CountAny`/`ReplaceAny`/`ReplaceAnyExcept` z `SearchValues<T>` i LINQ na `IAsyncEnumerable<T>` (.NET 10)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (sprawdzone na `10.0.400`). `searchvalues-any` i
`asyncenum-linq` celują w `net10.0`; `compat-check` celowo w `net9.0` (potrzebuje
SDK 9.x obok; sprawdzone na `9.0.316`). Brak zależności NuGet.

## Fragment prasówki, którego dotyczy ten kod

> `MemoryExtensions.CountAny` / `ReplaceAny` / `ReplaceAnyExcept` z `SearchValues<T>` —
> liczenie i podmiana zbioru znaków bez pętli. Nie istnieją w .NET 9 (`CS1061`×4).
> Zmierzone: 16 M znaków — `ReplaceAny` 0 B alokacji, dziewięć `string.Replace` 288 MB.
> Haczyki: `destination` krótszy → `ArgumentException`; emoji = 2 jednostki UTF-16 (`a😀b` →
> `a__b`); `ReplaceAnyExcept` z pustym zbiorem zamienia wszystko.
>
> LINQ na `IAsyncEnumerable<T>` (`Where`, `Select`, `ToListAsync`, `CountAsync`...) w BCL,
> bez `System.Linq.Async`. Na .NET 9: `CS0411`/`CS1061`. Haczyki: każda enumeracja
> startuje źródło od nowa; `Take(2)` zatrzymuje generator i uruchamia jego `finally`;
> `FirstOrDefaultAsync` na pustym zwraca `default`.

## 1. searchvalues-any

```bash
dotnet run -c Release --project searchvalues-any
```

Output (alokacje deterministyczne; czasy zależą od maszyny i różnią się między uruchomieniami):

```
--- 1. CountAny: ile znakow ze zbioru (bez petli i bez alokacji) ---
CountAny(samogloski) = 10
petla + Contains     = 10

--- 2. ReplaceAny / ReplaceAnyExcept: sanityzacja nazwy pliku ---
ReplaceAny (src->dst) : raport_ Q3_Q4 _final__.txt
ReplaceAny (w miejscu): raport_ Q3_Q4 _final__.txt
ReplaceAnyExcept       : za_____g__l__ja___2026_.txt
CountAnyExcept brak -> uzyj Length - CountAny: 13 znakow zastapionych

--- 3. Pomiar: 16M znakow, ReplaceAny vs petla vs lancuch string.Replace (Release) ---
CountAny          :   4195786 trafien, alokacje 0 B
petla + Contains  :   4195786 trafien, alokacje 0 B (wynik zgodny: True)
ReplaceAny        : alokacje 0 B
9x string.Replace : alokacje 288 MB (wynik zgodny: True)
czas (sr. z 5): CountAny 132.1 ms, petla 148.7 ms
czas (sr. z 5): ReplaceAny 99.1 ms, 9x string.Replace 608.6 ms

--- 4. HACZYK A: destination krotszy niz source ---
RZUCILO ArgumentException: "Destination is too short. (Parameter 'destination')"

--- 5. HACZYK B: znaki spoza BMP (emoji = 2 jednostki UTF-16) ---
"a😀b" (Length 4) -> "a__b" (zastapionych: 2)
a naprawde znakow tekstowych (Rune): 3

--- 6. HACZYK C: pusty zbior i ReplaceAny z newValue ze zbioru ---
CountAny(pusty) = 0
ReplaceAnyExcept(pusty) -> ###  (pusty zbior = 'wszystko poza nim' = wszystko)
ReplaceAny('-'->'-') -> a-b-c (idempotentne, bez wyjatku)

--- 7. Bonus: to samo na bajtach UTF-8 (SearchValues<byte>) ---
zażółć_1_2_3 (CountAny na bajtach: 3)
```

## 2. asyncenum-linq

```bash
dotnet run --project asyncenum-linq
```

Output (skrót; pełny log każdej sekcji zawiera linie `[X] start` / `[X] dispose (finally)`;
liczba elementów oddanych przy anulowaniu w sekcji 7 zależy od czasu):

```
Where+Select+ToListAsync: [4, 16, 36, 64, 100]
CountAsync = 3
SumAsync   = 15
MaxAsync   = 5
   [E] start
   [E] dispose (finally), oddanych elementow: 2      <- Take(2) na generatorze 100-elementowym
dostepne: [1, 2, 4, 5]
Order: [1, 2, 3]
pierwszy raz: 2   (start+dispose)    drugi raz: 2   (znowu start+dispose)
RZUCILO TaskCanceledException
RZUCILO InvalidOperationException: boom na 3
FirstAsync: RZUCILO InvalidOperationException: "Sequence contains no elements"
FirstOrDefaultAsync: 0
```

## 3. compat-check (celowo NIE kompiluje się na .NET 9)

```bash
dotnet build compat-check
```

Oczekiwany wynik — dokładnie 6 błędów (zweryfikowane): `CS1061` dla `CountAny`,
`ReplaceAny`×2, `ReplaceAnyExcept`, `CountAsync`; `CS0411` dla `Where` na
`IAsyncEnumerable` (kompilator trafia na `ImmutableArrayExtensions.Where`). Linie ze
starym API (`IndexOfAny`, `ContainsAny`, `IndexOfAnyExcept`) kompilują się.

## Zweryfikowane / niezweryfikowane

- Zweryfikowane `dotnet run` (SDK 10.0.400): oba programy, wszystkie sekcje.
- Zweryfikowane `dotnet build` (net9.0, SDK 9.0.316): 6 błędów jak wyżej.
- Niezweryfikowane: pełna lista operatorów async LINQ, EF Core, nakładające się spany,
  .NET 11 (brak SDK), dokumentacja online. Czasy są jakościowe (duży rozrzut między uruchomieniami).
