<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #4 — 27 września 2026

![.NET](https://img.shields.io/badge/.NET-10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![C#](https://img.shields.io/badge/C%23-14-239120?style=for-the-badge&logo=csharp&logoColor=white)

## Lambdy z `out`/`ref` bez typów i „first-class Span" — mniej ceremonii, mniej `.AsSpan()`

</div>

---

> _"Napisałeś `int.TryParse`, kompilator wie, że to `int`. Dlaczego każe Ci to wpisać jeszcze raz?"_

Dwie nowości **języka C# 14** (dostarczane z .NET 10 SDK), których jeszcze nie było:
**modyfikatory parametrów lambdy bez podawania typu** oraz **niejawne konwersje
`Span`** (w specyfikacji: „first-class Span types"). Kod w [`code/`](code/) zbudowany i
uruchomiony na `.NET SDK 10.0.400`; outputy poniżej to prawdziwe `dotnet build`/`run`.

| # | Funkcja | Zastępuje | Trudność |
|---|---------|-----------|----------|
| 1️⃣ | Lambda: `(text, out result) => ...` | `(string text, out int result) => ...` | ⭐ |
| 2️⃣ | Niejawne konwersje `T[]`/`string` → `ReadOnlySpan<T>` (także dla `this`) | ręczne `.AsSpan()` przy wołaniu metod na spanach | ⭐⭐ |

---

## 1️⃣ Modyfikatory parametrów lambdy bez typów

### 😤 Problem
Do C# 13 lambda z `out`, `ref`, `in`, `scoped` czy `ref readonly` musiała mieć
**jawnie wypisane typy wszystkich parametrów** — wystarczyło jedno `out`, a cała reszta
też traciła inferencję. Przy delegatach w stylu `TryParse` oznaczało to powtarzanie
typu, który kompilator i tak zna z delegata.

### ✨ Co się zmieniło
W C# 14 modyfikator można dać przy parametrze bez typu:

```csharp
delegate bool TryParser<T>(string text, out T result);

// Przed C# 14: (string text, out int result) => int.TryParse(text, out result)
TryParser<int> parse = (text, out result) => int.TryParse(text, out result);

delegate void Doubler(ref int value);
Doubler dbl = (ref v) => v *= 2;

delegate int Summer(in Big big);
Summer sum = (in b) => (int)(b.A + b.B + b.C + b.D);

delegate int SpanCounter(scoped Span<int> span);
SpanCounter count = (scoped span) => span.Length;
```

### 🖥️ Prawdziwy output (`dotnet run --project lambda-modifiers`)
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

### 🔬 Dowód „przed i po"
To samo w projekcie z `<LangVersion>13</LangVersion>` (kod z `compat-check`,
wersja z lambdą `out`):
```
error CS9260: Feature 'simple lambda parameter modifiers' is not available in C# 13.0. Please use language version 14.0 or greater.
```

### 💡 Co to zmienia w praktyce
- Krótsze lambdy do delegatów `TryXxx`, `ref`/`in` (np. wielkie struktury przekazywane
  przez `in`) — typ bierze się z delegata.
- Nie musisz już wypisywać typów wszystkich parametrów tylko dlatego, że jeden jest `out`.
- To czysto składniowe: semantyka delegatów się nie zmienia; typ parametru nadal jest
  wywnioskowany **z docelowego typu delegata**, więc lambda musi mieć taki kontekst
  (przypisanie do `var f = (x, out y) => ...` nie ma z czego wnioskować).
  Ten ostatni punkt to moja interpretacja reguł inferencji lambd — **nie testowałem** go
  osobno.

### ⚠️ Haczyk — dlaczego to ważne
`params` nie należy do tego udogodnienia. Sprawdzone kompilatorem (C# 14):
```
error CS9272: Implicitly typed lambda parameter 'xs' cannot have the 'params' modifier.
```
Czyli `(params xs) => ...` nadal wymaga `(params int[] xs) => ...`.

**Kod:** [`code/lambda-modifiers/`](code/lambda-modifiers/), błąd `params`: [`code/compat-check/`](code/compat-check/)

---

## 2️⃣ „First-class Span" — niejawne konwersje tablic, stringów i spanów

### 😤 Problem
`Span<T>` i `ReadOnlySpan<T>` są `ref struct`ami z konwersjami zdefiniowanymi
**przez użytkownika** (`implicit operator`). Konwersje użytkownika nie brały udziału
w bindowaniu metod rozszerzających ani w inferencji generyków, więc `"kajak".IsPalindrome()`
na metodzie `this ReadOnlySpan<char>` się nie kompilowało — trzeba było
`"kajak".AsSpan().IsPalindrome()`.

### ✨ Co się zmieniło
C# 14 wprowadza wbudowane konwersje: `T[]` → `Span<T>`/`ReadOnlySpan<T>`,
`Span<T>` → `ReadOnlySpan<T>`, `string` → `ReadOnlySpan<char>`. Działają też jako
**odbiornik metody rozszerzającej** i w **inferencji typów** przy metodach generycznych:

```csharp
public static bool IsPalindrome(this ReadOnlySpan<char> s) { /* ... */ }
public static int CountEqual<T>(this ReadOnlySpan<T> s, T value) where T : IEquatable<T> { /* ... */ }

string word = "kajak";
word.IsPalindrome();                        // string -> ReadOnlySpan<char> jako this
new[] { 'a', 'b', 'a' }.IsPalindrome();     // char[] -> ReadOnlySpan<char>
int[] numbers = [1, 2, 2, 3, 2];
numbers.CountEqual(2);                      // T wywnioskowane z int[]
```

### 🖥️ Prawdziwy output (`dotnet run --project span-conversions`)
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

### 🔬 Dowód „przed i po"
Ta sama wywołanie `"kajak".IsPalindrome()` przy `<LangVersion>13</LangVersion>`:
```
error CS1929: 'string' does not contain a definition for 'IsPalindrome' and the best extension method overload 'Ext.IsPalindrome(ReadOnlySpan<char>)' requires a receiver of type 'System.ReadOnlySpan<char>'
```

### 💡 Co to zmienia w praktyce
- API projektowane „span-first" (`ReadOnlySpan<char>` zamiast `string`) przestaje
  być uciążliwe dla wołających: nie trzeba `AsSpan()` przy każdym wywołaniu, także
  dla metod rozszerzających i generycznych.
- Możesz pisać jedną metodę na `ReadOnlySpan<T>` zamiast zestawu przeciążeń
  (`T[]`, `string`, `Span<T>`).
- Biblioteki mogą bez alokacji przyjmować spany i nadal być wygodne w użyciu.

### ⚠️ Haczyk — dlaczego to ważne
Nowe konwersje zmieniają, **jaka metoda zostanie wybrana** przy istniejącym kodzie
po podniesieniu `LangVersion` do 14. Znana obawa: `array.Reverse()` mogłoby zacząć
wskazywać na `MemoryExtensions.Reverse(Span<T>)` (odwraca w miejscu) zamiast LINQ-owego
`Enumerable.Reverse`. **U mnie na SDK 10.0.400 się to nie zmaterializowało** — output
wyżej pokazuje `ReverseIterator` (LINQ) i tablicę bez zmian. Wniosek: w tym zestawie
(SDK 10.0.400, `net10.0`) ten konkretny przypadek jest bezpieczny; **nie sprawdzałem**
innych metod z `MemoryExtensions` (np. `Contains`, `StartsWith`, `Sort`) ani starszych
target frameworków. Po włączeniu C# 14 warto przejrzeć testy pod kątem zmiany
wyboru przeciążeń.

**Kod:** [`code/span-conversions/`](code/span-conversions/)

---

## 📎 Jak uruchomić
Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #4 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
