using System.Net.Security;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;

namespace MtlsDemo;

/// <summary>Ladowanie certyfikatow z katalogu wygenerowanego przez generate-mtls-pki.sh.</summary>
public sealed class Pki(string dir)
{
    public string Dir { get; } = dir;

    public X509Certificate2 Root => X509CertificateLoader.LoadCertificateFromFile(Path.Combine(Dir, "root.pem"));
    public X509Certificate2 Intermediate => X509CertificateLoader.LoadCertificateFromFile(Path.Combine(Dir, "intermediate.pem"));

    /// <summary>Certyfikat + klucz prywatny z dwoch plikow PEM (name.pem + name.key).</summary>
    public X509Certificate2 WithKey(string name) =>
        X509Certificate2.CreateFromPemFile(Path.Combine(Dir, name + ".pem"), Path.Combine(Dir, name + ".key"));

    /// <summary>
    /// Polityka lancucha: ufamy WYLACZNIE naszemu rootowi (nie systemowemu magazynowi),
    /// sprawdzamy EKU (serverAuth albo clientAuth zaleznie od strony), bez sprawdzania odwolan.
    /// </summary>
    public X509ChainPolicy TrustPolicy(string ekuOid, bool checkEku = true)
    {
        var policy = new X509ChainPolicy
        {
            TrustMode = X509ChainTrustMode.CustomRootTrust,
            RevocationMode = X509RevocationMode.NoCheck,
        };
        policy.CustomTrustStore.Add(Root);
        if (checkEku)
            policy.ApplicationPolicy.Add(new Oid(ekuOid));
        return policy;
    }

    public const string ServerAuthOid = "1.3.6.1.5.5.7.3.1";
    public const string ClientAuthOid = "1.3.6.1.5.5.7.3.2";

    /// <summary>Kontekst klienta: jego certyfikat + intermediate, zeby serwer dostal PELNY lancuch.</summary>
    public SslStreamCertificateContext ClientContext(string name) =>
        SslStreamCertificateContext.Create(WithKey(name), new X509Certificate2Collection(Intermediate), offline: true);

    public static string Describe(X509Chain? chain) =>
        chain is null || chain.ChainStatus.Length == 0
            ? "brak"
            : string.Join("; ", chain.ChainStatus.Select(s => $"{s.Status} ({s.StatusInformation.Trim()})"));
}
