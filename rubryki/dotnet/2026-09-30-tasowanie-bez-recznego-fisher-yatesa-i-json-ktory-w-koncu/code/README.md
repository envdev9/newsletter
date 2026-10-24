# Kod do wydania #6 — LINQ `Shuffle` i `System.Text.Json` `Strict` (.NET 10 BCL)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`). Sprawdzone na `10.0.400`.
Projekty `linq-shuffle` i `json-strict` celują w `net10.0`; `compat-check` celowo
celuje w `net9.0` (wymaga zainstalowanego SDK 9.x obok — sprawdzone na `9.0.316`), żeby
pokazać realny błąd kompilatora "przed". Brak zależności NuGet.

## Fragment prasówki, którego dotyczy ten kod

> `System.Linq.Enumerable.Shuffle<T>()` — nowa metoda tasująca dowolny
> `IEnumerable<T>`, bez ręcznego Fisher-Yatesa i bez wolnego
> `OrderBy(_ => Guid.NewGuid())`. Sprawdzone: nie istnieje w .NET 9 (`CS1061`).
> Haczyk zmierzony realnie: to leniwe LINQ — bez materializacji (`.ToArray()`)
> każda kolejna enumeracja tej samej zmiennej daje **inną** kolejność.
>
> `System.Text.Json.JsonSerializerOptions.Strict` /
> `JsonDocumentOptions.AllowDuplicateProperties` — nowy, jawny sposób na
> odrzucenie duplikatów kluczy JSON (`{"a":1,"a":2}`), które dotąd
> `System.Text.Json` po cichu tolerował (ostatnia wartość wygrywa). Sprawdzone:
> `Strict` nie istnieje w .NET 9 (`CS0117`). Haczyk zmierzony realnie: `Strict`
> to gotowy preset, który oprócz duplikatów odrzuca też każdą nieznaną
> właściwość — nie jest to osobny przełącznik wyłącznie na duplikaty.

## 1. linq-shuffle (`Enumerable.Shuffle<T>`)

```bash
dotnet run --project linq-shuffle
```

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

--- 3. Poprawny idiom: zmaterializuj RAZ, jesli kolejnosc ma byc stabilna ---
stabilna kolejnosc (ta sama przy kazdym odczycie tej tablicy): 1,3,10,7,4,5,6,2,8,9
odczyt ponowny tej samej tablicy: 1,3,10,7,4,5,6,2,8,9

--- 4. Dziala na dowolnym IEnumerable<T>, nie tylko na tablicy ---
potasowane litery z lazy source: B,C,D,A
```

(Konkretna kolejność losowa będzie inna przy każdym uruchomieniu — to normalne,
`Shuffle()` korzysta z `Random.Shared`.)

## 2. json-strict (`JsonSerializerOptions.Strict` / `AllowDuplicateProperties`)

```bash
dotnet run --project json-strict
```

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

## 3. compat-check (celowo NIE kompiluje się na .NET 9)

Projekt celuje w `net9.0` i domyślnie ma aktywny **Dowód 1** (`Enumerable.Shuffle`):

```bash
dotnet build compat-check
```

Oczekiwany wynik: `error CS1061: 'int[]' does not contain a definition for
'Shuffle' and no accessible extension method 'Shuffle' accepting a first
argument of type 'int[]' could be found (are you missing a using directive or
an assembly reference?)`.

Żeby zobaczyć **Dowód 2** (`JsonSerializerOptions.Strict`), zakomentuj blok
"Dowod 1" w `compat-check/Program.cs`, odkomentuj blok "Dowod 2" (i `using
System.Text.Json;`), i zbuduj ponownie. Oczekiwany wynik: `error CS0117:
'JsonSerializerOptions' does not contain a definition for 'Strict'`. Oba błędy
zostały realnie zweryfikowane w tej sesji (SDK 9.0.316) — output wklejony
powyżej 1:1, bez zmyślania.

## Jak zweryfikowano „co jest nowe w .NET 10"

Zamiast zgadywać z pamięci, które API są nowe, w tej sesji porównano realną
powierzchnię API `System.Linq.dll` i `System.Text.Json.dll` między
zainstalowanym SDK **9.0.316** a **10.0.400** przez refleksję
(`System.Reflection.MetadataLoadContext`, `PathAssemblyResolver` wskazujący na
pliki `.dll` z odpowiedniego katalogu `shared/Microsoft.NETCore.App/<wersja>`,
porównanie zbiorów sygnatur `GetExportedTypes()`/`GetMembers()`). Znaleziono
m.in. `Enumerable.Shuffle`, `Enumerable.Sequence`/`InfiniteSequence`,
`JsonSerializerOptions.Strict`/`JsonSerializerDefaults.Strict`,
`JsonDocumentOptions.AllowDuplicateProperties` i kilkanaście innych nowych
przeciążeń (np. `DeserializeAsyncEnumerable` na `PipeReader`). Z tej listy
wybrano dwie funkcje opisane w artykule i każdą potwierdzono osobno realną
kompilacją `error CS1061`/`CS0117` na `net9.0`. Skrypt porównawczy (projekt
tymczasowy, referencja do `System.Reflection.MetadataLoadContext` z NuGet) nie
wszedł do repo — był w katalogu tymczasowym poza tym wydaniem i został usunięty
po użyciu; powyższe błędy kompilatora i output programów są jego bezpośrednim,
wklejonym efektem.

## Zweryfikowane / niezweryfikowane — podsumowanie

- Zweryfikowane realnym `dotnet build`/`dotnet run` (SDK 10.0.400): `linq-shuffle`
  (wszystkie 4 sekcje, w tym haczyk z sekcji 2), `json-strict` (wszystkie 4
  sekcje), `compat-check` (oba błędy, SDK 9.0.316, przełączane ręcznie
  komentarzem — w repo domyślnie zostawiony Dowód 1).
- Niezweryfikowane: czy `Enumerable.Shuffle` wewnętrznie korzysta dokładnie z
  algorytmu Fisher-Yatesa (nie sprawdzano implementacji w źródłach CoreLib,
  tylko obserwowalne zachowanie z zewnątrz — brak mutacji źródła, różny wynik
  przy każdej enumeracji); statystyczna jednostajność rozkładu permutacji z
  `Shuffle()` (nie testowano na dużej próbie, tylko pojedyncze uruchomienia
  pokazane w outpucie powyżej).
