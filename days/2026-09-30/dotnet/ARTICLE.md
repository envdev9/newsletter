<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #7 — 30 września 2026

![.NET](https://img.shields.io/badge/.NET-10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![BCL](https://img.shields.io/badge/BCL-runtime-blue?style=for-the-badge)

## Tasowanie bez ręcznego Fisher-Yatesa i JSON, który w końcu potrafi być podejrzliwy

</div>

---

> _"Duplicate keys SHOULD be avoided... Implementations whose behavior does not
> depend on member ordering will be interoperable in the sense that they will
> not be affected by these differences."_ — RFC 8259 (JSON), sekcja 8.3 — czyli
> specyfikacja JSON od lat wprost przyznaje, że duplikaty kluczy to źródło
> niejednoznaczności, a różne parsery mogą je obsłużyć różnie. .NET 10 wreszcie
> daje narzędzie, żeby to zamknąć jawną decyzją zamiast losu implementacji.

Kontynuujemy przegląd nowości **BCL/runtime .NET 10** (wydania #1–#4 to nowości
**języka** C# 14, wydanie #5 to kryptografia postkwantowa i generyczne
`GCHandle<T>`) — dziś dwie zupełnie inne funkcje: jedna w LINQ, jedna w
`System.Text.Json`. Obie znalezione **empirycznie**, nie z pamięci: w tej sesji
porównano refleksją publiczne API `System.Linq.dll` i `System.Text.Json.dll`
zainstalowanego SDK 9.0.316 (.NET 9) i 10.0.400 (.NET 10), a potem każdą
kandydatkę potwierdzono osobno realnym błędem kompilatora na `net9.0`. Kod w
[`code/`](code/).

| # | Funkcja | Namespace | Status |
|---|---------|-----------|--------|
| 1️⃣ | `Enumerable.Shuffle<T>()` | `System.Linq` | ✅ w pełni zweryfikowane |
| 2️⃣ | `JsonSerializerOptions.Strict` / `JsonDocumentOptions.AllowDuplicateProperties` | `System.Text.Json` | ✅ w pełni zweryfikowane |

---

## 1️⃣ `Enumerable.Shuffle<T>()` — tasowanie wreszcie w standardowej bibliotece

### 😤 Problem
Do tej pory, żeby potasować sekwencję w LINQ, ludzie sięgali po jeden z dwóch
złych idiomów: `sequence.OrderBy(_ => Guid.NewGuid())` (sortowanie po losowym
kluczu — działa, ale marnuje czas na sortowanie `O(n log n)`, gdy tasowanie da
się zrobić w `O(n)`, i nie jest to sposób, który ktokolwiek by nazwał czytelnym)
albo ręczna implementacja algorytmu Fisher-Yatesa w pętli `for`, kopiowana
z projektu do projektu.

### ✨ Co się zmieniło
.NET 10 dodaje do `System.Linq.Enumerable` metodę `Shuffle<TSource>(this
IEnumerable<TSource> source)`. Sprawdzone empirycznie: **nie istnieje w .NET
9** — na SDK 9.0.316 `tablica.Shuffle()` daje `CS1061` (dowód niżej). Przy
okazji tego samego przeglądu API w `System.Linq` znaleziono też dwie inne nowe
metody, `Enumerable.Sequence`/`InfiniteSequence` (generowanie sekwencji liczb
z krokiem) — nie opisujemy ich dziś szerzej, żeby nie rozwadniać wydania, ale
warto wiedzieć, że też są nowe w .NET 10.

```csharp
int[] questions = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

IEnumerable<int> shuffled = questions.Shuffle();
Console.WriteLine(string.Join(",", shuffled.ToArray()));
// oryginalna tablica `questions` pozostaje niezmieniona - Shuffle nie mutuje w miejscu
```

### 🖥️ Prawdziwy output (`dotnet run --project linq-shuffle`, ta maszyna)
```
--- 1. Podstawowe tasowanie ---
oryginalna tablica: 1,2,3,4,5,6,7,8,9,10
questions.Shuffle() (zmaterializowane raz): 7,9,2,8,4,5,6,1,3,10
oryginalna tablica po Shuffle() - NIE zmieniona: 1,2,3,4,5,6,7,8,9,10

--- 2. HACZYK: Shuffle() jest leniwe i tasuje NA NOWO przy kazdej enumeracji ---
1. enumeracja tej samej zmiennej: 8,9,6,7,3,10,5,4,1,2
2. enumeracja tej samej zmiennej: 6,7,3,10,4,1,5,9,8,2
identyczna kolejnosc obu enumeracji? False
typ zwracany: ShuffleIterator`1 (deferred execution, jak reszta LINQ)
```

### 🔬 Dowód „przed i po" (SDK 9.0.316, `net9.0`)
```
error CS1061: 'int[]' does not contain a definition for 'Shuffle' and no
accessible extension method 'Shuffle' accepting a first argument of type
'int[]' could be found (are you missing a using directive or an assembly
reference?)
```

### 💡 Co to zmienia w praktyce
- Nie trzeba już wybierać między wolnym `OrderBy(_ => Guid.NewGuid())` a
  wklejaniem własnej implementacji Fisher-Yatesa — losowanie kolejności pytań
  w quizie, kart w talii, elementów playlisty to teraz jedna metoda z BCL.
- `Shuffle()` **nie mutuje** źródła (sprawdzone: `questions` po wywołaniu jest
  identyczne jak przed) — bezpieczne w kodzie, który trzyma referencję do
  oryginalnej kolekcji gdzie indziej.
- Działa na dowolnym `IEnumerable<T>`, nie tylko na tablicy/liście.

### ⚠️ Haczyk — deferred execution tasuje na nowo przy KAŻDEJ enumeracji
Zmierzone realnie (sekcja 2 w kodzie): `Shuffle()`, jak cała reszta LINQ, jest
**leniwe**. Jeśli nie zmaterializujesz wyniku (`.ToArray()`/`.ToList()`) i
enumerujesz tę samą zmienną dwa razy — np. raz żeby coś policzyć, raz żeby to
wyświetlić — dostaniesz **dwie różne kolejności**, bo `ShuffleIterator<T>`
losuje od nowa przy każdym `GetEnumerator()`. To nie jest bug, to konsekwencja
tego jak działa LINQ — ale łatwo się na tym potknąć, jeśli ktoś zakłada, że
"jedno wywołanie `Shuffle()` = jedna, stała kolejność". Zasada: jeśli kolejność
ma być stabilna w obrębie danego użycia, materializuj wynik **raz**:
`var stabilna = questions.Shuffle().ToArray();` i dalej operuj na `stabilna`.

**Kod:** [`code/linq-shuffle/`](code/linq-shuffle/), dowód `CS1061`:
[`code/compat-check/`](code/compat-check/)

---

## 2️⃣ `JsonSerializerOptions.Strict` i `AllowDuplicateProperties` — JSON, który potrafi odmówić

### 😤 Problem
JSON jako format nie zabrania duplikatów kluczy w obiekcie — `{"a":1,"a":2}`
jest syntaktycznie poprawnym JSON-em. RFC 8259 wprost mówi, że zachowanie przy
duplikacie jest zależne od implementacji, i **ostrzega**, że to źródło
niejednoznaczności między różnymi parserami. `System.Text.Json` do tej pory
zawsze po cichu brał **ostatnią** wartość i milczał — dokładnie tak jak
większość innych parserów, co samo w sobie jest ryzykiem: jeśli dwa różne
komponenty systemu (np. warstwa walidacji i warstwa przetwarzania) parsują ten
sam JSON różnymi bibliotekami, a jedna weźmie pierwszą wartość, a druga
ostatnią, atakujący może "przemycić" wartość, którą zobaczy tylko jeden z tych
komponentów.

### ✨ Co się zmieniło
.NET 10 dodaje w `System.Text.Json`: `JsonDocumentOptions.AllowDuplicateProperties`
(bool, domyślnie `true` — zachowuje stare, tolerancyjne zachowanie) oraz nowy,
gotowy preset `JsonSerializerOptions.Strict` / `JsonSerializerDefaults.Strict`,
który łączy w jednym miejscu kilka bardziej rygorystycznych zachowań: odrzuca
duplikaty właściwości **i** odrzuca nieznane właściwości (odpowiednik
`JsonUnmappedMemberHandling.Disallow`). Sprawdzone empirycznie: **żadne z tych
dwóch API nie istnieje w .NET 9** — na SDK 9.0.316 `JsonSerializerOptions.Strict`
daje `CS0117` (dowód niżej).

```csharp
const string dupJson = """{"a":1,"a":2}""";

// Domyślnie - jak zawsze - cicha tolerancja, ostatnia wartość wygrywa:
var lenient = JsonSerializer.Deserialize<Rekord>(dupJson);
// lenient.A == 2, bez wyjątku

// .NET 10: jawna, twarda odmowa
var strictOpts = new JsonSerializerOptions(JsonSerializerOptions.Strict);
JsonSerializer.Deserialize<Rekord>(dupJson, strictOpts);
// rzuca JsonException: "Duplicate property 'a' encountered..."
```

### 🖥️ Prawdziwy output (`dotnet run --project json-strict`, ta maszyna)
```
--- 1. Domyslne zachowanie: duplikat klucza JSON jest CICHO tolerowany ---
JSON wejsciowy: {"a":1,"a":2}
JsonDocument.Parse (domyslne opcje) - bez wyjatku, GetProperty("a") = 2 (ostatnia wartosc wygrywa)
JsonSerializer.Deserialize<Rekord> (domyslne opcje) - bez wyjatku, A = 2

--- 2. JsonDocumentOptions.AllowDuplicateProperties = false: jawne odrzucenie duplikatu ---
JsonDocument.Parse (AllowDuplicateProperties=false) rzucil: Duplicate property 'a' encountered during deserialization.

--- 3. JsonSerializerOptions.Strict: nowy gotowy preset (duplikaty + nieznane wlasciwosci) ---
Deserialize<Rekord>(dupJson, Strict) rzucil: Duplicate property 'a' encountered during deserialization of type 'Rekord'.
Deserialize<Rekord>(unknownJson, Strict) rzucil: The JSON property 'unknown' could not be mapped to any .NET member contained in type 'Rekord'.
Dla porownania - domyslne opcje na tym samym JSON z nieznana wlasciwoscia: bez wyjatku, A = 1

--- 4. Strict jako JsonSerializerDefaults (do wspolnej konfiguracji np. w ASP.NET Core) ---
JsonSerializerOptions z JsonSerializerDefaults.Strict utworzone: True
```

### 🔬 Dowód „przed i po" (SDK 9.0.316, `net9.0`)
```
error CS0117: 'JsonSerializerOptions' does not contain a definition for 'Strict'
```

### 💡 Co to zmienia w praktyce
- Można teraz w jednym miejscu (`JsonSerializerOptions.Strict` albo
  `JsonSerializerDefaults.Strict` przy konfiguracji np. `AddControllers().AddJsonOptions`)
  przełączyć cały serializer w tryb "podejrzliwy": odrzuca zarówno duplikaty
  właściwości, jak i pola, których model C# w ogóle nie zna — dwa różne źródła
  niejednoznaczności zamknięte jedną flagą, bez ręcznego składania
  `JsonUnmappedMemberHandling` + własnej walidacji duplikatów.
- `JsonDocumentOptions.AllowDuplicateProperties = false` działa na niższym
  poziomie (`JsonDocument`/`JsonElement`), więc nadaje się też tam, gdzie nie
  masz modelu C# do deserializacji — np. w middleware walidującym surowy JSON
  przed przekazaniem dalej.
- Domyślne zachowanie **się nie zmieniło** — `AllowDuplicateProperties` domyślnie
  to `true`, więc istniejący kod nie dostanie niespodziewanych wyjątków po
  aktualizacji do .NET 10. To jest opt-in, nie zaostrzenie domyślnego
  zachowania.

### ⚠️ Haczyk — `Strict` to więcej niż "odrzuć duplikaty"
Zmierzone realnie (sekcja 3 w kodzie): `JsonSerializerOptions.Strict` rzuca
wyjątek nie tylko na duplikacie, ale też na zwykłej nieznanej właściwości
(`{"a":1,"unknown":123}`), której domyślny `JsonSerializerOptions` w ogóle by
nie zauważył. Jeśli używasz `Strict` tylko po to, żeby złapać duplikaty, a Twój
JSON legalnie zawiera pola spoza modelu C# (np. wersjonowane API, gdzie klient
zawsze wysyła nowsze pola niż zna serwer), dostaniesz fałszywie pozytywne
odrzucenia z zupełnie innego powodu. To pojedynczy, gotowy preset "surowego"
trybu, a nie osobny przełącznik wyłącznie na duplikaty — jeśli potrzebujesz
tylko odrzucania duplikatów bez odrzucania nieznanych pól, sięgnij po
`JsonDocumentOptions.AllowDuplicateProperties` na niższym poziomie zamiast po
cały preset `Strict`.

**Kod:** [`code/json-strict/`](code/json-strict/), dowód `CS0117`:
[`code/compat-check/`](code/compat-check/)

---

## 📎 Jak zweryfikowano „co jest nowe w .NET 10"

Zamiast zgadywać z pamięci, w tej sesji porównano realną powierzchnię API
`System.Linq.dll` i `System.Text.Json.dll` między zainstalowanym SDK **9.0.316**
a **10.0.400** przez refleksję (`MetadataLoadContext` + `GetExportedTypes()` /
`GetMembers()`, różnica zbiorów sygnatur). Skrypt porównawczy nie wszedł do
repo (uruchamiany tymczasowo poza katalogiem tego wydania, potem usunięty) —
ale każda z dwóch opisanych dziś funkcji została **osobno** potwierdzona
realnym błędem kompilatora na `net9.0` (`CS1061`, `CS0117` — zobacz
`code/compat-check/`), więc "nowość w .NET 10" nie jest tu założeniem, tylko
zmierzonym faktem.

---

## 📎 Jak uruchomić
Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #7 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
