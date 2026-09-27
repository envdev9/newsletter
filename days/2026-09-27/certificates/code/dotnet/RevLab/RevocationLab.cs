using System.Diagnostics;
using System.Security.Cryptography.X509Certificates;

/// <summary>Macierz: tryb odwolan x certyfikat. Pokazuje co .NET robi z CDP/AIA.</summary>
static class RevocationLab
{
    public static void Run(Pki pki, string crlFile)
    {
        // Cache CRL .NET na Linuksie: $HOME/.dotnet/corefx/cryptography/crls  (HOME wskazuje na katalog roboczy - patrz Program.cs)
        var cache = Path.Combine(Environment.GetEnvironmentVariable("HOME")!, ".dotnet", "corefx", "cryptography", "crls");
        if (Directory.Exists(cache)) Directory.Delete(cache, recursive: true);
        Console.WriteLine($"cache CRL: {cache} (wyczyszczony)\nCRL serwowany z: {Path.GetFileName(crlFile)}\n");

        using var server = new CrlServer(crlFile);

        Row(pki, "srv-revoked", X509RevocationMode.NoCheck);
        Row(pki, "srv-revoked", X509RevocationMode.Offline);
        Row(pki, "srv-good", X509RevocationMode.Offline);
        Row(pki, "srv-good", X509RevocationMode.Online);
        Row(pki, "srv-revoked", X509RevocationMode.Online);
        Row(pki, "srv-revoked", X509RevocationMode.Offline);
        Row(pki, "srv-deadcdp", X509RevocationMode.Online);
        Row(pki, "srv-deadcdp", X509RevocationMode.Offline);
        Row(pki, "srv-good", X509RevocationMode.Online, X509RevocationFlag.EntireChain);

        Console.WriteLine("\nzawartosc cache CRL po testach:");
        if (Directory.Exists(cache))
            foreach (var f in Directory.GetFiles(cache)) Console.WriteLine($"  {Path.GetFileName(f)} ({new FileInfo(f).Length} B)");
        else Console.WriteLine("  (katalog nie istnieje)");
    }

    static void Row(Pki pki, string name, X509RevocationMode mode, X509RevocationFlag flag = X509RevocationFlag.EndCertificateOnly)
    {
        using var cert = pki.PublicOnly(name);
        using var chain = new X509Chain { ChainPolicy = pki.Policy(mode, flag) };
        var sw = Stopwatch.StartNew();
        var ok = chain.Build(cert);
        sw.Stop();
        Console.WriteLine($"[{mode,-7} {flag,-19}] {name,-12} Build={(ok ? "true " : "false")} {sw.ElapsedMilliseconds,4} ms | {Pki.Statuses(chain)}");
    }
}
