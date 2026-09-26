<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #3 — 26 września 2026

![.NET](https://img.shields.io/badge/.NET-10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![C#](https://img.shields.io/badge/C%23-14-239120?style=for-the-badge&logo=csharp&logoColor=white)

## `LeftJoin`/`RightJoin` w LINQ i partial constructors/events — koniec obejść

</div>

---

> _"GroupJoin, SelectMany, DefaultIfEmpty — trzy metody, żeby powiedzieć jedno słowo: LEFT."_

Dwie nowości z **.NET 10 / C# 14**, o których wcześniej nie było mowy: nowe operatory
LINQ **`LeftJoin`** i **`RightJoin`** (biblioteka) oraz **partial constructors i partial
events** (język). Kod w [`code/`](code/) zbudowany i uruchomiony na `.NET SDK 10.0.400`;
outputy poniżej to prawdziwy `dotnet run`.

| # | Funkcja | Zastępuje | Trudność |
|---|---------|-----------|----------|
| 1️⃣ | `Enumerable.LeftJoin` / `RightJoin` | `GroupJoin` + `SelectMany` + `DefaultIfEmpty` | ⭐ |
| 2️⃣ | `partial` konstruktory i eventy | obejścia z metodami `OnCreated()` / ręczne sklejanie | ⭐⭐⭐ |

---

## 1️⃣ `LeftJoin` / `RightJoin` — outer join bez rytuału

### 😤 Problem
LINQ miał `Join` (inner join), ale zewnętrzne złączenie wymagało znanej sztuczki:
`GroupJoin`, potem `SelectMany` z `DefaultIfEmpty()`. Działa, ale intencja ginie w
szumie, a przy `IQueryable` (EF) łatwo o zapytanie, którego provider nie przetłumaczy
tak, jak chcesz.

### ✨ Co się zmieniło
`System.Linq.Enumerable` ma nowe metody z sygnaturą jak `Join`, ale **element po
stronie „opcjonalnej" jest nullable** w `resultSelector`:

```csharp
var left = customers.LeftJoin(orders, c => c.Id, o => o.CustomerId,
    (c, o) => (Customer: c, Order: o));   // o: Order? - null gdy klient nie ma zamówień

var right = customers.RightJoin(orders, c => c.Id, o => o.CustomerId,
    (c, o) => (Customer: c, Order: o));   // c: Customer? - null gdy zamówienie jest "sierotą"
```

### 🖥️ Prawdziwy output (`dotnet run`)
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
Stara i nowa wersja dają identyczny wynik dla danych z przykładu.

### 💡 Co to zmienia w praktyce
- Intencja widoczna w nazwie metody; jeden operator zamiast trzech.
- Adnotacje nullable w `resultSelector` sprawiają, że kompilator (przy
  `<Nullable>enable`) pilnuje sprawdzenia `null` po stronie opcjonalnej — w starym
  wzorcu `DefaultIfEmpty()` bywało to niewidoczne.
- Anti-join („kto nie ma zamówień") to `LeftJoin` + `Where(t => t.o is null)`.
- Kolejność wyniku w teście: wg elementów `outer`, potem wg kolejności `inner`.

### ⚠️ Haczyk — dlaczego to ważne
To metody **`Enumerable`** (LINQ to Objects). Czy i jak dostawca EF Core tłumaczy
`LeftJoin` na SQL w konkretnej wersji — **nie weryfikowałem** (nie ma tu bazy); sprawdź
w notatkach wydania swojego EF Core, zanim wyrzucisz sprawdzone `GroupJoin`+`DefaultIfEmpty`
z zapytań do bazy. Zwróć też uwagę na `RightJoin`: wynik jest w kolejności `inner`
(zamówienia), nie `outer`.

**Kod:** [`code/left-right-join/`](code/left-right-join/)

---

## 2️⃣ Partial constructors i partial events (C# 14)

### 😤 Problem
`partial` działało dla klas i metod, właściwości (C# 13), ale **nie dla konstruktorów i
eventów**. Generatory kodu musiały więc wymyślać obejścia (partial metoda
`OnCreated()` wołana z konstruktora, którego i tak ktoś musiał napisać ręcznie).

### ✨ Co się zmieniło
Konstruktor instancji i event mogą mieć **deklarację definiującą** (sam podpis) i
**implementującą** (ciało). Reguły, które zaobserwowałem w kompilatorze:

```csharp
public partial class Sensor
{
    // implementacja: ciało (tu też trafia inicjalizator : this()/: base(), jeśli potrzebny)
    public partial Sensor(string name, double initial) { Name = name; Value = initial; }
    // zwykły konstruktor może delegować do partial
    public Sensor(string name) : this(name, double.NaN) { }
}
public partial class Sensor
{
    public partial Sensor(string name, double initial);       // definiująca
    public partial event Action<double>? Changed;             // definiująca (bez add/remove)
}
public partial class Sensor
{
    public partial event Action<double>? Changed              // implementująca: add/remove
    {
        add { _handlers += value; Trace.Add("add"); }
        remove { _handlers -= value; Trace.Add("remove"); }
    }
}
```

### 🖥️ Prawdziwy output (`dotnet run`)
```
  [handler] nowa wartosc: 22
  [handler 2] 22
  [handler] nowa wartosc: 23.5
  [handler 2] 23.5
Log konstruktora: ctor(ręczna implementacja) | add | add
Liczba subskrybentow: 2
Konstruktor 1-arg -> Name=bez-wartosci, Value=NaN
```

### 💡 Co to zmienia w praktyce
- Generator może wyemitować **podpis** konstruktora/eventu (kontrakt), a Ty
  dostarczasz logikę — albo odwrotnie — bez sztucznych hooków.
- Event z własnym `add`/`remove` (np. słaba referencja, liczenie subskrybentów,
  marshalling na wątek UI) da się „doczepić" do wygenerowanej klasy.
- Przykład jest ręczny: **nie testowałem** wariantu z prawdziwym source generatorem.

### ⚠️ Haczyk — dlaczego to ważne
Pierwsza wersja mojego kodu **nie skompilowała się**: po nadaniu eventowi `add`/`remove`
przestaje on być „field-like", więc `Changed?.Invoke(v)` daje błąd **`CS0079`** (event
może być tylko po lewej stronie `+=`/`-=`). Trzeba przechowywać delegata samemu
(`_handlers?.Invoke(v)`). Tu wychodzi realna konsekwencja: to, jak event został
zaimplementowany, zmienia to, co wolno wołać w reszcie klasy — także w kodzie, który
pisał ktoś inny.

**Kod:** [`code/partial-members/`](code/partial-members/)

---

## 📎 Jak uruchomić
Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #3 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
