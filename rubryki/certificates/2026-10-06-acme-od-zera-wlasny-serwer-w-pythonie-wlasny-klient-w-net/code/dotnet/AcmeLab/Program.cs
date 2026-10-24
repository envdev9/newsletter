// AcmeLab - klient ACME (RFC 8555) napisany od zera: JWS ES256, nonce, thumbprint RFC 7638,
// keyAuthorization, http-01, CSR, finalize. Zadnej biblioteki ACME.
// Uzycie: dotnet run -- <scenariusz> [domena] [katalog-wyjsciowy]
//   scenariusze: happy | wrong-keyauth | reuse-nonce | der-sig | wrong-url | csr-mismatch | finalize-early | wrong-account-key | bad-nonce-retry
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using System.Text.Json;

string scenario = args.Length > 0 ? args[0] : "happy";
string domain = args.Length > 1 ? args[1] : "demo.example.test";
string outDir = args.Length > 2 ? args[2] : "work";
const string DirUrl = "http://127.0.0.1:14000/directory";
const int ChallengePort = 5002;
System.IO.Directory.CreateDirectory(outDir);

var acme = new AcmeClient(DirUrl);
acme.Quirk = scenario;

try
{
    await acme.LoadDirectory();
    Console.WriteLine($"[client] scenariusz={scenario} domena={domain}");
    Console.WriteLine($"[client] konto: thumbprint(JWK)={acme.Thumbprint}");

    var acct = await acme.Post(acme.NewAccount, new { termsOfServiceAgreed = true, contact = new[] { "mailto:demo@example.test" } }, useJwk: true);
    acme.Kid = acct.Location!;
    Console.WriteLine($"[client] newAccount -> HTTP {acct.Status}, kid={acme.Kid}");

    // --- zamowienie ---
    var ord = await acme.Post(acme.NewOrder, new { identifiers = new[] { new { type = "dns", value = domain } } });
    string orderUrl = ord.Location!;
    var ordJson = ord.Json;
    string authzUrl = ordJson.GetProperty("authorizations")[0].GetString()!;
    string finalizeUrl = ordJson.GetProperty("finalize").GetString()!;
    Console.WriteLine($"[client] newOrder -> HTTP {ord.Status}, status={ordJson.GetProperty("status").GetString()}");

    var az = (await acme.Post(authzUrl, null)).Json;
    var ch = az.GetProperty("challenges")[0];
    string token = ch.GetProperty("token").GetString()!;
    string chUrl = ch.GetProperty("url").GetString()!;
    string keyAuth = token + "." + acme.Thumbprint;           // RFC 8555 8.1
    Console.WriteLine($"[client] challenge http-01: token={token[..12]}... keyAuthorization = token.thumbprint");

    if (scenario == "finalize-early")
    {
        var (csrE, _) = MakeCsr(domain);
        await acme.Post(finalizeUrl, new { csr = AcmeClient.B64u(csrE) });
        return 0;
    }

    // --- responder http-01 (nasz mini-serwer HTTP na loopbacku) ---
    string served = scenario == "wrong-keyauth" ? token + ".AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" : keyAuth;
    using var cts = new CancellationTokenSource();
    var responder = Responder.Run(ChallengePort, "/.well-known/acme-challenge/" + token, served, cts.Token);

    await acme.Post(chUrl, new { });                           // "gotowe, sprawdz"
    Console.WriteLine("[client] POST {} na challenge -> serwer waliduje http-01...");
    string status = "pending";
    for (int i = 0; i < 20 && status is "pending" or "processing"; i++)
    {
        await Task.Delay(250);
        var a2 = (await acme.Post(authzUrl, null)).Json;
        status = a2.GetProperty("status").GetString()!;
    }
    Console.WriteLine($"[client] authorization status={status}");
    cts.Cancel();
    if (status != "valid")
    {
        var a3 = (await acme.Post(authzUrl, null)).Json;
        var err = a3.GetProperty("challenges")[0].TryGetProperty("error", out var e) ? e.ToString() : "(brak)";
        Console.WriteLine($"[client] BLAD walidacji: {err}");
        return 2;
    }

    // --- CSR + finalize ---
    var (csr, key) = MakeCsr(scenario == "csr-mismatch" ? "inna-domena.example.test" : domain);
    var fin = await acme.Post(finalizeUrl, new { csr = AcmeClient.B64u(csr) });
    Console.WriteLine($"[client] finalize -> HTTP {fin.Status}, order status={fin.Json.GetProperty("status").GetString()}");
    string certUrl = fin.Json.GetProperty("certificate").GetString()!;
    var cert = await acme.Post(certUrl, null);
    string pem = cert.Text;
    File.WriteAllText(Path.Combine(outDir, "leaf-chain.pem"), pem);
    File.WriteAllText(Path.Combine(outDir, "leaf.key"), key.ExportPkcs8PrivateKeyPem()); // KLUCZ DEMO, jednorazowy
    var leaf = X509Certificate2.CreateFromPem(pem);
    Console.WriteLine($"[client] certyfikat: subject={leaf.Subject} serial={leaf.SerialNumber[..12]}... NotAfter={leaf.NotAfter:u}");
    Console.WriteLine($"[client] zapisano {Path.Combine(outDir, "leaf-chain.pem")}");
    return 0;
}
catch (AcmeProblem p)
{
    Console.WriteLine($"[client] SERWER ODRZUCIL: HTTP {p.Status} {p.Type} - {p.Detail}");
    return 3;
}

static (byte[] csr, ECDsa key) MakeCsr(string name)
{
    var key = ECDsa.Create(ECCurve.NamedCurves.nistP256);
    var req = new CertificateRequest("CN=" + name, key, HashAlgorithmName.SHA256);
    var san = new SubjectAlternativeNameBuilder();
    san.AddDnsName(name);
    req.CertificateExtensions.Add(san.Build());
    return (req.CreateSigningRequest(), key);
}

record AcmeResponse(int Status, string? Location, string Text)
{
    public JsonElement Json => JsonDocument.Parse(Text).RootElement;
}

class AcmeProblem : Exception
{
    public int Status { get; } public string Type { get; } public string Detail { get; }
    public AcmeProblem(int status, string type, string detail) : base(type) { Status = status; Type = type; Detail = detail; }
}

class AcmeClient
{
    readonly HttpClient _http = new();
    readonly ECDsa _key = ECDsa.Create(ECCurve.NamedCurves.nistP256);   // klucz konta: jednorazowy, tylko w pamieci
    readonly string _dirUrl;
    string? _nonce;
    string? _usedNonce;
    public string? Kid;
    public string Quirk = "happy";
    public string NewAccount = "", NewOrder = "", NewNonce = "";

    public AcmeClient(string dirUrl) => _dirUrl = dirUrl;

    public static string B64u(byte[] b) => Convert.ToBase64String(b).TrimEnd('=').Replace('+', '-').Replace('/', '_');

    (string x, string y) Coords()
    {
        var q = _key.ExportParameters(false).Q;
        return (B64u(q.X!), B64u(q.Y!));                               // P-256: po 32 B, z zerami wiodacymi
    }

    object Jwk() { var (x, y) = Coords(); return new { kty = "EC", crv = "P-256", x, y }; }

    // RFC 7638: wylacznie pola wymagane, alfabetycznie, bez spacji
    public string Thumbprint
    {
        get
        {
            var (x, y) = Coords();
            string canon = $"{{\"crv\":\"P-256\",\"kty\":\"EC\",\"x\":\"{x}\",\"y\":\"{y}\"}}";
            return B64u(SHA256.HashData(Encoding.UTF8.GetBytes(canon)));
        }
    }

    public async Task LoadDirectory()
    {
        var d = JsonDocument.Parse(await _http.GetStringAsync(_dirUrl)).RootElement;
        NewAccount = d.GetProperty("newAccount").GetString()!;
        NewOrder = d.GetProperty("newOrder").GetString()!;
        NewNonce = d.GetProperty("newNonce").GetString()!;
        await FetchNonce();
        if (Quirk == "bad-nonce-retry") _nonce = "AAAAAAAAAAAAAAAAAAAAAA";   // symulacja nonce po restarcie serwera
    }

    async Task FetchNonce()
    {
        var r = await _http.SendAsync(new HttpRequestMessage(HttpMethod.Head, NewNonce));
        _nonce = r.Headers.GetValues("Replay-Nonce").First();
    }

    public async Task<AcmeResponse> Post(string url, object? payload, bool useJwk = false)
    {
        for (int attempt = 0; ; attempt++)
        {
            try { return await PostOnce(url, payload, useJwk); }
            catch (AcmeProblem p) when (p.Type.EndsWith(":badNonce") && attempt == 0 && Quirk != "reuse-nonce")
            {
                Console.WriteLine("[client] badNonce -> pobieram swiezy i ponawiam (RFC 8555 6.5)");
                await FetchNonce();
            }
        }
    }

    async Task<AcmeResponse> PostOnce(string url, object? payload, bool useJwk)
    {
        string nonce = _nonce!;
        if (Quirk == "reuse-nonce" && _usedNonce != null && !useJwk && payload != null) nonce = _usedNonce; // celowo stary nonce
        var prot = new Dictionary<string, object> { ["alg"] = "ES256", ["nonce"] = nonce, ["url"] = Quirk == "wrong-url" && !useJwk ? url + "x" : url };
        if (useJwk) prot["jwk"] = Jwk(); else prot["kid"] = Kid!;
        string p64 = B64u(JsonSerializer.SerializeToUtf8Bytes(prot));
        string pay64 = payload == null ? "" : B64u(JsonSerializer.SerializeToUtf8Bytes(payload));
        byte[] data = Encoding.ASCII.GetBytes(p64 + "." + pay64);
        // .NET domyslnie: IEEE P1363 (r||s, 64 B) = format JWS. DER = zly format dla JWS.
        var fmt = Quirk == "der-sig" && !useJwk ? DSASignatureFormat.Rfc3279DerSequence : DSASignatureFormat.IeeeP1363FixedFieldConcatenation;
        byte[] sig = _key.SignData(data, HashAlgorithmName.SHA256, fmt);
        if (Quirk == "wrong-account-key" && !useJwk) sig[10] ^= 0xFF;     // zepsuty podpis
        string body = JsonSerializer.Serialize(new { protected_ = p64, payload = pay64, signature = B64u(sig) }).Replace("protected_", "protected");
        var req = new HttpRequestMessage(HttpMethod.Post, url) { Content = new StringContent(body, Encoding.UTF8, "application/jose+json") };
        req.Content.Headers.ContentType = new("application/jose+json");
        var resp = await _http.SendAsync(req);
        _usedNonce = nonce;
        if (resp.Headers.TryGetValues("Replay-Nonce", out var n)) _nonce = n.First();
        string text = await resp.Content.ReadAsStringAsync();
        if (!resp.IsSuccessStatusCode)
        {
            var j = JsonDocument.Parse(text).RootElement;
            throw new AcmeProblem((int)resp.StatusCode, j.GetProperty("type").GetString()!, j.GetProperty("detail").GetString()!);
        }
        return new AcmeResponse((int)resp.StatusCode, resp.Headers.Location?.ToString(), text);
    }
}

static class Responder
{
    // Minimalny serwer HTTP/1.1 na surowym TcpListener, tylko 127.0.0.1. Odpowiada keyAuthorization na jedna sciezke.
    public static Task Run(int port, string path, string body, CancellationToken ct)
    {
        var l = new TcpListener(IPAddress.Loopback, port);
        l.Start();
        return Task.Run(async () =>
        {
            ct.Register(l.Stop);
            try
            {
                while (!ct.IsCancellationRequested)
                {
                    using var c = await l.AcceptTcpClientAsync(ct);
                    using var s = c.GetStream();
                    var buf = new byte[4096];
                    int n = await s.ReadAsync(buf, ct);
                    string req = Encoding.ASCII.GetString(buf, 0, n);
                    string first = req.Split("\r\n")[0];
                    string host = req.Split("\r\n").FirstOrDefault(x => x.StartsWith("Host:", StringComparison.OrdinalIgnoreCase)) ?? "";
                    Console.WriteLine($"[responder] {first} | {host}");
                    bool ok = first.StartsWith("GET " + path + " ");
                    string payload = ok ? body : "not found";
                    string resp = $"HTTP/1.1 {(ok ? "200 OK" : "404 Not Found")}\r\nContent-Type: text/plain\r\nContent-Length: {payload.Length}\r\nConnection: close\r\n\r\n{payload}";
                    await s.WriteAsync(Encoding.ASCII.GetBytes(resp), ct);
                }
            }
            catch (Exception) when (ct.IsCancellationRequested) { }
            catch (ObjectDisposedException) { }
        });
    }
}
