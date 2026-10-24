<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #18 — 11 października 2026

![.NET](https://img.shields.io/badge/.NET-10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![BCL](https://img.shields.io/badge/BCL-JsonKnownReferenceHandler%20%2B%20FrozenDictionary.Create-blue?style=for-the-badge)

## Cykle w JSON-ie ze source generatora wreszcie z atrybutu, a `FrozenDictionary` powstaje prosto ze spana

</div>

---

> _"CurrentDepth (64) is equal to or larger than the maximum allowed depth of 64."_ — tak
> `System.Text.Json` zgłasza cykl w grafie obiektów, gdy nikt nie włączył obsługi referencji.
> Zmierzone w tej sesji. Dziś: jak włączyć ją **jednym atrybutem** na kontekście source-gen.

Z listy „zostało z diffu" (diff refleksyjny runtime 9.0.18 vs 10.0.11 z wydania #15) bierzemy
dwie rzeczy: **konfigurację obsługi referencji w `[JsonSourceGenerationOptions]`**
(`JsonKnownReferenceHandler`) i **`FrozenDictionary.Create(ReadOnlySpan<KeyValuePair<,>>)`**.
SDK .NET 11 nadal nie ma na tej maszynie (`dotnet --list-sdks`: 8.0.422, 8.0.425, 9.0.316,
10.0.400), więc zostajemy przy .NET 10. Kod w [`code/`](code/).

| # | Funkcja | Namespace | Status |
|---|---------|-----------|--------|
| 1️⃣ | `JsonKnownReferenceHandler` w `[JsonSourceGenerationOptions]` | `System.Text.Json.Serialization` | ✅ zweryfikowane `dotnet run` |
| 2️⃣ | `FrozenDictionary.Create(ReadOnlySpan<KeyValuePair<,>>)` | `System.Collections.Frozen` | ✅ zweryfikowane `dotnet run -c Release` |

---

## 1️⃣ `JsonKnownReferenceHandler` — `Preserve` / `IgnoreCycles` z atrybutu

### 😤 Problem
`ReferenceHandler.Preserve` i `ReferenceHandler.IgnoreCycles` to obiekty — nie da się ich
wstawić jako argumentu atrybutu (atrybuty przyjmują tylko stałe). Dlatego
`[JsonSourceGenerationOptions]`, który konfiguruje kontekst generowany w czasie kompilacji,
nie miał właściwości `ReferenceHandler`. Chcąc mieć cyklicznie bezpieczny kontekst, trzeba
było ręcznie konstruować go z `JsonSerializerOptions` — i zapomnieć o statycznym `Default`
z czystą konfiguracją deklaratywną.

### ✨ Co się zmieniło
Nowy enum `JsonKnownReferenceHandler` (`Unspecified`, `Preserve`, `IgnoreCycles`) i nowa
właściwość `JsonSourceGenerationOptionsAttribute.ReferenceHandler`. Enum jest stałą, więc
mieści się w atrybucie:

```csharp
[JsonSourceGenerationOptions(ReferenceHandler = JsonKnownReferenceHandler.Preserve)]
[JsonSerializable(typeof(Pracownik))]
public partial class PreserveCtx : JsonSerializerContext { }
```

### 🖥️ Prawdziwy output (`dotnet run --project json-known-reference-handler`, ta maszyna)
Graf: `Jan` i `Ewa` mają szefa `Anna`, a `Anna.Podwladni` zawiera ich oboje (cykl).
```
Bez atrybutu:        null
Preserve:            PreserveReferenceHandler
IgnoreCycles:        IgnoreReferenceHandler
Unspecified (jawne): null
--- 2. Bez obslugi referencji: cykl ---
RZUCILO InvalidOperationException: CurrentDepth (64) is equal to or larger than the maximum allowed depth of 64...
--- 3. Preserve ---
{"$id":"1","Imie":"Jan","Szef":{"$id":"2","Imie":"Anna","Szef":null,"Podwladni":{"$id":"3","$values":[{"$ref":"1"},{"$id":"4","Imie":"Ewa","Szef":{"$ref":"2"},...
po deserializacji: wroc.Szef.Podwladni[0] == wroc ? True
--- 4. IgnoreCycles ---
{"Imie":"Jan","Szef":{"Imie":"Anna","Szef":null,"Podwladni":[null,{"Imie":"Ewa","Szef":null,"Podwladni":[]}]},"Podwladni":[]}
```

### 🔬 Dowód „przed i po" (target `net9.0`, kompilacja SDK 10.0.400 z pakietem referencyjnym net9)
```
error CS0246: The type or namespace name 'ReferenceHandler' could not be found
error CS0103: The name 'JsonKnownReferenceHandler' does not exist in the current context
```
(Pierwszy błąd dotyczy nazwanego argumentu `ReferenceHandler =` — atrybut na net9.0 takiej
właściwości nie ma.) Stara droga nadal działa i została sprawdzona: `new BezRef(new
JsonSerializerOptions { ReferenceHandler = ReferenceHandler.Preserve })`.

### 💡 Co to zmienia w praktyce
- Konfiguracja cykli jest **deklaratywna** i siedzi przy kontekście; `Ctx.Default` od razu
  zachowuje się poprawnie — brak miejsca, w którym ktoś zapomni przekazać opcje.
- Dla grafów z relacją rodzic–dziecko (EF Core nawigacje, drzewa kategorii) wybierasz
  świadomie: `Preserve` zachowuje tożsamość obiektów, `IgnoreCycles` daje „płaski" JSON.

### ⚠️ Haczyk A — `IgnoreCycles` gubi dane, nie tylko cykl
W wyniku `IgnoreCycles` pierwsza pozycja `Podwladni` Anny to `null` — to Jan, którego
właśnie serializujemy (to on jest „przodkiem" w bieżącej ścieżce). Na liście pojawia się
`null`, nie brak elementu. Po stronie odbiorcy trzeba to uwzględnić; nie da się odtworzyć grafu.

### ⚠️ Haczyk B — `Preserve` zmienia kształt JSON-a (i kontrakt)
Listy stają się obiektami `{"$id":...,"$values":[...]}`. Czytający JSON bez obsługi
`$id`/`$ref` (np. frontend, inny kontekst) się wywróci — zmierzone: deserializacja z kontekstu
bez `Preserve` → `JsonException: The JSON value could not be converted to List<Pracownik>. Path: $.Szef.Podwladni`.
Nie używaj `Preserve` na publicznym API bez uzgodnienia z klientami.

### ⚠️ Haczyk C — `Unspecified` to po prostu „brak"
Jawne `Unspecified` daje `Options.ReferenceHandler == null` — identycznie jak brak
właściwości, cykl rzuca. Wartość istnieje głównie jako domyślna dla atrybutu.

**Kod:** [`code/json-known-reference-handler/`](code/json-known-reference-handler/), dowód
niekompilacji: [`code/compat-check-known-reference/`](code/compat-check-known-reference/)

---

## 2️⃣ `FrozenDictionary.Create(ReadOnlySpan<KeyValuePair<,>>)`

### 😤 Problem
`FrozenDictionary` (od .NET 8) buduje się metodą `ToFrozenDictionary()` na `IEnumerable<>`.
Kiedy dane masz w tablicy, `stackalloc` albo literale kolekcji, przechodziłeś przez
`IEnumerable` (interfejs, wirtualne wywołania, ścieżka „nieznany typ"). Dla zbioru
`FrozenSet.Create(ReadOnlySpan<T>)` istniało, dla słownika — nie.

### ✨ Co się zmieniło
Statyczne `FrozenDictionary.Create<TKey,TValue>(ReadOnlySpan<KeyValuePair<TKey,TValue>>)`
oraz wariant z komparatorem — **komparator jest PIERWSZYM argumentem**
(`Create(IEqualityComparer<TKey>, ReadOnlySpan<...>)`).

```csharp
var kody = FrozenDictionary.Create<string, int>([new("PL", 48), new("DE", 49)]);
var ci   = FrozenDictionary.Create<string, int>(StringComparer.OrdinalIgnoreCase, [new("pl", 48)]);
```

### 🖥️ Prawdziwy output (`dotnet run -c Release --project frozen-create-span`, ta maszyna)
```
Count=3, PL=48, TryGetValue("XX")=False
ci["PL"]=48, ci["De"]=49, Comparer=OrdinalIgnoreCaseComparer
kwadraty: 0->0, 1->1, 2->4, 3->9  (zrodlo zmutowane po Create: kwadraty[0]=0)
Create(span):         Count=2, a=2
ToFrozenDictionary:   Count=2, a=2
Dictionary.Add:       RZUCILO ArgumentException
Count=0, ReferenceEquals(Empty)=True
```

### 🔬 Dowód „przed i po" (target `net9.0`)
```
error CS0117: 'FrozenDictionary' does not contain a definition for 'Create'
```
Uczciwa korekta: `FrozenSet.Create(ReadOnlySpan<T>)` kompiluje się na `net9.0` **bez błędu** —
to nie jest nowość .NET 10 (w kodzie pokazane tylko jako porównanie).

### 💡 Co to zmienia w praktyce
- Dane statyczne (tabele kodów, słowniki konfiguracyjne, parsery) budujesz wprost z
  literału `[ new(...), new(...) ]` bez pośredniego `Dictionary`/`List`.
- Źródło jest **kopiowane**: mutacja spana po `Create` nie wpływa na słownik (zmierzone).

### ⚠️ Haczyk A — wnioskowanie typów nie działa z collection expression
`FrozenDictionary.Create([new("PL", 48)])` nie wyprowadzi `TKey/TValue` — trzeba podać
`<string, int>` jawnie (wszystkie nasze wywołania to robią).

### ⚠️ Haczyk B — duplikaty kluczy: ostatni wygrywa, bez wyjątku
`Create(span)` i `ToFrozenDictionary()` dały oba `a=2`; `Dictionary.Add` rzuca
`ArgumentException`. Literówka w tabeli zostanie więc **połknięta**.

### ⚠️ Haczyk C — oszczędność alokacji nie jest oczywista
Zmierzone `GC.GetAllocatedBytesForCurrentThread` dla 100 000 par `int→int` (po rozgrzewce,
powtórzone, wynik identyczny):

| Droga | Alokacje |
|-------|----------|
| `FrozenDictionary.Create(span)` | 8371 KB |
| `tablica.ToFrozenDictionary()` | 12146 KB |
| `new Dictionary(...).ToFrozenDictionary()` | 8371 KB |

Czyli `Create(span)` bije `ToFrozenDictionary` na tablicy o ~3,7 MB, ale **nie** przez
`Dictionary` — tu wyszło tyle samo. Nie wyjaśniliśmy dlaczego (nie badaliśmy źródeł
runtime'u). Czasu nie mierzyliśmy — nie wyciągamy wniosków o szybkości. Żadnego twierdzenia
„szybsze/bez kopiowania" z tego nie wolno wyprowadzać.

**Kod:** [`code/frozen-create-span/`](code/frozen-create-span/), dowód `CS0117`:
[`code/compat-check-frozen/`](code/compat-check-frozen/)

---

## 📎 Jak zweryfikowano
- `compat-check-known-reference` (`CS0246` + `CS0103`) i `compat-check-frozen` (`CS0117`) na
  `net9.0`; **uwaga:** kompilowane SDK 10.0.400 z pakietem referencyjnym `net9.0`, nie SDK
  9.0.316 (porównanie API jest tym samym, ale to inna ścieżka niż w poprzednich wydaniach).
- `json-known-reference-handler` i `frozen-create-span` uruchomione `dotnet run` (SDK 10.0.400;
  ten drugi w `-c Release`).
- **Niezweryfikowane:** wygenerowany przez source generator kod (nie czytaliśmy), `Preserve`
  z konstruktorami parametrycznymi/`required`, ASP.NET `JsonOptions`, polimorfizm +
  `$id`, `FrozenSet`/`FrozenDictionary.Create` na typach niestandardowych, czas budowy i
  wyszukiwania, .NET 11 (brak SDK), dokumentacja online (nie korzystano).
- Zostaje (z tego samego diffu): `OrderedDictionary.TryAdd(..., out int)`,
  `SlhDsa`/`CompositeMLDsa` → .NET 11, gdy pojawi się SDK, lub zejście do .NET 9.

---

## 📎 Jak uruchomić
Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wszystkie artykuły: 🔷 .NET — nowości w wersji](../README.md) · [spis rubryk](../../../README.md)

</div>
