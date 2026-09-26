using MtlsDemo;

// Uzycie:
//   dotnet run --project MtlsDemo -- demo  [katalog-pki]
//   dotnet run --project MtlsDemo -- serve [katalog-pki] [port] [server|server-nosan] [full|leaf-only] [eku|no-eku] [debug]
//   dotnet run --project MtlsDemo -- call  [katalog-pki] [port] [nazwa-certu-klienta|none] [host]
// Domyslny katalog PKI: /tmp/prasowka-mtls-pki (patrz openssl/generate-mtls-pki.sh).

var mode = args.Length > 0 ? args[0] : "demo";
var pki = new Pki(args.Length > 1 ? args[1] : "/tmp/prasowka-mtls-pki");

if (mode == "serve")
{
    var port = args.Length > 2 ? int.Parse(args[2]) : 18443;
    var certName = args.Length > 3 ? args[3] : "server";
    var sendInter = !(args.Length > 4 && args[4] == "leaf-only");
    var checkEku = !(args.Length > 5 && args[5] == "no-eku");
    var debug = args.Length > 6 && args[6] == "debug";
    var app = await MtlsServer.StartAsync(new ServerOptions(pki, port, certName, sendInter, checkEku, debug), Console.WriteLine);
    Console.WriteLine($"mTLS serwer nasluchuje na https://localhost:{port}/ (cert={certName}, intermediate={(sendInter ? "wysylany" : "NIE wysylany")}, EKU clientAuth={(checkEku ? "wymagane" : "nie sprawdzane")})");
    await app.WaitForShutdownAsync();
    return;
}

if (mode == "call")
{
    var port = args.Length > 2 ? int.Parse(args[2]) : 18443;
    var cert = args.Length > 3 && args[3] != "none" ? args[3] : null;
    var host = args.Length > 4 ? args[4] : "localhost";
    Console.WriteLine(await MtlsClient.CallAsync(pki, port, cert, Console.WriteLine, host));
    return;
}

const int Port = 18443;

var seen = new HashSet<string>();
void Log(string line)
{
    var side = line[..line.IndexOf(']')];
    if (seen.Add(side)) Console.WriteLine(line);
}

// HttpClient sam ponawia zapytanie, gdy serwer zerwie polaczenie - do logu bierzemy
// tylko PIERWSZA linie z kazdej strony (klient/serwer), zeby nie zasmiecac outputu.
async Task Scenario(string title, ServerOptions server, params (string label, string? cert, string host)[] clients)
{
    Console.WriteLine();
    Console.WriteLine($"=== {title} ===");
    var app = await MtlsServer.StartAsync(server, Log);
    try
    {
        foreach (var (label, cert, host) in clients)
        {
            seen.Clear();
            Console.WriteLine($"  -- klient: {label}");
            var result = await MtlsClient.CallAsync(pki, server.Port, cert, Log, host);
            Console.WriteLine($"    {result}");
        }
    }
    finally
    {
        await app.StopAsync();
        await app.DisposeAsync();
    }
}

await Scenario("A. Serwer poprawny (SAN + intermediate w handshake), RequireCertificate",
    new ServerOptions(pki, Port),
    ("alice (clientAuth, wystawca: nasze CA)", "client", "localhost"),
    ("BEZ certyfikatu klienta", null, "localhost"),
    ("mallory (EKU = serverAuth, nie clientAuth)", "client-wrongeku", "localhost"),
    ("bob (wygasly w 2025)", "client-expired", "localhost"),
    ("eve (podpisana przez OBCE CA)", "client-rogue", "localhost"),
    ("carol (ODWOLANA w CRL - .NET bez RevocationMode nie sprawdza)", "client-revoked", "localhost"));

await Scenario("B. To samo, ale polityka serwera BEZ jawnego ApplicationPolicy (CheckClientEku=false)",
    new ServerOptions(pki, Port, CheckClientEku: false),
    ("mallory (EKU = serverAuth)", "client-wrongeku", "localhost"));

await Scenario("C. Certyfikat serwera BEZ SAN (tylko CN=localhost)",
    new ServerOptions(pki, Port, CertName: "server-nosan"),
    ("alice, laczymy sie po nazwie localhost", "client", "localhost"),
    ("alice, laczymy sie po 127.0.0.1", "client", "127.0.0.1"));

await Scenario("C2. Kontrola: certyfikat serwera Z SAN (DNS:localhost, IP:127.0.0.1)",
    new ServerOptions(pki, Port),
    ("alice, po 127.0.0.1", "client", "127.0.0.1"));

await Scenario("D. Serwer NIE dosyla intermediate (tylko leaf)",
    new ServerOptions(pki, Port, SendIntermediate: false),
    ("alice", "client", "localhost"));
