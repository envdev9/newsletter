<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #15 — 8 października 2026

![.NET](https://img.shields.io/badge/.NET-10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![BCL](https://img.shields.io/badge/BCL-SSE%20%2B%20WebSocketStream-blue?style=for-the-badge)

## Server-Sent Events i `WebSocketStream` — protokoły sieciowe jako zwykły `Stream`, w samym BCL

</div>

---

> _"The enumerable may be enumerated only once."_ — tak odpowiada `SseParser` na próbę
> drugiego przejścia po strumieniu zdarzeń. Zmierzone w tej sesji. Strumień sieciowy to
> nie lista: raz przeczytany, zniknął.

Do tej pory w rubryce schodziliśmy po `Span`, LINQ i `System.Text.Json`. Dziś
**sieć**. Tym razem funkcje znaleźliśmy porządnym **diffem refleksyjnym** całego
shared frameworka: ten sam program zrzucił publiczne i chronione sygnatury wszystkich
`System*.dll`/`Microsoft*.dll` z runtime 9.0.18 i 10.0.11, a `comm -13` pokazał, co doszło
(42 376 vs 41 286 pozycji). Wśród nowych *typów* — poza PQC, async LINQ i `GCHandle<T>`
omówionymi wcześniej — zostały dwa sieciowe: `System.Net.ServerSentEvents` i
`WebSocketStream`. SDK .NET 11 nadal nie ma na tej maszynie (`dotnet --list-sdks`: 8.0.422,
8.0.425, 9.0.316, 10.0.400), więc zostajemy przy .NET 10. Kod w [`code/`](code/).

| # | Funkcja | Namespace | Status |
|---|---------|-----------|--------|
| 1️⃣ | `SseFormatter` + `SseParser` (Server-Sent Events) | `System.Net.ServerSentEvents` | ✅ w pełni zweryfikowane (w pamięci) |
| 2️⃣ | `WebSocketStream` (WebSocket jako `Stream`) | `System.Net.WebSockets` | ✅ w pełni zweryfikowane (w pamięci) |

---

## 1️⃣ Server-Sent Events: `SseFormatter` (zapis) i `SseParser` (odczyt)

### 😤 Problem
SSE (`text/event-stream`) to najprostszy sposób, by serwer pchał zdarzenia do klienta po
zwykłym HTTP — tak działają m.in. strumieniowane odpowiedzi modeli AI. Format jest prosty
(`event:`, `data:`, `id:`, `retry:`, pusta linia kończy zdarzenie), ale „prosty" znaczy:
ręczne sklejanie stringów, **wielolinijkowe dane** (każda linia musi dostać własny prefiks
`data:`), ucieczka przed wstrzyknięciem nowej linii w `event:`/`id:` i parser po stronie
klienta, który obsłuży komentarze i `retry`.

### ✨ Co się zmieniło
Typy w `System.Net.ServerSentEvents`: `SseItem<T>`, `SseParser`/`SseParser<T>` oraz —
nowość — **`SseFormatter`**, który zapisuje `IAsyncEnumerable<SseItem<T>>` do `Stream`.
Parser czyta, formatter zapisuje — razem dają obieg w obie strony. Dla dokładności: **nie sprawdzaliśmy**, czy sam `SseParser` istniał wcześniej jako pakiet NuGet
(brak dostępu do dokumentacji online); sprawdziliśmy tylko, że na `net9.0` bez żadnego
pakietu cały namespace nie istnieje (dowód niżej), a diff pokazuje `SseFormatter`,
`SseParser`, `SseItem<T>` jako typy nowe w shared frameworku.

```csharp
await SseFormatter.WriteAsync(Zdarzenia(), strumien);            // IAsyncEnumerable<SseItem<string>>

var parser = SseParser.Create(strumien);
await foreach (var e in parser.EnumerateAsync())
    Console.WriteLine($"{e.EventType} {e.EventId} {e.Data}");

// Typowo: własny formatter danych (JSON) i parser z delegatem SseItemParser<T>
await SseFormatter.WriteAsync(Pomiary(), ms,
    (item, writer) => { using var w = new Utf8JsonWriter(writer); JsonSerializer.Serialize(w, item.Data); });
var typed = SseParser.Create(ms, (typ, bajty) => JsonSerializer.Deserialize<Temp>(bajty)!);
```

### 🖥️ Prawdziwy output (`dotnet run --project sse-roundtrip`, ta maszyna; `\n` dopisane dla czytelności)
```
event: komunikat\n
data: linia 1\n
data: linia 2\n
id: 2\n
\n
event: ping\n
data: retry!\n
id: 3\n
retry: 5000\n
\n
data: bez typu\n
id: 4\n
\n
--- po parsowaniu ---
typ=status    id=1 retry=- dane=start
typ=komunikat id=2 retry=- dane=linia 1\nlinia 2
typ=ping      id=3 retry=5 dane=retry!
typ=message   id=4 retry=- dane=bez typu
parser.LastEventId = 4, parser.ReconnectionInterval = 5s
```
Z `WriteAsync<T>` i JSON-em: `data: {"Miasto":"Gdansk","Stopnie":11.5}`; po drugiej stronie
`[temp] Temp { Miasto = Gdansk, Stopnie = 11.5 }`.

### 🔬 Dowód „przed i po" (target `net9.0`, SDK 9.0.316, brak PackageReference)
```
error CS0234: The type or namespace name 'ServerSentEvents' does not exist in the namespace 'System.Net'
```
Kompilator zatrzymuje się na `using` — pozostałych nazw (`SseFormatter`, `SseItem<>`)
nie zgłasza w tym samym przebiegu.

### 💡 Co to zmienia w praktyce
- Serwer SSE bez ręcznego sklejania protokołu: wielolinijkowe dane dostają `data:` w każdej
  linii automatycznie (zmierzone: `"linia 1\nlinia 2"` → dwie linie `data:`), a parser skleja
  je z powrotem.
- Test „tam i z powrotem" w pamięci (`MemoryStream`) — bez portu, bez `HttpClient`.
  To dokładnie to, co robi nasz kod: **nie** uruchamialiśmy prawdziwego serwera HTTP.
- `retry: 5000` ustawia `SseParser.ReconnectionInterval`, a ostatnie `id:` ląduje w
  `LastEventId` — klient ma z czego zbudować nagłówek `Last-Event-ID` przy ponownym łączeniu.

### ⚠️ Haczyk A — walidacja nowej linii jest w konstruktorze `SseItem`, nie w `WriteAsync`
`new SseItem<string>("x", "zly\ntyp")` i `EventId = "a\nb"` rzucają natychmiast:
```
EventType z \n: RZUCILO ArgumentException: The argument cannot contain line breaks. (Parameter 'eventType')
EventId z \n   : RZUCILO ArgumentException: The argument cannot contain line breaks. (Parameter 'EventId')
```
Dobrze (nie da się wstrzyknąć fałszywego pola), ale uwaga: jeśli `EventType` pochodzi z
danych użytkownika, wyjątek poleci w kodzie budującym zdarzenie, nie w pętli zapisu.

### ⚠️ Haczyk B — dane są normalizowane, nie zachowane bajt w bajt
`"a\r\nb"` trafia do strumienia jako dwie linie `data: a` / `data: b`, a po sparsowaniu
wraca jako `"a\nb"` — `\r\n` zniknęło (zmierzone). Pusty string to `data: ` i wraca jako `""`.
Jeśli w payloadzie liczą się końce linii (np. fragment pliku), zakoduj dane (JSON, Base64).

### ⚠️ Haczyk C — parser jest jednorazowy, komentarze są pomijane
`SseParser.Enumerate()` drugi raz → `InvalidOperationException: The enumerable may be
enumerated only once.` Linia `: komentarz (keep-alive)` jest po cichu pomijana — w
wynikach zostały tylko `message:abc` i `x:def`. Jeśli chcesz widzieć keep-alive, ten parser
ich nie pokaże.

**Kod:** [`code/sse-roundtrip/`](code/sse-roundtrip/), dowód `CS0234`: [`code/compat-check/`](code/compat-check/)

---

## 2️⃣ `WebSocketStream` — WebSocket, który udaje `Stream`

### 😤 Problem
`WebSocket` ma API wiadomościowe: `ReceiveAsync(buffer)` zwraca kawałek i flagę
`EndOfMessage`, więc każdy konsument pisze tę samą pętlę: bufor, składanie fragmentów,
sprawdzanie typu wiadomości. A wszystkie wygodne API .NET (`JsonSerializer`, `StreamReader`,
`CopyToAsync`, `GZipStream`) przyjmują `Stream`.

### ✨ Co się zmieniło
.NET 10 dodaje klasę `WebSocketStream`, która opakowuje `WebSocket` w `Stream`.
Cztery fabryki (potwierdzone diffem): `Create(ws, messageType, ownsWebSocket)`,
`Create(ws, messageType, TimeSpan closeTimeout)`, `CreateReadableMessageStream(ws)`,
`CreateWritableMessageStream(ws, messageType)`. Dwie ostatnie mapują **jedną wiadomość na
jeden strumień**: czytelny kończy się (0 bajtów) na granicy wiadomości, zapisywalny wysyła
`EndOfMessage` przy `Dispose`.

```csharp
// serwer: JSON prosto do wiadomości
await using (var o = WebSocketStream.CreateWritableMessageStream(serwer, WebSocketMessageType.Text))
    await JsonSerializer.SerializeAsync(o, new Pomiar("Gdansk", [1.5, 2.5, 3.5]));

// klient: zero ReceiveAsync, zero składania fragmentów
await using var i = WebSocketStream.CreateReadableMessageStream(klient);
var p = await JsonSerializer.DeserializeAsync<Pomiar>(i);
```

### 🖥️ Prawdziwy output (`dotnet run --project websocket-stream`, ta maszyna)
Dwa WebSockety („klient" i „serwer") spięte `WebSocket.CreateFromStream` przez
`System.IO.Pipelines` w pamięci — **żadnej sieci i portu**.
```
klient odebral: Gdansk: [1.5, 2.5, 3.5]
wiadomosc 1: "pierwsza"
wiadomosc 2: "druga"
odebrano 3145728 B, zgodne bajt w bajt: True       <- 3 MB przez CopyToAsync
```

### 🔬 Dowód „przed i po" (target `net9.0`, SDK 9.0.316)
```
error CS0103: The name 'WebSocketStream' does not exist in the current context   (x3)
```

### 💡 Co to zmienia w praktyce
- `JsonSerializer`, `StreamReader`, `CopyToAsync`, kompresja — wszystko, co zna `Stream`,
  działa teraz na WebSockecie bez adaptera. 3 MB przeszły w jednym `CopyToAsync` bez
  własnego bufora i bez pętli.
- Granice wiadomości zostają w protokole: dwie wiadomości = dwa `CreateReadableMessageStream`.

### ⚠️ Haczyk A — `Create(...)` to NIE to samo co strumień wiadomości
`Create(ws, Text, false)` + trzy `WriteAsync` („aa", „bb", „cc") → po drugiej stronie trzy
osobne wiadomości, każda `EndOfMessage=True`. Chcąc jedną wiadomość z wielu zapisów,
użyj `CreateWritableMessageStream`.

### ⚠️ Haczyk B — wiadomość z wielu zapisów kończy się pustym fragmentem
`CreateWritableMessageStream`, trzy zapisy, jeden `Dispose`; klasyczny `ReceiveAsync`
widzi cztery odbiory:
```
#1 2 B EndOfMessage=False "aa"   #2 2 B False "bb"   #3 2 B False "cc"
#4 0 B EndOfMessage=True ""
```
Granicę wiadomości domykają 0 bajtów. Kto miesza stary `ReceiveAsync` ze strumieniem,
musi to obsłużyć. Pominięty `Dispose` = wiadomość nigdy się nie kończy.

### ⚠️ Haczyk C — `ownsWebSocket` i brak seekowania
`Length` → `NotSupportedException` (`CanSeek=False`). Dispose strumienia z
`ownsWebSocket:false` zostawia gniazdo `Open`; z `ownsWebSocket:true` stan to `Aborted`
(w naszym teście — brak prawdziwego peera do uściśnięcia dłoni zamknięcia, więc nie
oceniamy tu graceful close), a kolejny `SendAsync` rzuca `WebSocketException`.

**Kod:** [`code/websocket-stream/`](code/websocket-stream/), dowód `CS0103`: [`code/compat-check-ws/`](code/compat-check-ws/)

---

## 📎 Jak zweryfikowano
- Diff refleksyjny (osobny program poza repo, `Assembly.LoadFrom` dla `System*.dll` i
  `Microsoft*.dll` z runtime 9.0.18 i 10.0.11, członkowie publiczni/chronieni): lista
  nowych typów wskazała oba tematy. Zrzut z wielu dziesiątek tysięcy linii — przejrzano
  nowe *typy* i wybrane assembly, nie każdą pojedynczą nową metodę.
- `compat-check` i `compat-check-ws` na `net9.0` (SDK 9.0.316): oba nie
  kompilują się: `CS0234` (SSE) i 3×`CS0103` (`WebSocketStream`).
- Oba programy uruchomione `dotnet run` na SDK 10.0.400, cały obieg w pamięci.
- **Niezweryfikowane:** prawdziwy serwer/klient HTTP (ASP.NET `TypedResults.ServerSentEvents`,
  `HttpClient`), prawdziwa sieć i graceful close WebSocketa, `SseItemParser<T>` na bajtach
  nie-UTF-8, zachowanie przy anulowaniu `WriteAsync`, wydajność, .NET 11 (brak SDK),
  to, czy `SseParser` był wcześniej w pakiecie NuGet. Nie korzystano z dokumentacji online.
- Zostaje (z tego samego diffu): `ActivitySourceOptions` (+`TelemetrySchemaUrl`),
  `JsonSerializer.DeserializeAsync` z `PipeReader`, `JsonKnownReferenceHandler`,
  `FrozenDictionary.Create(ReadOnlySpan<...>)`, `OrderedDictionary.TryAdd(..., out int)`,
  `SlhDsa`/`CompositeMLDsa` → .NET 11, gdy pojawi się SDK.

---

## 📎 Jak uruchomić
Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #15 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
