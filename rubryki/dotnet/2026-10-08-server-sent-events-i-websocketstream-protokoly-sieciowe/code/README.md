# Kod do wydania #15 — Server-Sent Events (`SseFormatter`/`SseParser`) i `WebSocketStream` (.NET 10)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (sprawdzone na `10.0.400`). `sse-roundtrip` i `websocket-stream`
celują w `net10.0`; `compat-check` i `compat-check-ws` celowo w `net9.0` (potrzebują SDK 9.x
obok; sprawdzone na `9.0.316`). Brak zależności NuGet, brak sieci (wszystko w pamięci).

## Fragment prasówki, którego dotyczy ten kod

> `System.Net.ServerSentEvents`: `SseFormatter.WriteAsync` zapisuje `IAsyncEnumerable<SseItem<T>>`
> jako `text/event-stream`, `SseParser.Create(stream)` czyta z powrotem. Na `net9.0` bez pakietu
> cały namespace nie istnieje (`CS0234`). Haczyki: `\n` w `EventType`/`EventId` rzuca
> `ArgumentException` już w konstruktorze `SseItem`; `\r\n` w danych wraca jako `\n`; parser
> jest jednorazowy ("may be enumerated only once"); komentarze `:` są pomijane.
>
> `WebSocketStream` (`System.Net.WebSockets`): WebSocket jako `Stream`, więc `JsonSerializer`,
> `StreamReader`, `CopyToAsync` działają bez pętli `ReceiveAsync`. Na `net9.0`: `CS0103`.
> Haczyki: `Create(...)` = jedna wiadomość na zapis, `CreateWritableMessageStream` = jedna
> wiadomość do `Dispose` (zamknięta pustym fragmentem `EndOfMessage`); `ownsWebSocket:true` →
> stan `Aborted` po Dispose.

## 1. sse-roundtrip

```bash
dotnet run --project sse-roundtrip
```

Output (pełny, deterministyczny):

```
--- 2. SseParser.Create(...).EnumerateAsync: ten sam strumien z powrotem ---
typ=status    id=1 retry=- dane=start
typ=komunikat id=2 retry=- dane=linia 1\nlinia 2
typ=ping      id=3 retry=5 dane=retry!
typ=message   id=4 retry=- dane=bez typu
parser.LastEventId = 4, parser.ReconnectionInterval = 5s
...
EventType z \n: RZUCILO ArgumentException: The argument cannot contain line breaks. (Parameter 'eventType')
EventId z \n   : RZUCILO ArgumentException: The argument cannot contain line breaks. (Parameter 'EventId')
...
zdarzenia: message:abc | x:def
drugi Enumerate: RZUCILO InvalidOperationException: The enumerable may be enumerated only once.
```

## 2. websocket-stream

```bash
dotnet run --project websocket-stream
```

Output (kolejność i treść deterministyczne):

```
klient odebral: Gdansk: [1.5, 2.5, 3.5]
wiadomosc 1: "pierwsza"
wiadomosc 2: "druga"
odebrano 3145728 B, zgodne bajt w bajt: True
ReceiveAsync #1..#3: 2 B, EndOfMessage=True  (Create: trzy osobne wiadomosci)
ReceiveAsync #1..#3: 2 B, EndOfMessage=False, #4: 0 B, EndOfMessage=True (CreateWritableMessageStream)
po Dispose z ownsWebSocket:false -> klient.State = Open
po Dispose z ownsWebSocket:true  -> klient.State = Aborted
SendAsync po Dispose: RZUCILO WebSocketException
```

## 3. compat-check i compat-check-ws (celowo NIE kompilują się na .NET 9)

```bash
dotnet build compat-check
dotnet build compat-check-ws
```

Oczekiwane (zweryfikowane): `compat-check` → `CS0234` (brak namespace `System.Net.ServerSentEvents`);
`compat-check-ws` → 3× `CS0103` (`WebSocketStream` nie istnieje).

## Zweryfikowane / niezweryfikowane

- Zweryfikowane `dotnet run` (SDK 10.0.400): oba programy, wszystkie sekcje, w pamięci.
- Zweryfikowane `dotnet build` (net9.0, SDK 9.0.316): błędy jak wyżej.
- Niezweryfikowane: prawdziwy HTTP/ASP.NET, prawdziwa sieć i graceful close WebSocketa,
  .NET 11 (brak SDK), historia pakietu NuGet `System.Net.ServerSentEvents`, dokumentacja online.
