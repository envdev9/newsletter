using System.Net;

/// <summary>Minimalny serwer HTTP udajacy CDP: serwuje plik CRL i liczy zapytania.</summary>
sealed class CrlServer : IDisposable
{
    readonly HttpListener _l = new();
    readonly string _file;
    public int Hits;

    public CrlServer(string crlFile, int port = 18480)
    {
        _file = crlFile;
        _l.Prefixes.Add($"http://127.0.0.1:{port}/");
        _l.Start();
        _ = Task.Run(Loop);
    }

    async Task Loop()
    {
        while (_l.IsListening)
        {
            HttpListenerContext ctx;
            try { ctx = await _l.GetContextAsync(); } catch { return; }
            Interlocked.Increment(ref Hits);
            Console.WriteLine($"      [CDP-HTTP] {ctx.Request.HttpMethod} {ctx.Request.Url!.AbsolutePath} -> serwuje {Path.GetFileName(_file)}");
            var bytes = await File.ReadAllBytesAsync(_file);
            ctx.Response.ContentType = "application/pkix-crl";
            ctx.Response.ContentLength64 = bytes.Length;
            await ctx.Response.OutputStream.WriteAsync(bytes);
            ctx.Response.Close();
        }
    }

    public void Dispose() { _l.Stop(); _l.Close(); }
}
