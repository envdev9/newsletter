# Kod do wydania #18 — `JsonKnownReferenceHandler` i `FrozenDictionary.Create` (.NET 10)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (sprawdzone na `10.0.400`). `json-known-reference-handler` i
`frozen-create-span` celują w `net10.0`; `compat-check-*` celowo w `net9.0` (kompilowane tu
SDK 10.0.400 z pakietem referencyjnym net9; wymagają zainstalowanego SDK/pakietu 9.x).
Brak zależności NuGet, brak sieci.

## Fragment prasówki, którego dotyczy ten kod

> `JsonKnownReferenceHandler` (`Unspecified`/`Preserve`/`IgnoreCycles`) + właściwość
> `[JsonSourceGenerationOptions(ReferenceHandler = ...)]` (.NET 10): obsługa cykli w
> kontekście source-gen konfigurowana atrybutem. Na `net9.0`: `CS0246`/`CS0103`. Haczyki:
> `IgnoreCycles` wstawia `null` w miejsce cyklu; `Preserve` zmienia kształt JSON (`$id`,
> `$values`) i bez niego odbiorca się wywraca; `Unspecified` = brak obsługi.
>
> `FrozenDictionary.Create(ReadOnlySpan<KeyValuePair<,>>)` (+ wariant z komparatorem PIERWSZYM):
> słownik prosto ze spana/literału. Na `net9.0`: `CS0117` (`FrozenSet.Create(span)` jednak
> istnieje na net9.0). Haczyki: typy trzeba podać jawnie; duplikaty kluczy — ostatni wygrywa
> bez wyjątku; źródło jest kopiowane; alokacje: 8371 KB (span) vs 12146 KB (tablica
> `ToFrozenDictionary`) vs 8371 KB (przez `Dictionary`), przyczyny nie badano.

## 1. json-known-reference-handler

```bash
dotnet run --project json-known-reference-handler
```

Output (zweryfikowany):

```
--- 1. Co kontekst faktycznie ustawil w Options.ReferenceHandler ---
Bez atrybutu:        null
Preserve:            PreserveReferenceHandler
IgnoreCycles:        IgnoreReferenceHandler
Unspecified (jawne): null
--- 2. Bez obslugi referencji: cykl ---
RZUCILO InvalidOperationException: CurrentDepth (64) is equal to or larger than the maximum allowed depth of 64. Cannot write the next JSON objec...
--- 3. Preserve (z atrybutu source-gen): $id / $ref ---
{"$id":"1","Imie":"Jan","Szef":{"$id":"2","Imie":"Anna","Szef":null,"Podwladni":{"$id":"3","$values":[{"$ref":"1"},{"$id":"4","Imie":"Ewa","Szef":{"$ref":"2"},"Podwladni":{"$id":"5","$values":[]}}]}},"Podwladni":{"$id":"6","$values":[]}}
po deserializacji: wroc.Szef.Podwladni[0] == wroc ? True
--- 4. IgnoreCycles: cykl zamieniony na null ---
{"Imie":"Jan","Szef":{"Imie":"Anna","Szef":null,"Podwladni":[null,{"Imie":"Ewa","Szef":null,"Podwladni":[]}]},"Podwladni":[]}
--- 5. Unspecified jawnie = brak obslugi ---
RZUCILO InvalidOperationException: CurrentDepth (64) is equal to or larger than the maximum allowed depth of 64. Cannot write the next JSON objec...
--- 6. Deserializacja Preserve z kontekstu bez Preserve ---
RZUCILO JsonException: The JSON value could not be converted to System.Collections.Generic.List`1[Pracownik]. Path: $.Szef.Podwladni ...
--- 7. Stary sposob (dziala tez na net9.0): opcje przekazane do konstruktora kontekstu ---
{"$id":"1","Imie":"Jan","Szef":{"$id":"2","Imie":"Anna","Sze...
```

## 2. frozen-create-span

```bash
dotnet run -c Release --project frozen-create-span
```

Output (zweryfikowany, dwa przebiegi, identyczne liczby):

```
--- 1. FrozenDictionary.Create z ReadOnlySpan<KeyValuePair<,>> (collection expression) ---
Count=3, PL=48, TryGetValue("XX")=False
--- 2. Z komparatorem: UWAGA na kolejnosc argumentow (komparator PIERWSZY) ---
ci["PL"]=48, ci["De"]=49, Comparer=OrdinalIgnoreCaseComparer
--- 3. Ze stackalloc (struktury bez referencji; tu int->int) ---
kwadraty: 0->0, 1->1, 2->4, 3->9  (zrodlo zmutowane po Create: kwadraty[0]=0)
--- 4. Duplikaty kluczy ---
Create(span):         Count=2, a=2
ToFrozenDictionary:   Count=2, a=2
Dictionary.Add:       RZUCILO ArgumentException
--- 5. Pusty span ---
Count=0, ReferenceEquals(Empty)=True
--- 6. Dla porownania: FrozenSet.Create(ReadOnlySpan<T>) - istnieje juz na net9.0, to NIE nowosc ---
Count=2, Contains(root)=True
ci Contains(admin)=True
--- 7. Alokacje: Create(span) vs ToFrozenDictionary(IEnumerable) vs przez Dictionary ---
Create(span)                     8371 KB  (wynik: WithOptionalValues`3)
ToFrozenDictionary(array)       12146 KB  (wynik: WithOptionalValues`3)
new Dictionary + ToFrozen        8371 KB  (wynik: WithOptionalValues`3)
```

## 3. compat-check-known-reference i compat-check-frozen (celowo NIE kompilują się na .NET 9)

```bash
dotnet build compat-check-known-reference
dotnet build compat-check-frozen
```

Oczekiwane (zweryfikowane): `compat-check-known-reference` → `CS0246` (`ReferenceHandler`) i
`CS0103` (`JsonKnownReferenceHandler`); `compat-check-frozen` → `CS0117`
(`FrozenDictionary` nie ma `Create`; linia z `FrozenSet.Create` błędu nie daje).

## Zweryfikowane / niezweryfikowane

- Zweryfikowane `dotnet run` (SDK 10.0.400): oba programy, wszystkie sekcje.
- Zweryfikowane `dotnet build` (TFM net9.0, kompilacja SDK 10.0.400 — nie SDK 9.0.316): błędy jak wyżej.
- Niezweryfikowane: kod wygenerowany przez source generator, `Preserve` z konstruktorami
  parametrycznymi, ASP.NET, czasy wykonania, przyczyna równych alokacji w ścieżce przez
  `Dictionary`, .NET 11 (brak SDK), dokumentacja online.
