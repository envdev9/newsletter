// Server-Sent Events w BCL (.NET 10): SseFormatter (zapis) + SseParser (odczyt).
// Wszystko w pamieci (MemoryStream), bez sieci i bez ASP.NET.
using System.Buffers;
using System.Net.ServerSentEvents;
using System.Text;
using System.Text.Json;

static async IAsyncEnumerable<SseItem<string>> Zdarzenia()
{
    yield return new SseItem<string>("start", "status") { EventId = "1" };
    await Task.Yield();
    yield return new SseItem<string>("linia 1\nlinia 2", "komunikat") { EventId = "2" };
    yield return new SseItem<string>("retry!", "ping") { EventId = "3", ReconnectionInterval = TimeSpan.FromSeconds(5) };
    yield return new SseItem<string>("bez typu", null) { EventId = "4" };
}

static async Task<string> Surowo(Stream s)
{
    s.Position = 0;
    return await new StreamReader(s, Encoding.UTF8).ReadToEndAsync();
}

Console.WriteLine("--- 1. SseFormatter.WriteAsync: IAsyncEnumerable<SseItem<string>> -> strumien ---");
var ms = new MemoryStream();
await SseFormatter.WriteAsync(Zdarzenia(), ms);
var surowy = await Surowo(ms);
Console.WriteLine(surowy.Replace("\n", "\\n\n"));

Console.WriteLine("--- 2. SseParser.Create(...).EnumerateAsync: ten sam strumien z powrotem ---");
ms.Position = 0;
var parser = SseParser.Create(ms);
await foreach (var e in parser.EnumerateAsync())
    Console.WriteLine($"typ={e.EventType,-9} id={e.EventId} retry={e.ReconnectionInterval?.TotalSeconds.ToString() ?? "-"} dane={e.Data.Replace("\n", "\\n")}");
Console.WriteLine($"parser.LastEventId = {parser.LastEventId}, parser.ReconnectionInterval = {parser.ReconnectionInterval.TotalSeconds}s");

Console.WriteLine("\n--- 3. Typowo: WriteAsync<T> z wlasnym formaterem (JSON) i SseItemParser<T> ---");
static async IAsyncEnumerable<SseItem<Temp>> Pomiary()
{
    yield return new SseItem<Temp>(new Temp("Gdansk", 11.5), "temp");
    await Task.Yield();
    yield return new SseItem<Temp>(new Temp("Krakow", 14.25), "temp");
}
var ms2 = new MemoryStream();
await SseFormatter.WriteAsync(Pomiary(), ms2,
    (item, writer) => { using var w = new Utf8JsonWriter(writer); JsonSerializer.Serialize(w, item.Data); });
Console.WriteLine((await Surowo(ms2)).Replace("\n", "\\n\n"));
ms2.Position = 0;
var typed = SseParser.Create(ms2, (typ, bajty) => JsonSerializer.Deserialize<Temp>(bajty)!);
foreach (var e in typed.Enumerate())
    Console.WriteLine($"[{e.EventType}] {e.Data}");

Console.WriteLine("\n--- 4. HACZYK A: znak nowej linii w EventType / EventId ---");
foreach (var (nazwa, fabryka) in new (string, Func<SseItem<string>>)[]
{
    ("EventType z \\n", () => new SseItem<string>("x", "zly\ntyp")),
    ("EventId z \\n   ", () => new SseItem<string>("x", "ok") { EventId = "a\nb" }),
})
{
    try { _ = fabryka(); Console.WriteLine($"{nazwa}: bez wyjatku"); }
    catch (Exception ex) { Console.WriteLine($"{nazwa}: RZUCILO {ex.GetType().Name}: {ex.Message}"); }
}

Console.WriteLine("\n--- 5. HACZYK B: dane z \\r\\n i pusty string ---");
var ms3 = new MemoryStream();
await SseFormatter.WriteAsync(Seria(), ms3);
Console.WriteLine((await Surowo(ms3)).Replace("\r", "\\r").Replace("\n", "\\n\n"));
ms3.Position = 0;
foreach (var e in SseParser.Create(ms3).Enumerate())
    Console.WriteLine($"dane po parsowaniu = \"{e.Data.Replace("\r", "\\r").Replace("\n", "\\n")}\"");
static async IAsyncEnumerable<SseItem<string>> Seria()
{
    await Task.Yield();
    yield return new SseItem<string>("a\r\nb", "x");
    yield return new SseItem<string>("", "pusty");
}

Console.WriteLine("\n--- 6. HACZYK C: komentarze i enumeracja parsera dwa razy ---");
var reczny = Encoding.UTF8.GetBytes(": to jest komentarz (keep-alive)\ndata: abc\n\nevent: x\ndata: def\n\n");
var p = SseParser.Create(new MemoryStream(reczny));
Console.WriteLine("zdarzenia: " + string.Join(" | ", p.Enumerate().Select(e => $"{e.EventType}:{e.Data}")));
try { _ = p.Enumerate().ToList(); Console.WriteLine("drugi Enumerate: bez wyjatku"); }
catch (Exception ex) { Console.WriteLine($"drugi Enumerate: RZUCILO {ex.GetType().Name}: {ex.Message}"); }

record Temp(string Miasto, double Stopnie);
