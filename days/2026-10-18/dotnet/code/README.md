# Kod do wydania #25 — `Enumerable.Reverse(T[])` i `HttpMethod.Query` (.NET 10)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (sprawdzone na `10.0.400`) oraz runtime 9.x (`dotnet --list-runtimes`) dla
projektów dwu-TFM (`reflect-diff`, `reverse-array`); `compat-check-query` wymaga **SDK 9.0.316**
(przypięte `global.json`, `rollForward: disable` — zmień wersję, jeśli masz inne 9.0.x). Brak NuGet, brak
sieci zewnętrznej (serwer `HttpListener` na `127.0.0.1`).

## Fragment prasówki, którego dotyczy ten kod

> **`Enumerable.Reverse<TSource>(TSource[])`** (.NET 10) łata cichy breaking change C# 14 (first-class Span):
> `a.Reverse();` na tablicy wiązało się z LINQ (nic nie robi), ale z `LangVersion 14` na `net9.0` wiąże się z
> `MemoryExtensions.Reverse(Span<T>)` i **odwraca tablicę w miejscu** (zwraca `void`). Na `net10.0` nowe,
> dokładniejsze przeciążenie wygrywa i znów jest LINQ. `foreach (var x in a.Reverse())` na net9.0 + C# 14 →
> `CS1579`. Pisz jawnie: `Enumerable.Reverse(a)`, `a.AsSpan().Reverse()`, `Array.Reverse(a)`.
>
> **`HttpMethod.Query`** (.NET 10): metoda HTTP `QUERY` (bezpieczna, idempotentna, z ciałem). Na SDK 9.0.316:
> `CS0117`. Zmierzone: round-trip z ciałem JSON; `Query == new HttpMethod("QUERY")` (nieczułe na wielkość
> liter), ale inna referencja; po 301/302 `QUERY` zachowuje metodę i ciało (`POST` degraduje do `GET`), po 303
> → `GET`. `GET` z ciałem też przechodzi (pułapka z pośrednikami). Serwer: tylko `HttpListener`, nie Kestrel.

## 1. reflect-diff (refleksja na dwóch runtime'ach)

```bash
dotnet run -f net9.0  --project reflect-diff
dotnet run -f net10.0 --project reflect-diff
```

Różnica: na 10.0.11 pojawia się `IEnumerable`1 Reverse(TSource[])` oraz `Query -> "QUERY"`.

## 2. reverse-array

```bash
dotnet run -f net9.0  --project reverse-array
dotnet run -f net10.0 --project reverse-array
```

Output (zweryfikowany; skrót, pełny w konsoli — sekcje 2–5 identyczne poza sekcjami 1, 3 i 4):

```
Runtime: .NET 9.0.18, TFM-define: NET9_0
po a.Reverse(): [5, 4, 3, 2, 1]  -> ODWROCONA w miejscu (Span)
c po c.Reverse(): [3, 2, 1]
c po IEnumerable<int>.Reverse(): [3, 2, 1] (rzutowanie na IEnumerable<T> zawsze daje LINQ)
(pominiete na net9.0: `d.Reverse()` zwraca void -> foreach nie skompiluje sie)
Enumerable.Reverse(TSource[]) istnieje: False

Runtime: .NET 10.0.11, TFM-define: NET10_0_OR_GREATER
po a.Reverse(): [1, 2, 3, 4, 5]  -> bez zmian (LINQ, wynik wyrzucony)
c po c.Reverse(): [1, 2, 3]
c po IEnumerable<int>.Reverse(): [1, 2, 3] (rzutowanie na IEnumerable<T> zawsze daje LINQ)
30 20 10   <- kompiluje sie tylko na net10.0 (na net9.0 + C# 14: CS1579)
Enumerable.Reverse(TSource[]) istnieje: True
```

Sekcja 2 (oba TFM): `Enumerable.Reverse(b)` → `[5, 4, 3, 2, 1]`, `b` bez zmian; `b.AsSpan().Reverse()`
odwraca `b`; `Array.Reverse(b)` odwraca z powrotem.

## 3. compat-check-reverse (celowo NIE kompiluje się z C# 14 na net9.0)

```bash
dotnet build compat-check-reverse
dotnet run -p:LangVersion=13 --project compat-check-reverse
```

Zweryfikowane: pierwsze → `error CS1579: foreach statement cannot operate on variables of type 'void'...`;
drugie → `30 20 10`.

## 4. http-query-method

```bash
dotnet run -c Release --project http-query-method
```

Output (zweryfikowany, 2 przebiegi, identyczny):

```
--- 1. Round-trip: HttpMethod.Query z cialem JSON ---
status=200, odpowiedz=["alfa","alfabet"]
serwer zobaczyl: QUERY /search body={"prefix":"al"}
--- 2. Rownosc i tekst ---
HttpMethod.Query.Method = "QUERY", ToString = "QUERY"
Query == new HttpMethod("QUERY") : True
Query == new HttpMethod("query") : True
ReferenceEquals(Query, new HttpMethod("QUERY")) : False
HttpMethod.Parse("QUERY") jest singletonem Query : True
--- 3. Dla porownania: GET z cialem ---
GET z cialem -> status=200; serwer zobaczyl: GET /search body={"prefix":"al"}
--- 4. Przekierowania (AllowAutoRedirect = true): jaka metode dostaje cel? ---
POST  + 301 -> GET /landed body=<pusto>
POST  + 302 -> GET /landed body=<pusto>
POST  + 303 -> GET /landed body=<pusto>
POST  + 307 -> POST /landed body=tresc
POST  + 308 -> POST /landed body=tresc
QUERY + 301 -> QUERY /landed body=tresc
QUERY + 302 -> QUERY /landed body=tresc
QUERY + 303 -> GET /landed body=<pusto>
QUERY + 307 -> QUERY /landed body=tresc
QUERY + 308 -> QUERY /landed body=tresc
```

## 5. compat-check-query (celowo NIE kompiluje się na .NET 9)

```bash
dotnet build compat-check-query
```

Zweryfikowane (SDK 9.0.316): `error CS0117: 'HttpMethod' does not contain a definition for 'Query'`
(linia z `HttpMethod.Post` nie daje błędu).

## Zweryfikowane / niezweryfikowane

- Zweryfikowane `dotnet run`: `reflect-diff` i `reverse-array` (oba TFM), `http-query-method`.
- Zweryfikowane `dotnet build`: `compat-check-reverse` (CS1579 / OK z LangVersion 13), `compat-check-query` (CS0117, SDK 9.0.316).
- Niezweryfikowane: `List<T>`/`ReadOnlySpan` przy `Reverse`, Kestrel/minimal API/CORS/cache dla `QUERY`, pośrednicy
  HTTP, przyczyna zachowania przy 301/302, status RFC, .NET 11 (brak SDK), dokumentacja online.
