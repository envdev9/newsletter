# Kod do wydania #2 — `field` i null-conditional assignment (C# 14 / .NET 10)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`). Projekty ustawiają
`<LangVersion>14</LangVersion>`. Sprawdzone na `10.0.400`.

## Fragment prasówki, którego dotyczy ten kod

> W akcesorze `get`/`set`/`init` można użyć kontekstowego słowa `field` — niejawnego
> pola zapasowego generowanego przez kompilator (semi-auto property). Jeden akcesor
> może być nadal automatyczny, drugi z logiką (walidacja, trim, powiadomienia,
> leniwa inicjalizacja) — bez ręcznego pola `_name`.
>
> `?.` i `?[]` mogą stać po lewej stronie przypisania: `c?.Name = "Ala"`,
> `c?.Score += 8`, `arr?[1] = 7`. Prawa strona jest ewaluowana tylko wtedy, gdy cel
> nie jest null. Uwaga: `c?.Score++` się nie kompiluje (CS1059).

## 1. `field`

```bash
cd field-keyword
dotnet run
```

Wynik:

```
--- Name: walidacja + trim w setterze ---
  [event] zmieniono: Name
Name = 'Ada Lovelace'
Wyjątek: The value cannot be an empty string or composed entirely of whitespace. (Parameter 'value')
--- Email: getter z domyślną wartością, setter z normalizacją ---
Email (przed ustawieniem) = '(brak)'
Email = 'ada@example.com'
--- Tags: leniwa inicjalizacja w getterze ---
Tags.Count = 0
Tags = [math]
--- Ile razy leniwy getter tworzył listę: 1 ---
```

## 2. Null-conditional assignment

```bash
cd null-conditional-assignment
dotnet run
```

Wynik:

```
--- 1. Klasyczne vs C# 14 ---
c1.Name = Ala (nowe ?.), c2 = null
--- 2. Prawa strona jest ewaluowana WARUNKOWO (short-circuit) ---
  [Expensive() wywołane]
c1.Score = 42, sideEffects = 1
po c2: sideEffects = 1
--- 3. Operatory złożone i indekser ---
c1.Score = 50
arr = [0,7,0]
--- 4. Łańcuch: cała reszta pomijana gdy coś w drodze jest null ---
order.Customer is null: True
order.Customer.Name = Bob II
--- 5. Jako wyrażenie: typ wyniku staje się nullable ---
x = y, y = null, typ = String
s = 5, HasValue = True
```

Oba projekty zbudowane i uruchomione lokalnie przed publikacją (0 ostrzeżeń, 0 błędów
w końcowej wersji `null-conditional-assignment`). Błąd `CS1059` dla `c1?.Score++`
zaobserwowany w prawdziwej próbie budowania.
