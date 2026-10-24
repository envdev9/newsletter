using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;

Console.WriteLine($"Runtime: {System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription}");

var root = Path.Combine(Path.GetTempPath(), "zip-async-" + Guid.NewGuid().ToString("N")[..8]);
Directory.CreateDirectory(root);
try
{
    var src = Path.Combine(root, "src");
    Directory.CreateDirectory(Path.Combine(src, "sub"));
    await File.WriteAllTextAsync(Path.Combine(src, "a.txt"), new string('a', 10_000));
    await File.WriteAllTextAsync(Path.Combine(src, "sub", "b.txt"), "zażółć gęślą jaźń");
    await File.WriteAllBytesAsync(Path.Combine(src, "sub", "rnd.bin"), RandomNumberGenerator.GetBytes(50_000));

    // 1. Round-trip: katalog -> plik zip -> katalog, porownanie hashy
    Console.WriteLine("--- 1. Round-trip CreateFromDirectoryAsync -> ExtractToDirectoryAsync ---");
    var zipPath = Path.Combine(root, "out.zip");
    await ZipFile.CreateFromDirectoryAsync(src, zipPath, CompressionLevel.Optimal, includeBaseDirectory: false);
    var dst = Path.Combine(root, "dst");
    await ZipFile.ExtractToDirectoryAsync(zipPath, dst);
    Console.WriteLine($"rozmiar zip: {new FileInfo(zipPath).Length} B (zrodlo: {Directory.GetFiles(src, "*", SearchOption.AllDirectories).Sum(f => new FileInfo(f).Length)} B)");
    foreach (var f in Directory.GetFiles(src, "*", SearchOption.AllDirectories).OrderBy(x => x, StringComparer.Ordinal))
    {
        var rel = Path.GetRelativePath(src, f);
        var same = Hash(f) == Hash(Path.Combine(dst, rel));
        Console.WriteLine($"{rel}: hash zgodny = {same}");
    }

    // 2. Czy "async" znaczy naprawde bez synchronicznego I/O na docelowym strumieniu?
    //    Liczymy sync vs async zapisy na nieseekowalnym strumieniu (kopia do pamieci, nic nie rzuca).
    Console.WriteLine("--- 2. Sync vs async zapisy na strumieniu docelowym ---");
    Console.WriteLine($"{"scenariusz",-58} {"sync Write",10} {"async Write",12} {"bajty",8}  poprawny zip");

    var s = new CountingStream();
    ZipFile.CreateFromDirectory(src, s, CompressionLevel.Optimal, false);
    Report("sync  ZipFile.CreateFromDirectory(dir, Stream), Optimal", s);

    s = new CountingStream();
    await ZipFile.CreateFromDirectoryAsync(src, s, CompressionLevel.Optimal, false);
    Report("async ZipFile.CreateFromDirectoryAsync(dir, Stream), Optimal", s);

    s = new CountingStream();
    await ZipFile.CreateFromDirectoryAsync(src, s, CompressionLevel.NoCompression, false);
    Report("async ZipFile.CreateFromDirectoryAsync(dir, Stream), NoCompr.", s);

    s = new CountingStream();
    await ManualAsync(s, CompressionLevel.Optimal, explicitFlush: false);
    Report("async reczne CreateAsync+OpenAsync+DisposeAsync, Optimal", s);

    s = new CountingStream();
    await ManualAsync(s, CompressionLevel.Optimal, explicitFlush: true);
    Report("jw. + await entryStream.FlushAsync() przed Dispose", s);

    s = new CountingStream();
    await ManualAsync(s, CompressionLevel.NoCompression, explicitFlush: false);
    Report("async reczne CreateAsync+OpenAsync+DisposeAsync, NoCompr.", s);

    // 3. Odczyt z archiwum przez async: wpisy i zawartosc
    Console.WriteLine("--- 3. Odczyt: OpenReadAsync + entry.OpenAsync ---");
    await using (var za = await ZipFile.OpenReadAsync(zipPath))
    {
        foreach (var e in za.Entries.OrderBy(e => e.FullName, StringComparer.Ordinal))
        {
            await using var es = await e.OpenAsync();
            var buf = new byte[e.Length];
            await es.ReadExactlyAsync(buf);
            Console.WriteLine($"{e.FullName}: {e.Length} B -> skompresowane {e.CompressedLength} B");
        }
    }

    // 4. Anulowanie
    Console.WriteLine("--- 4. CancellationToken ---");
    var big = Path.Combine(root, "big");
    Directory.CreateDirectory(big);
    for (var i = 0; i < 200; i++)
        await File.WriteAllBytesAsync(Path.Combine(big, $"f{i}.bin"), RandomNumberGenerator.GetBytes(200_000));
    var cancelledZip = Path.Combine(root, "cancelled.zip");
    using var cts = new CancellationTokenSource();
    cts.Cancel();
    try
    {
        await ZipFile.CreateFromDirectoryAsync(big, cancelledZip, cts.Token);
        Console.WriteLine("zawczasu anulowany token: brak wyjatku");
    }
    catch (Exception e)
    {
        Console.WriteLine($"zawczasu anulowany token: {e.GetType().Name}");
    }
    Console.WriteLine($"plik po anulowaniu istnieje: {File.Exists(cancelledZip)}"
        + (File.Exists(cancelledZip) ? $", rozmiar {new FileInfo(cancelledZip).Length} B" : ""));

    var midZip = Path.Combine(root, "mid.zip");
    using var cts2 = new CancellationTokenSource();
    var task = ZipFile.CreateFromDirectoryAsync(big, midZip, CompressionLevel.SmallestSize, false, cts2.Token);
    await Task.Delay(30);
    cts2.Cancel();
    try
    {
        await task;
        Console.WriteLine("anulowanie w trakcie: zadanie ukonczone przed anulowaniem (za szybkie, wynik nieostateczny)");
    }
    catch (OperationCanceledException e)
    {
        Console.WriteLine($"anulowanie w trakcie: {e.GetType().Name}");
        Console.WriteLine($"plik po anulowaniu istnieje: {File.Exists(midZip)}"
            + (File.Exists(midZip) ? $", rozmiar {new FileInfo(midZip).Length} B" : ""));
        if (File.Exists(midZip))
        {
            try { using var z = ZipFile.OpenRead(midZip); Console.WriteLine($"da sie otworzyc, wpisow: {z.Entries.Count} z 200"); }
            catch (Exception ex) { Console.WriteLine($"proba otwarcia: {ex.GetType().Name}"); }
        }
    }

    // 5. Zip-slip
    Console.WriteLine("--- 5. Zip-slip: wpis '../evil.txt' ---");
    var evilZip = Path.Combine(root, "evil.zip");
    await using (var fs = File.Create(evilZip))
    await using (var za = await ZipArchive.CreateAsync(fs, ZipArchiveMode.Create, leaveOpen: false, entryNameEncoding: null))
    {
        await using var es = await za.CreateEntry("../evil.txt").OpenAsync();
        await es.WriteAsync("pwned"u8.ToArray());
    }
    try
    {
        await ZipFile.ExtractToDirectoryAsync(evilZip, Path.Combine(root, "safe"));
        Console.WriteLine("rozpakowano bez wyjatku");
    }
    catch (Exception e)
    {
        Console.WriteLine($"{e.GetType().Name}: {e.Message.Replace(root, "<root>")}");
    }
    Console.WriteLine($"evil.txt poza katalogiem docelowym istnieje: {File.Exists(Path.Combine(root, "evil.txt"))}");

    async Task ManualAsync(Stream target, CompressionLevel level, bool explicitFlush)
    {
        var archive = await ZipArchive.CreateAsync(target, ZipArchiveMode.Create, leaveOpen: true, entryNameEncoding: null);
        foreach (var f in Directory.GetFiles(src, "*", SearchOption.AllDirectories).OrderBy(x => x, StringComparer.Ordinal))
        {
            var entry = archive.CreateEntry(Path.GetRelativePath(src, f).Replace('\\', '/'), level);
            await using var es = await entry.OpenAsync();
            await es.WriteAsync(await File.ReadAllBytesAsync(f));
            if (explicitFlush) await es.FlushAsync();
        }
        await archive.DisposeAsync();
    }
}
finally
{
    Directory.Delete(root, recursive: true);
}

static string Hash(string path) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path)))[..12];

static void Report(string name, CountingStream s)
{
    string valid;
    try
    {
        using var z = new ZipArchive(new MemoryStream(s.Bytes), ZipArchiveMode.Read);
        valid = $"tak ({z.Entries.Count} wpisy)";
    }
    catch (Exception e) { valid = "NIE: " + e.GetType().Name; }
    Console.WriteLine($"{name,-58} {s.SyncWrites,10} {s.AsyncWrites,12} {s.Length,8}  {valid}");
}

// Nieseekowalny strumien zapisu w pamieci, liczacy synchroniczne i asynchroniczne zapisy.
sealed class CountingStream : Stream
{
    private readonly MemoryStream _inner = new();
    public int SyncWrites { get; private set; }
    public int AsyncWrites { get; private set; }
    public byte[] Bytes => _inner.ToArray();

    public override bool CanRead => false;
    public override bool CanSeek => false;
    public override bool CanWrite => true;
    public override long Length => _inner.Length;
    public override long Position { get => _inner.Position; set => throw new NotSupportedException(); }

    public override void Flush() { }
    public override int Read(byte[] buffer, int offset, int count) => throw new NotSupportedException();
    public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
    public override void SetLength(long value) => throw new NotSupportedException();
    public override void Write(byte[] buffer, int offset, int count) { SyncWrites++; _inner.Write(buffer, offset, count); }
    public override void Write(ReadOnlySpan<byte> buffer) { SyncWrites++; _inner.Write(buffer); }

    public override Task FlushAsync(CancellationToken ct) => Task.CompletedTask;
    public override async ValueTask WriteAsync(ReadOnlyMemory<byte> buffer, CancellationToken ct = default)
    {
        AsyncWrites++;
        await Task.Yield();
        _inner.Write(buffer.Span);
    }
    public override Task WriteAsync(byte[] buffer, int offset, int count, CancellationToken ct) =>
        WriteAsync(buffer.AsMemory(offset, count), ct).AsTask();
}
