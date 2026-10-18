using System.Net;
using System.Net.Http.Json;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;

// Wolny port na loopbacku (bez sieci zewnetrznej).
var probe = new TcpListener(IPAddress.Loopback, 0);
probe.Start();
int port = ((IPEndPoint)probe.LocalEndpoint).Port;
probe.Stop();
string prefix = $"http://127.0.0.1:{port}/";

var seen = new List<string>(); // co serwer faktycznie dostal: metoda + tresc
using var listener = new HttpListener();
listener.Prefixes.Add(prefix);
listener.Start();
var serverLoop = Task.Run(async () =>
{
    while (listener.IsListening)
    {
        HttpListenerContext ctx;
        try { ctx = await listener.GetContextAsync(); } catch { break; }
        var req = ctx.Request;
        string body = req.HasEntityBody ? await new StreamReader(req.InputStream, Encoding.UTF8).ReadToEndAsync() : "";
        lock (seen) seen.Add($"{req.HttpMethod} {req.Url!.AbsolutePath} body={(body.Length == 0 ? "<pusto>" : body)}");

        var path = req.Url!.AbsolutePath;
        if (path.StartsWith("/redir/") && int.TryParse(path.AsSpan("/redir/".Length), out int code))
        {
            ctx.Response.StatusCode = code;
            ctx.Response.RedirectLocation = prefix + "landed";
        }
        else if (path == "/search" && req.HttpMethod == "QUERY")
        {
            // Wyszukiwanie z trescia (zamiast dlugiego query stringa): odfiltruj po polu "prefix".
            using var doc = JsonDocument.Parse(body);
            string p = doc.RootElement.GetProperty("prefix").GetString()!;
            string[] all = ["alfa", "alfabet", "beta", "bravo"];
            var hits = all.Where(x => x.StartsWith(p, StringComparison.Ordinal)).ToArray();
            ctx.Response.StatusCode = 200;
            ctx.Response.ContentType = "application/json";
            await ctx.Response.OutputStream.WriteAsync(JsonSerializer.SerializeToUtf8Bytes(hits));
        }
        else
        {
            ctx.Response.StatusCode = 200;
        }
        ctx.Response.Close();
    }
});

using var http = new HttpClient(new SocketsHttpHandler { AllowAutoRedirect = false });

Console.WriteLine("--- 1. Round-trip: HttpMethod.Query z cialem JSON ---");
using (var req = new HttpRequestMessage(HttpMethod.Query, prefix + "search")
       { Content = JsonContent.Create(new { prefix = "al" }) })
{
    using var resp = await http.SendAsync(req);
    Console.WriteLine($"status={(int)resp.StatusCode}, odpowiedz={await resp.Content.ReadAsStringAsync()}");
}
Console.WriteLine($"serwer zobaczyl: {seen[^1]}");

Console.WriteLine("--- 2. Rownosc i tekst ---");
Console.WriteLine($"HttpMethod.Query.Method = \"{HttpMethod.Query.Method}\", ToString = \"{HttpMethod.Query}\"");
Console.WriteLine($"Query == new HttpMethod(\"QUERY\") : {HttpMethod.Query == new HttpMethod("QUERY")}");
Console.WriteLine($"Query == new HttpMethod(\"query\") : {HttpMethod.Query == new HttpMethod("query")}");
Console.WriteLine($"ReferenceEquals(Query, new HttpMethod(\"QUERY\")) : {ReferenceEquals(HttpMethod.Query, new HttpMethod("QUERY"))}");
Console.WriteLine($"HttpMethod.Parse(\"QUERY\") jest singletonem Query : {ReferenceEquals(HttpMethod.Parse("QUERY"), HttpMethod.Query)}");

Console.WriteLine("--- 3. Dla porownania: GET z cialem ---");
try
{
    using var get = new HttpRequestMessage(HttpMethod.Get, prefix + "search") { Content = new StringContent("{\"prefix\":\"al\"}") };
    using var resp = await http.SendAsync(get);
    Console.WriteLine($"GET z cialem -> status={(int)resp.StatusCode}; serwer zobaczyl: {seen[^1]}");
}
catch (Exception e) { Console.WriteLine($"GET z cialem -> {e.GetType().Name}: {e.Message}"); }

Console.WriteLine("--- 4. Przekierowania (AllowAutoRedirect = true): jaka metode dostaje cel? ---");
using var follower = new HttpClient(new SocketsHttpHandler { AllowAutoRedirect = true });
foreach (var method in new[] { HttpMethod.Post, HttpMethod.Query })
{
    foreach (int code in new[] { 301, 302, 303, 307, 308 })
    {
        seen.Clear();
        using var req = new HttpRequestMessage(method, prefix + $"redir/{code}") { Content = new StringContent("tresc") };
        using var resp = await follower.SendAsync(req);
        string landed = seen.FirstOrDefault(s => s.Contains("/landed")) ?? "(nie dotarlo)";
        Console.WriteLine($"{method,-5} + {code} -> {landed}");
    }
}

listener.Stop();
await serverLoop;
