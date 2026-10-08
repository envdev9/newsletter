// Na net9.0 (bez dodatkowych pakietow NuGet) ten plik NIE kompiluje sie - oczekiwane bledy w README.
using System.Net.ServerSentEvents;

var ms = new MemoryStream();
SseItem<string> item = new("x", "typ");
await SseFormatter.WriteAsync(Zrodlo(), ms);
var parser = SseParser.Create(ms);

static async IAsyncEnumerable<SseItem<string>> Zrodlo() { await Task.Yield(); yield break; }
