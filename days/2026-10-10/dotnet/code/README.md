# Kod do wydania #17 — JSON z `PipeReader` i `ActivitySourceOptions` (.NET 10)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (sprawdzone na `10.0.400`). `pipereader-json` i
`activitysource-options` celują w `net10.0`; `compat-check-pipe` i `compat-check-activity`
celowo w `net9.0` (potrzebują SDK 9.x obok; sprawdzone na `9.0.316`). Brak zależności NuGet,
brak sieci (wszystko w pamięci).

## Fragment prasówki, którego dotyczy ten kod

> `JsonSerializer.DeserializeAsync<T>(PipeReader)` i `DeserializeAsyncEnumerable<T>(PipeReader)`
> (.NET 10) czytają JSON bezpośrednio z `System.IO.Pipelines`, bez `AsStream()`. Na `net9.0`:
> `CS1503` (jedyne przeciążenie przyjmuje `Stream`). Haczyki: `DeserializeAsync` wraca dopiero po
> `Complete()` writera, nawet gdy obiekt jest kompletny; reader nie jest zamykany przez
> serializator; drugi dokument lub urwany string → `JsonException`. Pamięć dla ~58 MB JSON:
> 58 MB (strumieniowo) vs 166-171 MB (`List<T>`).
>
> `ActivitySourceOptions` (`Version`, `Tags`, `TelemetrySchemaUrl`) + `new ActivitySource(options)`:
> metadane źródła telemetrii widoczne w `ActivityListener.ShouldListenTo`. Na `net9.0`: `CS0246`/`CS1061`.
> Haczyki: stary konstruktor nie ustawi schematu; opcje kopiowane przy konstrukcji; URL niewalidowany;
> kolejność tagów nie jest zachowana; schemat nie scala źródeł o tej samej nazwie.

## 1. pipereader-json

```bash
dotnet run --project pipereader-json
```

Output (kawałek `2.` zależy od czasu: ~0/50/100 ms):

```
--- 1. DeserializeAsync<T>(PipeReader): obiekt skladany z kawalkow ---
wynik: Id=7 Nazwa=Gdansk Tagi=[a,b]
--- 2. DeserializeAsyncEnumerable<T>(PipeReader): top-level tablica, element po elemencie ---
  po ~  0 ms: Id=1 (a)
  po ~ 50 ms: Id=2 (b)
  po ~100 ms: Id=3 (c)
--- 3. Haczyk: DeserializeAsync czeka na koniec strumienia, nie na koniec obiektu ---
500 ms po kompletnym obiekcie, writer otwarty: zakonczone = False
po Complete() writera: Id=1, zadanie.IsCompletedSuccessfully = True
reader po deserializacji: ReadAsync dziala, Buffer.Length=0, IsCompleted=True
--- 4. Haczyk: dane po obiekcie (drugi dokument) ---
RZUCILO JsonException: '{' is invalid after a single JSON value. Expected end of data. Path: $ | LineNumber: 0 | BytePositi...
--- 5. Haczyk: urwany strumien ---
RZUCILO JsonException: Expected end of string, but instead reached end of data. Path: $.Nazwa | LineNumber: 0 | BytePositio...
--- 6. Pamiec: patrz  dotnet run -c Release -- stream  /  -- list ---
```

Pomiar pamięci (osobne procesy; wartości zależą od maszyny):

```bash
dotnet run -c Release --project pipereader-json -- stream
dotnet run -c Release --project pipereader-json -- list
```

```
tryb=stream: 250000 elementow, PeakWorkingSet64 = 58 MB, 1884 ms
tryb=list: 250000 elementow, PeakWorkingSet64 = 171 MB, 2294 ms
```

## 2. activitysource-options

```bash
dotnet run --project activitysource-options
```

Output (pełny):

```
--- 1. ActivitySourceOptions: wersja, tagi i TelemetrySchemaUrl w jednym obiekcie ---
Name=Sklep.Zamowienia Version=2.3.1
TelemetrySchemaUrl=https://opentelemetry.io/schemas/1.27.0
Tags=srodowisko=demo, zespol=platforma
--- 2. Listener widzi te metadane w ShouldListenTo ---
ShouldListenTo(Sklep.Zamowienia): schema=https://opentelemetry.io/schemas/1.27.0, tagi=2
ShouldListenTo(): schema=(null), tagi=0
  [stopped] PrzyjmijZamowienie, Source.TelemetrySchemaUrl=https://opentelemetry.io/schemas/1.27.0
--- 3. Stary konstruktor (name, version) nie ma jak podac schematu ---
ShouldListenTo(Sklep.Stary): schema=(null), tagi=0
stary: Version=1.0.0, TelemetrySchemaUrl=(null), Tags=(null)
--- 4. Haczyki ---
Name=null: RZUCILO ArgumentNullException
domyslnie: Version=, TelemetrySchemaUrl=(null), Tags=(null)
ShouldListenTo(Sklep.Mutacja): schema=https://example.invalid/v1, tagi=0
po mutacji opcji: zrodlo.TelemetrySchemaUrl=https://example.invalid/v1
ShouldListenTo(Sklep.Zly): schema=to nie jest url, tagi=0
niepoprawny URL przyjety bez walidacji: 'to nie jest url'
ShouldListenTo(Sklep.Dup): schema=(null), tagi=0
ShouldListenTo(Sklep.Dup): schema=https://opentelemetry.io/schemas/1.27.0, tagi=0
dwa zrodla o tej samej nazwie i wersji: d1.schema=(null), d2.schema=https://opentelemetry.io/schemas/1.27.0
--- 5. Porownanie: Meter ma analogiczne MeterOptions.TelemetrySchemaUrl ---
Meter.TelemetrySchemaUrl=https://opentelemetry.io/schemas/1.27.0
```

(Wiersz `ShouldListenTo()` z pustą nazwą pochodzi od źródła, którego pochodzenia nie badaliśmy.
Sprawdziliśmy tylko, że `MeterOptions.TelemetrySchemaUrl` działa w .NET 10.)

## 3. compat-check-pipe i compat-check-activity (celowo NIE kompilują się na .NET 9)

```bash
dotnet build compat-check-pipe
dotnet build compat-check-activity
```

Oczekiwane (zweryfikowane): `compat-check-pipe` → 2× `CS1503` (`PipeReader` → `Stream`);
`compat-check-activity` → `CS0246` (`ActivitySourceOptions`) i `CS1061` (`TelemetrySchemaUrl`).

## Zweryfikowane / niezweryfikowane

- Zweryfikowane `dotnet run` (SDK 10.0.400): oba programy, wszystkie sekcje, w pamięci.
- Zweryfikowane `dotnet build` (net9.0, SDK 9.0.316): błędy jak wyżej.
- Niezweryfikowane: Kestrel/`BodyReader`, prawdziwy socket, source-generated `JsonTypeInfo`,
  pakiet OpenTelemetry i eksport `schema_url`, wielowątkowość `ActivitySource`, .NET 11 (brak SDK),
  dokumentacja online, wersja, w której pojawił się `MeterOptions`.
