<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #17 — 10 października 2026

![.NET](https://img.shields.io/badge/.NET-10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![BCL](https://img.shields.io/badge/BCL-PipeReader%20JSON%20%2B%20ActivitySourceOptions-blue?style=for-the-badge)

## `System.Text.Json` czyta prosto z `PipeReader`, a `ActivitySource` dostaje opcje i schemat telemetrii

</div>

---

> _"Expected end of string, but instead reached end of data."_ — tak `DeserializeAsync`
> z `PipeReader` reaguje na urwany strumień. Zmierzone w tej sesji. A haczyk, który nas
> zaskoczył bardziej: kompletny obiekt JSON **nie wystarcza**, żeby `DeserializeAsync` wrócił.

Z listy „zostało z diffu" (diff refleksyjny runtime 9.0.18 vs 10.0.11 z wydania #15)
bierzemy dziś dwie rzeczy z dwóch różnych światów: **JSON ze strumienia potokowego**
(`System.IO.Pipelines`, serwery i parsery protokołów) oraz **telemetrię**
(`System.Diagnostics.ActivitySource`, fundament OpenTelemetry w .NET). SDK .NET 11 nadal
nie ma na tej maszynie (`dotnet --list-sdks`: 8.0.422, 8.0.425, 9.0.316, 10.0.400),
więc zostajemy przy .NET 10. Kod w [`code/`](code/).

| # | Funkcja | Namespace | Status |
|---|---------|-----------|--------|
| 1️⃣ | `JsonSerializer.DeserializeAsync` / `DeserializeAsyncEnumerable` z `PipeReader` | `System.Text.Json` | ✅ w pełni zweryfikowane (w pamięci) |
| 2️⃣ | `ActivitySourceOptions` + `TelemetrySchemaUrl` | `System.Diagnostics` | ✅ zweryfikowane (bez eksportera OTel) |

---

## 1️⃣ JSON prosto z `PipeReader`

### 😤 Problem
`JsonSerializer.DeserializeAsync` znał `Stream`. Ale kod sieciowy na `System.IO.Pipelines`
(Kestrel, własne parsery protokołów, `SocketConnection`) ma w ręku `PipeReader`.
Żeby wrzucić go do serializatora, trzeba było opakować go `reader.AsStream()` — kolejna
warstwa kopiowania — albo ręcznie pętlić `ReadAsync`/`Utf8JsonReader` i radzić sobie ze
zdarzeniami „token rozerwany na granicy bufora".

### ✨ Co się zmieniło
W .NET 10 `JsonSerializer` ma przeciążenia przyjmujące `PipeReader` — zarówno
`DeserializeAsync<T>(PipeReader, ...)`, jak i `DeserializeAsyncEnumerable<T>(PipeReader, ...)`
(strumieniowanie elementów top-level tablicy).

```csharp
var pipe = new Pipe();
// ... ktos pisze kawalki JSON do pipe.Writer ...
var zam = await JsonSerializer.DeserializeAsync<Zamowienie>(pipe.Reader);

await foreach (var z in JsonSerializer.DeserializeAsyncEnumerable<Zamowienie>(pipe.Reader))
    Console.WriteLine(z!.Id);
```

### 🖥️ Prawdziwy output (`dotnet run --project pipereader-json`, ta maszyna)
Producent wpisuje JSON w kawałkach, z opóźnieniem, dzieląc go w środku tokenów:
```
--- 1. DeserializeAsync<T>(PipeReader): obiekt skladany z kawalkow ---
wynik: Id=7 Nazwa=Gdansk Tagi=[a,b]
--- 2. DeserializeAsyncEnumerable<T>(PipeReader): top-level tablica, element po elemencie ---
  po ~  0 ms: Id=1 (a)
  po ~ 50 ms: Id=2 (b)
  po ~100 ms: Id=3 (c)
```
Element 2 przychodzi dopiero z drugim kawałkiem (+50 ms), element 3 z trzecim (+100 ms) —
czyli nie czekamy na koniec tablicy.

### 🔬 Dowód „przed i po" (target `net9.0`, SDK 9.0.316)
```
error CS1503: Argument 1: cannot convert from 'System.IO.Pipelines.PipeReader' to 'System.IO.Stream'   (x2)
```
Kompilator szuka jedynego pasującego przeciążenia (ze `Stream`) — tak wygląda brak API.

### 💡 Co to zmienia w praktyce
- Parser protokołu na `PipeReader` może oddać ciało JSON serializatorowi bez adaptera
  `AsStream()`.
- `DeserializeAsyncEnumerable` na potoku daje strumieniowanie z backpressure: producent
  jest wstrzymywany progami `Pipe`, a my trzymamy w pamięci tylko bieżący element.
  Zmierzone na ~58 MB JSON-u (250 000 elementów, `dotnet run -c Release`, próg pauzy
  writera 1 MB):

  | Tryb | PeakWorkingSet64 |
  |------|------------------|
  | `DeserializeAsyncEnumerable<T>` (element po elemencie) | 58 MB (2 przebiegi: 58, 58) |
  | `DeserializeAsync<List<T>>` (cała lista) | 166 i 171 MB |

  Czasy (1.9–2.7 s w obu trybach) wahały się między przebiegami bardziej niż różniły się
  między trybami — nie wyciągamy wniosków o szybkości.

### ⚠️ Haczyk A — `DeserializeAsync` wraca dopiero po `Complete()` writera
Wpisaliśmy **kompletny** obiekt JSON, writer zostawiliśmy otwarty:
```
500 ms po kompletnym obiekcie, writer otwarty: zakonczone = False
po Complete() writera: Id=1, zadanie.IsCompletedSuccessfully = True
```
Serializator czyta do końca strumienia (tak jak wersja ze `Stream`) — nie dostaje sygnału
„obiekt się skończył", bo dla dokumentu root to nie jest granica. Na długo żyjącym
połączeniu z wieloma wiadomościami **nie użyjesz `DeserializeAsync` do ramkowania** —
potrzebujesz własnych granic (długość, delimiter) i osobnego bufora na wiadomość.
Przy pierwszym podejściu nasz własny test zawiesił się dokładnie na tym.

### ⚠️ Haczyk B — `PipeReader` zostaje użyteczny i skonsumowany
Po deserializacji `reader.ReadAsync()` nadal działa (nie rzuca) i daje
`Buffer.Length=0, IsCompleted=True` — dane zostały zużyte do końca. Czyli: serializator
**nie** zakańcza readera (`CompleteAsync` zostaje po naszej stronie), ale też nie zostawia
nam nic „do dalszego czytania".

### ⚠️ Haczyk C — jak wygląda zły strumień
Drugi dokument zaraz po obiekcie i urwany string rzucają `JsonException`:
```
'{' is invalid after a single JSON value. Expected end of data. Path: $ | ...
Expected end of string, but instead reached end of data. Path: $.Nazwa | ...
```
W naszym teście nie znaleźliśmy sposobu na „weź pierwszy obiekt, resztę zostaw w potoku"
(nie badaliśmy przeciążeń z `JsonSerializerOptions` pod tym kątem).

**Kod:** [`code/pipereader-json/`](code/pipereader-json/), dowód `CS1503`: [`code/compat-check-pipe/`](code/compat-check-pipe/)

---

## 2️⃣ `ActivitySourceOptions` i `TelemetrySchemaUrl`

### 😤 Problem
`new ActivitySource(name, version)` to wszystko, co można było podać. Tymczasem
OpenTelemetry opisuje źródło telemetrii jeszcze dwoma rzeczami: **tagami zakresu**
(scope attributes, np. zespół) i **adresem schematu** (`schema_url`), czyli wskazaniem,
której wersji konwencji semantycznych używają nazwy atrybutów w spanach. Backend, który
zna schemat, może przetłumaczyć stare nazwy atrybutów na nowe. `Meter` dostał
`MeterOptions` z `TelemetrySchemaUrl` wcześniej (zweryfikowane niżej: działa w .NET 10;
nie sprawdzaliśmy, w której wersji dokładnie się pojawiło) — `ActivitySource` zostawał
bez odpowiednika.

### ✨ Co się zmieniło
Nowa klasa `ActivitySourceOptions` (nazwa w konstruktorze; `Version`, `Tags`,
`TelemetrySchemaUrl`) i konstruktor `ActivitySource(ActivitySourceOptions)`. Źródło
wystawia teraz `Tags` oraz `TelemetrySchemaUrl`.

```csharp
var opcje = new ActivitySourceOptions("Sklep.Zamowienia")
{
    Version = "2.3.1",
    TelemetrySchemaUrl = "https://opentelemetry.io/schemas/1.27.0",
    Tags = new KeyValuePair<string, object?>[] { new("zespol", "platforma"), new("srodowisko", "demo") },
};
using var zrodlo = new ActivitySource(opcje);
```

### 🖥️ Prawdziwy output (`dotnet run --project activitysource-options`, ta maszyna)
```
Name=Sklep.Zamowienia Version=2.3.1
TelemetrySchemaUrl=https://opentelemetry.io/schemas/1.27.0
Tags=srodowisko=demo, zespol=platforma
--- 2. Listener widzi te metadane w ShouldListenTo ---
ShouldListenTo(Sklep.Zamowienia): schema=https://opentelemetry.io/schemas/1.27.0, tagi=2
  [stopped] PrzyjmijZamowienie, Source.TelemetrySchemaUrl=https://opentelemetry.io/schemas/1.27.0
--- 3. Stary konstruktor (name, version) nie ma jak podac schematu ---
stary: Version=1.0.0, TelemetrySchemaUrl=(null), Tags=(null)
```
(Listener dostał też wywołanie `ShouldListenTo` dla źródła o pustej nazwie — nie badaliśmy,
skąd pochodzi; w tabeli powyżej je pominęliśmy, w pełnym wyniku w `code/README.md` jest.)

### 🔬 Dowód „przed i po" (target `net9.0`, SDK 9.0.316)
```
error CS0246: The type or namespace name 'ActivitySourceOptions' could not be found
error CS1061: 'ActivitySource' does not contain a definition for 'TelemetrySchemaUrl' ...
```

### 💡 Co to zmienia w praktyce
- `ActivityListener.ShouldListenTo` dostaje już `Version`, `Tags` i `TelemetrySchemaUrl` —
  eksporter (np. własny) może wysłać `schema_url` razem ze spanami. **Nie weryfikowaliśmy**,
  czy oficjalny pakiet OpenTelemetry .NET już to robi: nie ma go w tym repo i nie używaliśmy
  sieci.
- Aktywności z `Activity.Source.TelemetrySchemaUrl` mają metadane źródła dostępne w
  `ActivityStopped` (zmierzone wyżej).

### ⚠️ Haczyk A — tylko nowy konstruktor, nie ma „starego z schematem"
`new ActivitySource(name, version)` zostawia `TelemetrySchemaUrl == null` i `Tags == null`.
Żeby ustawić schemat, trzeba użyć konstruktora z opcjami.

### ⚠️ Haczyk B — opcje są kopiowane przy konstrukcji, URL nie jest walidowany
```
po mutacji opcji: zrodlo.TelemetrySchemaUrl=https://example.invalid/v1     (opcje zmieniono na v2)
niepoprawny URL przyjety bez walidacji: 'to nie jest url'
```
`TelemetrySchemaUrl` to zwykły `string`. Literówka przejdzie cicho — a backend dowie się o
niej dopiero przy próbie pobrania schematu.

### ⚠️ Haczyk C — kolejność tagów i pusta wersja
Podaliśmy tagi `zespol`, `srodowisko`; źródło zwróciło `srodowisko`, `zespol` — nie
zakładaj kolejności wstawienia. `new ActivitySourceOptions("x").Version` to pusty string
(nie `null`), a `Tags` domyślnie `null`. `new ActivitySourceOptions(null)` →
`ArgumentNullException`.

### ⚠️ Haczyk D — schemat nie wchodzi do „tożsamości" źródła
Dwa źródła o tej samej nazwie i wersji, jedno ze schematem, drugie bez, istnieją
obok siebie (listener dostał `ShouldListenTo` dwa razy). Nie ma tu żadnego scalania — jeśli
w dużej aplikacji dwie biblioteki zarejestrują tę samą nazwę z różnymi schematami,
oba warianty trafią do listenera i trzeba je rozróżnić samemu.

**Kod:** [`code/activitysource-options/`](code/activitysource-options/), dowód `CS0246`/`CS1061`: [`code/compat-check-activity/`](code/compat-check-activity/)

---

## 📎 Jak zweryfikowano
- `compat-check-pipe` i `compat-check-activity` na `net9.0` (SDK 9.0.316): oba nie
  kompilują się (`CS1503`×2; `CS0246` + `CS1061`).
- `pipereader-json` i `activitysource-options` uruchomione `dotnet run` na SDK 10.0.400;
  pamięć mierzona w osobnych procesach (`-c Release`, tryb `stream` i `list`, każdy 2×).
- **Niezweryfikowane:** ASP.NET/Kestrel (`HttpContext.Request.BodyReader` jako źródło),
  prawdziwy socket, `DeserializeAsyncEnumerable` z `JsonTypeInfo`/source-generation,
  anulowanie, pakiet OpenTelemetry i faktyczny eksport `schema_url` (OTLP),
  zachowanie `ActivitySource` przy wielu wątkach, .NET 11 (brak SDK), dokumentacja online
  (nie korzystano), historia `MeterOptions.TelemetrySchemaUrl` w wersjach .NET.
- Zostaje (z tego samego diffu): `JsonKnownReferenceHandler`,
  `FrozenDictionary.Create(ReadOnlySpan<...>)`, `OrderedDictionary.TryAdd(..., out int)`,
  `SlhDsa`/`CompositeMLDsa` → .NET 11, gdy pojawi się SDK.

---

## 📎 Jak uruchomić
Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #17 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
