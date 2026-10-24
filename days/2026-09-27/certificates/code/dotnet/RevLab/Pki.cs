using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;

/// <summary>Ladowanie demo-PKI z katalogu (domyslnie code/work) i male narzedzia.</summary>
sealed class Pki
{
    public string Dir { get; }
    public X509Certificate2 Root { get; }
    public X509Certificate2 Intermediate { get; }

    public Pki(string dir)
    {
        Dir = dir;
        Root = X509CertificateLoader.LoadCertificateFromFile(Path.Combine(dir, "root", "ca.pem"));
        Intermediate = X509CertificateLoader.LoadCertificateFromFile(Path.Combine(dir, "inter", "ca.pem"));
    }

    /// <summary>Certyfikat serwera razem z kluczem prywatnym (PEM + PEM).</summary>
    public X509Certificate2 Server(string name)
    {
        // srv-renewed-samekey to NOWY certyfikat na TYM SAMYM kluczu co srv-good (odnowienie bez zmiany klucza)
        var keyName = name == "srv-renewed-samekey" ? "srv-good" : name;
        return X509Certificate2.CreateFromPemFile(Path.Combine(Dir, name + ".pem"), Path.Combine(Dir, keyName + ".key"));
    }

    public X509Certificate2 PublicOnly(string name) =>
        X509CertificateLoader.LoadCertificateFromFile(Path.Combine(Dir, name + ".pem"));

    /// <summary>Polityka "ufamy tylko naszemu rootowi" + wybrany tryb odwolan.</summary>
    public X509ChainPolicy Policy(X509RevocationMode mode, X509RevocationFlag flag = X509RevocationFlag.EndCertificateOnly)
    {
        var p = new X509ChainPolicy
        {
            TrustMode = X509ChainTrustMode.CustomRootTrust,
            RevocationMode = mode,
            RevocationFlag = flag,
            UrlRetrievalTimeout = TimeSpan.FromSeconds(3),
        };
        p.CustomTrustStore.Add(Root);
        p.ExtraStore.Add(Intermediate);
        return p;
    }

    public static string Spki(X509Certificate2 cert) =>
        Convert.ToBase64String(SHA256.HashData(cert.PublicKey.ExportSubjectPublicKeyInfo()));

    public static string Statuses(X509Chain chain) =>
        chain.ChainStatus.Length == 0
            ? "brak"
            : string.Join("; ", chain.ChainStatus.Select(s => $"{s.Status} ({s.StatusInformation.Trim()})"));
}
