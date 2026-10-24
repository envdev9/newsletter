# Kod do wydania #4 — lambda modifiers bez typów i first-class Span (.NET 10 / C# 14)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`). Sprawdzone na `10.0.400`.
Projekty ustawiają `<LangVersion>14</LangVersion>`; brak zależności NuGet.

## Fragment prasówki, którego dotyczy ten kod

> C# 14 pozwala dać `out`/`ref`/`in`/`scoped` parametrom lambdy bez podawania typu:
> `(text, out result) => int.TryParse(text, out result)`. `params` nadal wymaga typu
> (CS9272).
>
> Niejawne konwersje `T[]`/`string` → `ReadOnlySpan<T>` i `Span<T>` → `ReadOnlySpan<T>`
> działają także dla odbiornika metody rozszerzającej i w inferencji generyków, więc
> `"kajak".IsPalindrome()` działa bez `.AsSpan()`. Sprawdzone: `array.Reverse()` nadal
> wybiera LINQ na SDK 10.0.400; inne metody `MemoryExtensions` nie były badane.

## 1. Lambda modifiers

```bash
dotnet run --project lambda-modifiers
```

```
--- 1. out bez typow (C# 14) ---
42   -> ok=True, n=42
abc  -> ok=False, n=0
--- 2. ref bez typow ---
x po Doubler = 42
--- 3. in bez typow ---
suma = 10
--- 4. scoped bez typow ---
dlugosc = 5
```

## 2. First-class Span

```bash
dotnet run --project span-conversions
```

```
--- 1. Metoda rozszerzajaca na ReadOnlySpan<char> wolana na string ---
kajak -> True
tablica znakow -> True
--- 2. Generyk + inferencja T z tablicy ---
ile dwojek: 3
--- 3. Span<T> -> ReadOnlySpan<T> i tablica -> ReadOnlySpan<T> w argumencie ---
Sum(tablica) = 10, Sum(span) = 10
--- 4. Sprawdzenie znanej pulapki: tablica.Reverse() ---
typ wyniku Reverse(): ReverseIterator`1
arr po Reverse(): [1, 2, 3]
```

## 3. compat-check (celowo NIE kompiluje się)

Projekt `compat-check` dokumentuje błąd `CS9272` dla `(params xs) => ...`:

```bash
dotnet build compat-check
```

Oczekiwany wynik: `error CS9272: Implicitly typed lambda parameter 'xs' cannot have the 'params' modifier.`
Wersja z `<LangVersion>13</LangVersion>` (lambda `out` + `"kajak".IsPalindrome()` na
`ReadOnlySpan<char>`) dała `CS9260` i `CS1929` — opisane w artykule; tamten kod został
zastąpiony obecnym `Program.cs`.

Projekty `lambda-modifiers` i `span-conversions` zbudowane (0 ostrzeżeń, 0 błędów)
i uruchomione lokalnie.
