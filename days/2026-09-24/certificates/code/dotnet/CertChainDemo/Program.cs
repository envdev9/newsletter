// CertChainDemo - programowa weryfikacja łańcucha zaufania X.509 w .NET.
//
// Wczytuje trzy certyfikaty wygenerowane przez ../../openssl/generate-pki.sh:
//   ca.pem    - nasz własny root CA (self-signed, ALE świadomie mu ufamy)
//   leaf.pem  - certyfikat podpisany tym CA (normalny, "poprawny" przypadek)
//   rogue.pem - certyfikat self-signed, NIEPOWIĄZANY z naszym CA
//
// Pokazuje trzy scenariusze:
//   1. leaf.pem + nasze CA jako CustomRootTrust -> chain valid: True
//   2. leaf.pem + DOMYŚLNY magazyn zaufania systemu (nasze CA nie jest w nim
//      zainstalowane) -> chain valid: False (to jest realny błąd, który widzicie
//      w logach jako "unable to get local issuer certificate")
//   3. rogue.pem + nasze CA jako CustomRootTrust -> chain valid: False
//      (self-signed certificate, nie ma nic wspólnego z naszym CA)

using System.Security.Cryptography.X509Certificates;

string pkiDir = args.Length > 0
    ? args[0]
    : Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "openssl", "pki");

if (!Directory.Exists(pkiDir))
{
    Console.Error.WriteLine($"Nie znaleziono katalogu PKI: {Path.GetFullPath(pkiDir)}");
    Console.Error.WriteLine("Najpierw uruchom: ../../openssl/generate-pki.sh");
    return 1;
}

using var ca = X509CertificateLoader.LoadCertificateFromFile(Path.Combine(pkiDir, "ca.pem"));
using var leaf = X509CertificateLoader.LoadCertificateFromFile(Path.Combine(pkiDir, "leaf.pem"));
using var rogue = X509CertificateLoader.LoadCertificateFromFile(Path.Combine(pkiDir, "rogue.pem"));

Console.WriteLine("== Certyfikat leaf (wystawiony przez nasze CA) ==");
PrintCert(leaf);
Console.WriteLine();

Console.WriteLine("== Certyfikat CA ==");
PrintCert(ca);
Console.WriteLine();

Console.WriteLine("== Scenariusz 1: leaf.pem, nasze CA dodane jako zaufany custom root ==");
ValidateWithCustomRoot(leaf, ca);
Console.WriteLine();

Console.WriteLine("== Scenariusz 2: leaf.pem, DOMYŚLNY magazyn zaufania systemu (nasze CA NIE jest zainstalowane) ==");
ValidateWithSystemTrust(leaf);
Console.WriteLine();

Console.WriteLine("== Scenariusz 3: rogue.pem (self-signed, obcy), nasze CA jako custom root ==");
ValidateWithCustomRoot(rogue, ca);

return 0;

static void PrintCert(X509Certificate2 cert)
{
    Console.WriteLine($"  Subject: {cert.Subject}");
    Console.WriteLine($"  Issuer:  {cert.Issuer}");
    Console.WriteLine($"  Ważny:   {cert.NotBefore:yyyy-MM-dd} .. {cert.NotAfter:yyyy-MM-dd}");
    Console.WriteLine($"  Thumbprint (SHA1): {cert.Thumbprint}");
}

// Weryfikacja z JAWNIE wskazanym, zaufanym CA - nie dotykamy magazynu
// systemowego. To jest odpowiednik "zaufaj tylko temu jednemu urzędowi",
// przydatne np. przy mTLS między własnymi usługami albo w testach.
static void ValidateWithCustomRoot(X509Certificate2 subject, X509Certificate2 trustedCa)
{
    using var chain = new X509Chain();
    chain.ChainPolicy.TrustMode = X509ChainTrustMode.CustomRootTrust;
    chain.ChainPolicy.CustomTrustStore.Add(trustedCa);
    chain.ChainPolicy.RevocationMode = X509RevocationMode.NoCheck;

    bool valid = chain.Build(subject);
    Console.WriteLine($"Chain valid: {valid}");
    PrintChainStatus(chain);
}

// Weryfikacja przez DOMYŚLNY magazyn zaufania systemu operacyjnego - to robi
// każda przeglądarka i każdy HttpClient bez dodatkowej konfiguracji. Nasze
// demo-CA nie jest w nim zainstalowane, więc to MUSI się nie powieść -
// dokładnie tak samo, jak w produkcji, gdy serwer poda certyfikat podpisany
// przez urząd, którego klient nie zna.
static void ValidateWithSystemTrust(X509Certificate2 subject)
{
    using var chain = new X509Chain();
    chain.ChainPolicy.RevocationMode = X509RevocationMode.NoCheck;

    bool valid = chain.Build(subject);
    Console.WriteLine($"Chain valid: {valid}");
    PrintChainStatus(chain);
}

static void PrintChainStatus(X509Chain chain)
{
    if (chain.ChainStatus.Length == 0)
    {
        Console.WriteLine("  (brak problemów - łańcuch zbudowany do zaufanego korzenia)");
        return;
    }

    foreach (var status in chain.ChainStatus)
    {
        Console.WriteLine($"  -> {status.Status}: {status.StatusInformation.Trim()}");
    }
}
