# Kod do wydania #3 — LeftJoin/RightJoin i partial constructors/events (.NET 10 / C# 14)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`). Sprawdzone na `10.0.400`.
Projekty ustawiają `<LangVersion>14</LangVersion>`; brak zależności NuGet.

## Fragment prasówki, którego dotyczy ten kod

> `System.Linq.Enumerable` ma w .NET 10 metody `LeftJoin` i `RightJoin` o sygnaturze
> jak `Join`, ale element po stronie opcjonalnej jest nullable w `resultSelector`.
> Zastępują wzorzec `GroupJoin` + `SelectMany` + `DefaultIfEmpty`. Nie weryfikowano
> tłumaczenia na SQL w EF Core.
>
> W C# 14 konstruktory instancji i eventy mogą być `partial`: deklaracja definiująca
> (sam podpis) + implementująca (ciało; event z `add`/`remove`). Event z własnym
> `add`/`remove` nie jest field-like — `Changed?.Invoke()` daje CS0079, trzeba
> wołać własnego delegata.

## 1. LeftJoin / RightJoin

```bash
dotnet run --project left-right-join
```

Wynik:

```
--- 1. Stary sposob: GroupJoin + SelectMany + DefaultIfEmpty ---
Ada  -> 50
Ada  -> 70
Bob  -> 15
Cyd  -> (brak)
--- 2. .NET 10: Enumerable.LeftJoin ---
Ada  -> 50
Ada  -> 70
Bob  -> 15
Cyd  -> (brak)
--- 3. .NET 10: Enumerable.RightJoin (zamawiajacy moze nie istniec) ---
zamowienie 100 -> Ada
zamowienie 101 -> Ada
zamowienie 102 -> Bob
zamowienie 103 -> (nieznany klient)
--- 4. Kolejnosc wyniku LeftJoin = kolejnosc outer, potem kolejnosc inner ---
Ada/100, Ada/101, Bob/102, Cyd/-
--- 5. Anti-join: klienci bez zamowien ---
Cyd
```

## 2. Partial constructors / events

```bash
dotnet run --project partial-members
```

Wynik:

```
  [handler] nowa wartosc: 22
  [handler 2] 22
  [handler] nowa wartosc: 23.5
  [handler 2] 23.5
Log konstruktora: ctor(ręczna implementacja) | add | add
Liczba subskrybentow: 2
Konstruktor 1-arg -> Name=bez-wartosci, Value=NaN
```

Oba projekty zbudowane (0 ostrzeżeń, 0 błędów dla `left-right-join`) i uruchomione
lokalnie. Pierwsza wersja `partial-members` nie kompilowała się (CS0079) — poprawiona.
