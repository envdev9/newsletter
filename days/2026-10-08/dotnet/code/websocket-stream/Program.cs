// WebSocketStream (.NET 10): WebSocket jako zwykly System.IO.Stream.
// Dwa WebSockety "klient" i "serwer" spiete przez System.IO.Pipelines w pamieci - zero sieci, zero portow.
using System.IO.Pipelines;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;

var (klient, serwer) = ParaWebSocketow();

Console.WriteLine("--- 1. Serwer pisze JSON prosto do strumienia wiadomosci, klient czyta bez petli ReceiveAsync ---");
await using (var out1 = WebSocketStream.CreateWritableMessageStream(serwer, WebSocketMessageType.Text))
    await JsonSerializer.SerializeAsync(out1, new Pomiar("Gdansk", [1.5, 2.5, 3.5]));
// Dispose strumienia = koniec wiadomosci (EndOfMessage)
await using (var in1 = WebSocketStream.CreateReadableMessageStream(klient))
{
    var p = await JsonSerializer.DeserializeAsync<Pomiar>(in1);
    Console.WriteLine($"klient odebral: {p}");
}

Console.WriteLine("\n--- 2. Granice wiadomosci: jeden ReadableMessageStream = jedna wiadomosc ---");
foreach (var tekst in new[] { "pierwsza", "druga" })
{
    await using var o = WebSocketStream.CreateWritableMessageStream(serwer, WebSocketMessageType.Text);
    await o.WriteAsync(Encoding.UTF8.GetBytes(tekst));
}
for (int i = 1; i <= 2; i++)
{
    await using var r = WebSocketStream.CreateReadableMessageStream(klient);
    using var sr = new StreamReader(r);
    Console.WriteLine($"wiadomosc {i}: \"{await sr.ReadToEndAsync()}\"");
}

Console.WriteLine("\n--- 3. Duza wiadomosc: 3 MB przez CopyToAsync, bez wlasnego bufora ---");
var duze = new byte[3 * 1024 * 1024];
new Random(42).NextBytes(duze);
var wysylanie = Task.Run(async () =>
{
    await using var o = WebSocketStream.CreateWritableMessageStream(serwer, WebSocketMessageType.Binary);
    await new MemoryStream(duze).CopyToAsync(o);
});
var odebrane = new MemoryStream();
await using (var r = WebSocketStream.CreateReadableMessageStream(klient))
    await r.CopyToAsync(odebrane);
await wysylanie;
Console.WriteLine($"odebrano {odebrane.Length} B, zgodne bajt w bajt: {odebrane.ToArray().AsSpan().SequenceEqual(duze)}");

Console.WriteLine("\n--- 4. HACZYK A: Create(...) (nie CreateWritableMessageStream) - ile wiadomosci przy 3 zapisach? ---");
await using (var s = WebSocketStream.Create(serwer, WebSocketMessageType.Text, ownsWebSocket: false))
{
    foreach (var kawalek in new[] { "aa", "bb", "cc" })
        await s.WriteAsync(Encoding.UTF8.GetBytes(kawalek));
    await s.FlushAsync();
}
var buf = new byte[64];
for (int i = 1; i <= 3; i++)
{
    var res = await klient.ReceiveAsync(buf, CancellationToken.None);
    Console.WriteLine($"ReceiveAsync #{i}: {res.Count} B, EndOfMessage={res.EndOfMessage}, \"{Encoding.UTF8.GetString(buf, 0, res.Count)}\"");
}

Console.WriteLine("\n--- 5. HACZYK B: ten sam test dla CreateWritableMessageStream (3 zapisy, 1 Dispose) ---");
await using (var s = WebSocketStream.CreateWritableMessageStream(serwer, WebSocketMessageType.Text))
{
    foreach (var kawalek in new[] { "aa", "bb", "cc" })
        await s.WriteAsync(Encoding.UTF8.GetBytes(kawalek));
}
for (int i = 1; i <= 4; i++)
{
    using var timeout = new CancellationTokenSource(500);
    try
    {
        var res = await klient.ReceiveAsync(buf, timeout.Token);
        Console.WriteLine($"ReceiveAsync #{i}: {res.Count} B, EndOfMessage={res.EndOfMessage}, \"{Encoding.UTF8.GetString(buf, 0, res.Count)}\"");
    }
    catch (OperationCanceledException) { Console.WriteLine($"ReceiveAsync #{i}: brak wiecej danych (timeout 500 ms)"); break; }
}

Console.WriteLine("\n--- 6. HACZYK C: wlasciwosci strumienia i ownsWebSocket ---");
var tmp = WebSocketStream.Create(klient, WebSocketMessageType.Text, ownsWebSocket: false);
Console.WriteLine($"CanRead={tmp.CanRead} CanWrite={tmp.CanWrite} CanSeek={tmp.CanSeek}");
try { _ = tmp.Length; } catch (Exception ex) { Console.WriteLine($"Length: RZUCILO {ex.GetType().Name}"); }
await tmp.DisposeAsync();
Console.WriteLine($"po Dispose z ownsWebSocket:false -> klient.State = {klient.State}");
var tmp2 = WebSocketStream.Create(klient, WebSocketMessageType.Text, ownsWebSocket: true);
await tmp2.DisposeAsync();
Console.WriteLine($"po Dispose z ownsWebSocket:true  -> klient.State = {klient.State}");
try { await klient.SendAsync(new byte[1], WebSocketMessageType.Text, true, CancellationToken.None); Console.WriteLine("SendAsync po Dispose: ok"); }
catch (Exception ex) { Console.WriteLine($"SendAsync po Dispose: RZUCILO {ex.GetType().Name}"); }

// --- infrastruktura: dwa WebSockety przez Pipe ---
static (WebSocket klient, WebSocket serwer) ParaWebSocketow()
{
    var doSerwera = new Pipe();
    var doKlienta = new Pipe();
    var opcje = (bool serwer) => new WebSocketCreationOptions { IsServer = serwer };
    var klient = WebSocket.CreateFromStream(new Duplex(doKlienta.Reader.AsStream(), doSerwera.Writer.AsStream()), opcje(false));
    var serwer = WebSocket.CreateFromStream(new Duplex(doSerwera.Reader.AsStream(), doKlienta.Writer.AsStream()), opcje(true));
    return (klient, serwer);
}

sealed class Duplex(Stream czytaj, Stream pisz) : Stream
{
    public override bool CanRead => true;
    public override bool CanWrite => true;
    public override bool CanSeek => false;
    public override long Length => throw new NotSupportedException();
    public override long Position { get => throw new NotSupportedException(); set => throw new NotSupportedException(); }
    public override void Flush() => pisz.Flush();
    public override Task FlushAsync(CancellationToken ct) => pisz.FlushAsync(ct);
    public override int Read(byte[] b, int o, int c) => czytaj.Read(b, o, c);
    public override ValueTask<int> ReadAsync(Memory<byte> m, CancellationToken ct = default) => czytaj.ReadAsync(m, ct);
    public override void Write(byte[] b, int o, int c) => pisz.Write(b, o, c);
    public override ValueTask WriteAsync(ReadOnlyMemory<byte> m, CancellationToken ct = default) => pisz.WriteAsync(m, ct);
    public override long Seek(long o, SeekOrigin so) => throw new NotSupportedException();
    public override void SetLength(long v) => throw new NotSupportedException();
}

record Pomiar(string Miasto, double[] Wartosci)
{
    public override string ToString() => $"{Miasto}: [{string.Join(", ", Wartosci)}]";
}
