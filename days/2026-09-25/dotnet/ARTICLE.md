<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #2 — 25 września 2026

![.NET](https://img.shields.io/badge/.NET-10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![C#](https://img.shields.io/badge/C%23-14-239120?style=for-the-badge&logo=csharp&logoColor=white)

## `field` i `?.` po lewej stronie przypisania — koniec ceremonii w C# 14

</div>

---

> _"Najlepszy kod to ten, którego nie musisz pisać. Drugi w kolejności to ten,
> w którym `if (x != null)` znika z co dziesiątej linijki."_

Wczoraj: extension members i file-based apps. Dziś dwie kolejne nowości z **C# 14**
(język dostarczany z **.NET 10**): słowo kluczowe **`field`** oraz
**null-conditional assignment**. Obie przetestowane na `.NET SDK 10.0.400` —
kod w [`code/`](code/) kompiluje się, a output poniżej to prawdziwy `dotnet run`.

| # | Funkcja | Zastępuje | Trudność |
|---|---------|-----------|----------|
| 1️⃣ | `field` w property | ręczne pole `_name` | ⭐ |
| 2️⃣ | `a?.b = x` | `if (a is not null) a.b = x;` | ⭐ |

---

## 1️⃣ `field` — pole zapasowe bez pola

### 😤 Problem
Auto-property `{ get; set; }` jest wygodne, dopóki nie potrzebujesz **odrobiny** logiki:
trim, walidacji, `INotifyPropertyChanged`, leniwej inicjalizacji. Wtedy musiałeś
przepisać całość: dodać prywatne `_name`, napisać oba akcesory ręcznie, a `_name` mógł
potem być zmieniony z dowolnego miejsca klasy — omijając setter.

### ✨ Co się zmieniło
W akcesorze `get`/`set`/`init` można użyć kontekstowego słowa **`field`** — to niejawne
pole zapasowe, które kompilator generuje sam (tzw. *semi-auto property*).
Jeden akcesor może być nadal automatyczny (`get;`), drugi z logiką.

```csharp
public string Name
{
    get;
    set
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(value);
        var trimmed = value.Trim();
        if (field == trimmed) return;      // brak eventu przy tej samej wartości
        field = trimmed;
        PropertyChanged?.Invoke(this, new(nameof(Name)));
    }
} = "";

// Leniwa inicjalizacja - bez ręcznego pola
public List<string> Tags
{
    get
    {
        if (field is null) { field = new(); TagsCreated++; }
        return field;
    }
}
```

### 🖥️ Prawdziwy output (`dotnet run`)
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
Zwróć uwagę: event poleciał **raz** — drugie `user.Name = "Ada Lovelace"` porównało
z `field` i wyszło wcześniej. Inicjalizator `= ""` zapisuje wartość bezpośrednio w polu
(bez wołania settera), więc nie odpala walidacji.

### 💡 Co to zmienia w praktyce
- Ściana boilerplate'u w ViewModelach (`SetProperty(ref _x, value)`) kurczy się do
  kilku linii, bez dodatkowego prywatnego pola.
- Zniknęła możliwość, że ktoś w klasie napisze `_name = ...` i ominie walidację —
  `field` jest widoczne **tylko** w akcesorach danej właściwości.
- Migracja jest inkrementalna: zaczynasz od `{ get; set; }` i dopisujesz logikę
  tylko tam, gdzie potrzeba.

### ⚠️ Haczyk — dlaczego to ważne
`field` jest słowem kontekstowym. Jeśli w klasie **już masz** pole albo zmienną o nazwie
`field`, po aktualizacji języka `field` w akcesorze zacznie oznaczać niejawne pole
(może to zmienić znaczenie kodu; ten scenariusz opisuję z dokumentacji C# 14, nie
odtwarzałem go w projekcie). Rozwiązanie: `@field` (odwołanie do Twojego
symbolu) albo `this.field`. Kompilator ostrzega w takich przypadkach — nie ignoruj
ostrzeżeń przy migracji na C# 14. Uwaga też na serializację/refleksję: nazwa
wygenerowanego pola jest szczegółem implementacji (tego **nie** weryfikowałem —
sprawdź, jeśli polegasz na refleksji po polach).

**Kod:** [`code/field-keyword/`](code/field-keyword/)

---

## 2️⃣ Null-conditional assignment — `a?.b = x`

### 😤 Problem
Operator `?.` do tej pory działał tylko po **odczytach**. Przy zapisie zostawał
gadatliwy `if (customer is not null) customer.Name = ...;`.

### ✨ Co się zmieniło
`?.` i `?[]` mogą stać po lewej stronie przypisania i przypisania złożonego:

```csharp
c1?.Name = "Ala";        // ustawi tylko gdy c1 != null
c1?.Score += 8;          // operatory złożone też działają
arr?[1] = 7;             // indekser też
order?.Customer?.Name = "X";   // cały łańcuch pomijany gdy cokolwiek jest null
```

Kluczowa własność: **prawa strona jest ewaluowana tylko wtedy, gdy cel nie jest null**
(short-circuit). Sprawdziłem to licznikiem efektów ubocznych:

### 🖥️ Prawdziwy output (`dotnet run`)
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
`c2?.Score = Expensive()` **nie** wywołało `Expensive()` (licznik został na 1).

### 💡 Co to zmienia w praktyce
- Mniej zagnieżdżeń i guard-clauses przy „ustaw jeśli obiekt istnieje" (opcjonalne
  zależności, wyniki `FirstOrDefault`, `TryGet`).
- Semantyka short-circuit oznacza, że możesz bezpiecznie wstawić po prawej stronie
  kosztowne wywołanie — nie wykona się na `null`.
- Przypisanie użyte jako wyrażenie daje wynik nullable (`string?`, `int?`) — pokazane
  w sekcji 5 outputu.

### ⚠️ Haczyk — dlaczego to ważne
**Cichy no-op.** `c?.Name = x` przy `c == null` nie rzuca i nie loguje niczego. Tam,
gdzie null oznacza błąd programisty (a nie „opcjonalny obiekt"), stary `if`/`throw`
nadal jest lepszy — inaczej zamieniasz głośny `NullReferenceException` na cichą
utratę danych. Druga pułapka, którą sprawdził kompilator: **`c?.Score++` nie
kompiluje się** (błąd `CS1059`) — inkrement/dekrement nie są wspierane, użyj
`c?.Score += 1`.

**Kod:** [`code/null-conditional-assignment/`](code/null-conditional-assignment/)

---

## 📎 Jak uruchomić
Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #2 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
