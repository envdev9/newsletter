using System.Net;
using System.Net.Security;
using System.Security.Cryptography.X509Certificates;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Server.Kestrel.Core;
using Microsoft.AspNetCore.Server.Kestrel.Https;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

/// <summary>
/// X509Store (CurrentUser, wlasny magazyn "PrasowkaDemo" - w HOME wskazanym na katalog roboczy),
/// rotacja certyfikatu bez restartu Kestrela (ServerCertificateSelector) i pinning SPKI po stronie klienta.
/// </summary>
static class PinningLab
{
    const string StoreName = "PrasowkaDemo";
    const int Port = 18490;

    public static async Task Run(Pki pki)
    {
        // czysty magazyn na start
        using (var s = new X509Store(StoreName, StoreLocation.CurrentUser))
        {
            s.Open(OpenFlags.ReadWrite);
            foreach (var c in s.Certificates) s.Remove(c);
        }

        AddToStore(pki, "srv-good");

        var app = BuildServer(pki);
        await app.StartAsync();
        Console.WriteLine($"Kestrel na https://127.0.0.1:{Port}, certyfikat wybierany z magazynu CurrentUser\\{StoreName}\n");

        var pinGood = Pki.Spki(pki.PublicOnly("srv-good"));
        var pinRekeyed = Pki.Spki(pki.PublicOnly("srv-rekeyed"));
        Console.WriteLine($"pin(srv-good)     = {pinGood}");
        Console.WriteLine($"pin(srv-rekeyed)  = {pinRekeyed}");
        Console.WriteLine($"pin(srv-renewed-samekey) = {Pki.Spki(pki.PublicOnly("srv-renewed-samekey"))}\n");

        Console.WriteLine("--- 1. start: w magazynie srv-good");
        await Call(pki, "pin=srv-good", pinGood);
        await Call(pki, "pin=BLEDNY (zla wartosc)", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=");
        await Call(pki, "brak pinu (tylko lancuch)", (string?)null);

        Console.WriteLine("\n--- 2. odnowienie z TYM SAMYM kluczem: dokladamy srv-renewed-samekey do magazynu");
        AddToStore(pki, "srv-renewed-samekey");
        await Call(pki, "pin=srv-good", pinGood);

        Console.WriteLine("\n--- 3. rotacja z NOWYM kluczem: dokladamy srv-rekeyed (bez restartu serwera)");
        AddToStore(pki, "srv-rekeyed");
        await Call(pki, "pin=srv-good (stary pin)", pinGood);
        await Call(pki, "pin=srv-good + pin zapasowy srv-rekeyed", pinGood, pinRekeyed);

        Console.WriteLine("\n--- 4. sprzatanie magazynu");
        using (var s = new X509Store(StoreName, StoreLocation.CurrentUser))
        {
            s.Open(OpenFlags.ReadWrite);
            foreach (var c in s.Certificates) s.Remove(c);
            Console.WriteLine($"magazyn po sprzataniu: {s.Certificates.Count} certyfikatow");
        }
        await app.StopAsync();
    }

    static void AddToStore(Pki pki, string name)
    {
        using var s = new X509Store(StoreName, StoreLocation.CurrentUser);
        s.Open(OpenFlags.ReadWrite);
        // klucz z PEM jest "efemeryczny" - eksport/import PFX daje obiekt, ktory magazyn potrafi utrwalic
        using var withKey = pki.Server(name);
        using var persisted = X509CertificateLoader.LoadPkcs12(withKey.Export(X509ContentType.Pfx), null, X509KeyStorageFlags.PersistKeySet);
        s.Add(persisted);
        Console.WriteLine($"[store] +{name}: NotBefore={withKey.NotBefore:HH:mm:ss} serial={withKey.SerialNumber} thumb={withKey.Thumbprint[..12]}...  (w magazynie: {s.Certificates.Count})");
    }

    /// <summary>Wybor: najnowszy (NotBefore, potem serial) wazny certyfikat CN=localhost z kluczem prywatnym.</summary>
    static X509Certificate2? Pick()
    {
        using var s = new X509Store(StoreName, StoreLocation.CurrentUser);
        s.Open(OpenFlags.ReadOnly);
        return s.Certificates
            .Where(c => c.HasPrivateKey && c.Subject.Contains("CN=localhost") && c.NotBefore <= DateTime.Now && c.NotAfter > DateTime.Now)
            .OrderByDescending(c => c.NotBefore).ThenByDescending(c => c.SerialNumber)
            .FirstOrDefault();
    }

    static WebApplication BuildServer(Pki pki)
    {
        var b = WebApplication.CreateBuilder();
        b.Logging.ClearProviders();
        b.WebHost.ConfigureKestrel(k => k.Listen(IPAddress.Loopback, Port, lo => lo.UseHttps(https =>
        {
            https.ServerCertificateSelector = (_, _) => Pick();
            https.ServerCertificateChain = new X509Certificate2Collection(pki.Intermediate);
        })));
        var app = b.Build();
        app.MapGet("/", (HttpContext ctx) =>
        {
            var c = Pick();
            return $"serwer uzyl certyfikatu serial={c?.SerialNumber} thumb={c?.Thumbprint[..12]}...";
        });
        return app;
    }

    static async Task Call(Pki pki, string label, params string?[] pins)
    {
        var pinSet = pins.Where(p => p != null).Select(p => p!).ToHashSet();
        var handler = new HttpClientHandler
        {
            ServerCertificateCustomValidationCallback = (req, cert, chain, errors) =>
            {
                if (cert is null) return false;
                // 1) lancuch wg NASZEGO rootu (systemowy magazyn nie zna tego CA -> errors != None)
                using var own = new X509Chain { ChainPolicy = pki.Policy(X509RevocationMode.NoCheck) };
                if (!own.Build(cert)) return false;
                // 2) pinning: SPKI SHA-256 musi byc na liscie (jesli lista pusta - bez pinningu)
                return pinSet.Count == 0 || pinSet.Contains(Pki.Spki(cert));
            },
        };
        using var http = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(10) };
        try
        {
            var body = await http.GetStringAsync($"https://localhost:{Port}/");
            Console.WriteLine($"  [{label}] HTTP 200: {body}");
        }
        catch (Exception e)
        {
            Console.WriteLine($"  [{label}] BLAD -> {e.GetType().Name}: {e.Message} -> {e.InnerException?.GetType().Name}: {e.InnerException?.Message}");
        }
    }
}
