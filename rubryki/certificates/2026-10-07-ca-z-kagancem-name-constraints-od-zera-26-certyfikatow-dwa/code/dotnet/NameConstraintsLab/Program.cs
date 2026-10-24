// NameConstraintsLab: X.509 Name Constraints (RFC 5280 4.2.1.10) od zera.
// - PKI budowane w pamieci (ECDSA P-256), na dysk trafiaja WYLACZNIE certyfikaty publiczne (work/*.pem).
//   Klucze prywatne nie sa nigdy zapisywane.
// - Rozszerzenie NameConstraints kodowane recznie w DER (System.Formats.Asn1) - .NET nie ma dla niego klasy.
// - Kazdy przypadek walidowany dwukrotnie: X509Chain (.NET) i `openssl verify` (proces zewnetrzny).
using System.Diagnostics;
using System.Formats.Asn1;
using System.Net;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text;

var outDir = args.Length > 0 ? args[0] : "work";
Directory.CreateDirectory(outDir);

// ---------- DER NameConstraints ----------
byte[] Ip(string a, string mask) => IPAddress.Parse(a).GetAddressBytes().Concat(IPAddress.Parse(mask).GetAddressBytes()).ToArray();

byte[] EncodeNameConstraints(Constraints c)
{
    var w = new AsnWriter(AsnEncodingRules.DER);
    using (w.PushSequence())
    {
        void Subtrees(int tagNo, Constraints.Set s)
        {
            if (s.Dns.Count + s.Ip.Count + s.Email.Count == 0) return;
            using (w.PushSequence(new Asn1Tag(TagClass.ContextSpecific, tagNo)))      // [0] permitted / [1] excluded (IMPLICIT)
            {
                foreach (var d in s.Dns)   using (w.PushSequence()) w.WriteCharacterString(UniversalTagNumber.IA5String, d, new Asn1Tag(TagClass.ContextSpecific, 2));
                foreach (var e in s.Email) using (w.PushSequence()) w.WriteCharacterString(UniversalTagNumber.IA5String, e, new Asn1Tag(TagClass.ContextSpecific, 1));
                foreach (var i in s.Ip)    using (w.PushSequence()) w.WriteOctetString(i, new Asn1Tag(TagClass.ContextSpecific, 7));
            }
        }
        Subtrees(0, c.Permitted);
        Subtrees(1, c.Excluded);
    }
    return w.Encode();
}

// ---------- Authority ----------
Authority NewRoot(string cn, Constraints? nc = null, bool ncCritical = true)
{
    var key = ECDsa.Create(ECCurve.NamedCurves.nistP256);
    var req = new CertificateRequest($"CN={cn}", key, HashAlgorithmName.SHA256);
    req.CertificateExtensions.Add(new X509BasicConstraintsExtension(true, true, 1, true));
    req.CertificateExtensions.Add(new X509KeyUsageExtension(X509KeyUsageFlags.KeyCertSign | X509KeyUsageFlags.CrlSign, true));
    if (nc != null) req.CertificateExtensions.Add(new X509Extension(new Oid("2.5.29.30"), EncodeNameConstraints(nc), ncCritical));
    var cert = req.CreateSelfSigned(DateTimeOffset.UtcNow.AddDays(-1), DateTimeOffset.UtcNow.AddDays(30));
    return new Authority(cn, cert);
}

Authority NewIntermediate(Authority parent, string cn, Constraints? nc, bool ncCritical = true)
{
    var key = ECDsa.Create(ECCurve.NamedCurves.nistP256);
    var req = new CertificateRequest($"CN={cn}", key, HashAlgorithmName.SHA256);
    req.CertificateExtensions.Add(new X509BasicConstraintsExtension(true, true, 0, true));
    req.CertificateExtensions.Add(new X509KeyUsageExtension(X509KeyUsageFlags.KeyCertSign | X509KeyUsageFlags.CrlSign, true));
    if (nc != null) req.CertificateExtensions.Add(new X509Extension(new Oid("2.5.29.30"), EncodeNameConstraints(nc), ncCritical));
    var pub = req.Create(parent.Cert, DateTimeOffset.UtcNow.AddHours(-12), DateTimeOffset.UtcNow.AddDays(20), RandomNumberGenerator.GetBytes(8));
    return new Authority(cn, pub.CopyWithPrivateKey(key));
}

X509Certificate2 NewLeaf(Authority ca, Leaf l)
{
    using var key = ECDsa.Create(ECCurve.NamedCurves.nistP256);
    var req = new CertificateRequest(l.Cn is null ? "O=Prasowka DEMO" : $"CN={l.Cn}", key, HashAlgorithmName.SHA256);
    req.CertificateExtensions.Add(new X509BasicConstraintsExtension(false, false, 0, true));
    req.CertificateExtensions.Add(new X509KeyUsageExtension(X509KeyUsageFlags.DigitalSignature, true));
    req.CertificateExtensions.Add(new X509EnhancedKeyUsageExtension(new OidCollection { new Oid("1.3.6.1.5.5.7.3.1") }, false));
    if (l.Dns.Length + l.Ip.Length + l.Email.Length + l.Uri.Length > 0)
    {
        var san = new SubjectAlternativeNameBuilder();
        foreach (var d in l.Dns) san.AddDnsName(d);
        foreach (var i in l.Ip) san.AddIpAddress(IPAddress.Parse(i));
        foreach (var e in l.Email) san.AddEmailAddress(e);
        foreach (var u in l.Uri) san.AddUri(new Uri(u));
        req.CertificateExtensions.Add(san.Build());
    }
    // Zwracamy sam publiczny certyfikat (bez klucza prywatnego).
    var withKey = req.Create(ca.Cert, DateTimeOffset.UtcNow.AddHours(-1), DateTimeOffset.UtcNow.AddDays(10), RandomNumberGenerator.GetBytes(8));
    return X509CertificateLoader.LoadCertificate(withKey.RawData);
}

// ---------- weryfikatory ----------
(string, string) VerifyDotnet(X509Certificate2 leaf, Authority root, Authority inter)
{
    using var chain = new X509Chain();
    chain.ChainPolicy.TrustMode = X509ChainTrustMode.CustomRootTrust;
    chain.ChainPolicy.CustomTrustStore.Add(X509CertificateLoader.LoadCertificate(root.Cert.RawData));
    chain.ChainPolicy.ExtraStore.Add(X509CertificateLoader.LoadCertificate(inter.Cert.RawData));
    chain.ChainPolicy.RevocationMode = X509RevocationMode.NoCheck;
    bool ok = chain.Build(leaf);
    var flags = chain.ChainStatus.Select(s => s.Status.ToString()).Distinct().ToArray();
    return (ok ? "OK" : "FAIL", ok ? "" : string.Join("+", flags));
}

(string, string) VerifyOpenssl(string leafPem, string rootPem, string interPem)
{
    var psi = new ProcessStartInfo("openssl") { RedirectStandardOutput = true, RedirectStandardError = true };
    foreach (var a in new[] { "verify", "-CAfile", rootPem, "-untrusted", interPem, leafPem }) psi.ArgumentList.Add(a);
    using var p = Process.Start(psi)!;
    var text = p.StandardOutput.ReadToEnd() + p.StandardError.ReadToEnd();
    p.WaitForExit();
    var err = text.Split('\n').FirstOrDefault(l => l.StartsWith("error ")) ?? "";
    var m = System.Text.RegularExpressions.Regex.Match(err, @"error (\d+) at (\d+) depth lookup: (.*)");
    return p.ExitCode == 0 ? ("OK", "") : ("FAIL", m.Success ? $"{m.Groups[1]}@{m.Groups[2]} {m.Groups[3]}" : text.Trim());
}

// ---------- scenariusz ----------
var rootA = NewRoot("Prasowka NC Root DEMO");
var rootC = NewRoot("Prasowka NC Constrained Root DEMO", new Constraints { Permitted = { Dns = { ".corp.example.test" } } });

var ncA = new Constraints
{
    Permitted = { Dns = { ".corp.example.test" }, Ip = { Ip("192.0.2.0", "255.255.255.0") }, Email = { "corp.example.test" } },
    Excluded  = { Dns = { "secret.corp.example.test" } },
};
var interA = NewIntermediate(rootA, "NC Sub CA A", ncA);
var interB = NewIntermediate(rootA, "NC Sub CA B", ncA, ncCritical: false);
var interC = NewIntermediate(rootA, "NC Sub CA C", new Constraints { Permitted = { Dns = { "corp.example.test" } } });
var interD = NewIntermediate(rootA, "NC Sub CA D", new Constraints { Excluded = { Dns = { "example.org" } } });
var interE = NewIntermediate(rootA, "NC Sub CA E", new Constraints { Permitted = { Dns = { ".corp.example.test" } } });
var interR = NewIntermediate(rootC, "NC Sub CA R", null);
var interN = NewIntermediate(rootA, "NC Sub CA N", null);

var cases = new (string Id, string Desc, Authority Root, Authority Inter, Leaf L, string Expect)[]
{
    ("A1",  "SAN ok.corp.example.test",                       rootA, interA, new Leaf { Cn = "ok.corp.example.test", Dns = ["ok.corp.example.test"] }, "OK"),
    ("A2",  "SAN evil.example.org",                           rootA, interA, new Leaf { Cn = "evil.example.org", Dns = ["evil.example.org"] }, "FAIL"),
    ("A3",  "SAN secret.corp.example.test (excluded)",        rootA, interA, new Leaf { Cn = "secret.corp.example.test", Dns = ["secret.corp.example.test"] }, "FAIL"),
    ("A4",  "SAN a.secret.corp.example.test (pod-domena excl)", rootA, interA, new Leaf { Cn = "a.secret.corp.example.test", Dns = ["a.secret.corp.example.test"] }, "FAIL"),
    ("A5",  "2 SAN: ok.corp... + evil.example.org",           rootA, interA, new Leaf { Cn = "ok.corp.example.test", Dns = ["ok.corp.example.test", "evil.example.org"] }, "FAIL"),
    ("A6",  "SAN corp.example.test (apex vs '.corp...')",     rootA, interA, new Leaf { Cn = "corp.example.test", Dns = ["corp.example.test"] }, "FAIL"),
    ("A7",  "SAN *.corp.example.test (wildcard)",             rootA, interA, new Leaf { Cn = "x", Dns = ["*.corp.example.test"] }, "OK"),
    ("A8",  "SAN *.example.test (wildcard szerszy)",          rootA, interA, new Leaf { Cn = "x", Dns = ["*.example.test"] }, "FAIL"),
    ("A9",  "SAN OK.CORP.EXAMPLE.TEST (wielkie litery)",      rootA, interA, new Leaf { Cn = "x", Dns = ["OK.CORP.EXAMPLE.TEST"] }, "OK"),
    ("A10", "SAN dns ok + IP 192.0.2.5 (w puli)",             rootA, interA, new Leaf { Cn = "ok.corp.example.test", Dns = ["ok.corp.example.test"], Ip = ["192.0.2.5"] }, "OK"),
    ("A11", "SAN dns ok + IP 198.51.100.7 (poza pula)",       rootA, interA, new Leaf { Cn = "ok.corp.example.test", Dns = ["ok.corp.example.test"], Ip = ["198.51.100.7"] }, "FAIL"),
    ("A12", "BRAK SAN, CN=evil.example.org",                  rootA, interA, new Leaf { Cn = "evil.example.org" }, "FAIL"),
    ("A13", "SAN ok.corp... + CN=evil.example.org",           rootA, interA, new Leaf { Cn = "evil.example.org", Dns = ["ok.corp.example.test"] }, "OK"),
    ("A14", "SAN email alice@corp.example.test",              rootA, interA, new Leaf { Cn = "alice", Email = ["alice@corp.example.test"] }, "OK"),
    ("A15", "SAN email bob@evil.example.org",                 rootA, interA, new Leaf { Cn = "bob", Email = ["bob@evil.example.org"] }, "FAIL"),
    ("A16", "SAN URI https://evil.example.org/ (brak constraint na URI)", rootA, interA, new Leaf { Cn = "x", Uri = ["https://evil.example.org/"] }, "OK?"),
    ("B1",  "constraints NON-critical, SAN evil.example.org", rootA, interB, new Leaf { Cn = "evil.example.org", Dns = ["evil.example.org"] }, "FAIL?"),
    ("C1",  "permit 'corp.example.test', SAN corp.example.test", rootA, interC, new Leaf { Cn = "corp.example.test", Dns = ["corp.example.test"] }, "OK"),
    ("C2",  "permit 'corp.example.test', SAN ok.corp.example.test", rootA, interC, new Leaf { Cn = "x", Dns = ["ok.corp.example.test"] }, "OK"),
    ("C3",  "permit 'corp.example.test', SAN notcorp.example.test", rootA, interC, new Leaf { Cn = "x", Dns = ["notcorp.example.test"] }, "FAIL"),
    ("D1",  "tylko excluded example.org, SAN foo.example.test", rootA, interD, new Leaf { Cn = "x", Dns = ["foo.example.test"] }, "OK"),
    ("D2",  "tylko excluded example.org, SAN foo.example.org", rootA, interD, new Leaf { Cn = "x", Dns = ["foo.example.org"] }, "FAIL"),
    ("E1",  "constraint tylko DNS, leaf z SAN tylko-IP 203.0.113.9", rootA, interE, new Leaf { Cn = "x", Ip = ["203.0.113.9"] }, "OK"),
    ("N1",  "intermediate BEZ constraints, SAN evil.example.org", rootA, interN, new Leaf { Cn = "evil.example.org", Dns = ["evil.example.org"] }, "OK"),
    ("R1",  "constraints na ROOCIE (trust anchor), SAN evil.example.org", rootC, interR, new Leaf { Cn = "evil.example.org", Dns = ["evil.example.org"] }, "FAIL?"),
    ("R2",  "constraints na ROOCIE, SAN ok.corp.example.test", rootC, interR, new Leaf { Cn = "x", Dns = ["ok.corp.example.test"] }, "OK"),
};

foreach (var a in new[] { rootA, rootC }) File.WriteAllText(Path.Combine(outDir, $"root-{(a == rootA ? "plain" : "constrained")}.pem"), a.Cert.ExportCertificatePem());
foreach (var (n, a) in new[] { ("A", interA), ("B", interB), ("C", interC), ("D", interD), ("E", interE), ("R", interR), ("N", interN) })
    File.WriteAllText(Path.Combine(outDir, $"inter-{n}.pem"), a.Cert.ExportCertificatePem());

Console.WriteLine($"{"id",-4} {"oczek.",-6} {"dotnet",-6} {"openssl",-7} opis");
int diffs = 0;
foreach (var c in cases)
{
    var leaf = NewLeaf(c.Inter, c.L);
    var leafPem = Path.Combine(outDir, $"leaf-{c.Id}.pem");
    File.WriteAllText(leafPem, leaf.ExportCertificatePem());
    var rootPem = Path.Combine(outDir, c.Root == rootA ? "root-plain.pem" : "root-constrained.pem");
    var interPem = Path.Combine(outDir, $"inter-{c.Inter.Cn.Split(' ')[3]}.pem");
    var (dn, dnWhy) = VerifyDotnet(leaf, c.Root, c.Inter);
    var (os, osWhy) = VerifyOpenssl(leafPem, rootPem, interPem);
    var flag = dn != os ? "  <-- ROZBIEZNOSC .NET vs openssl" : "";
    if (dn != os) diffs++;
    Console.WriteLine($"{c.Id,-4} {c.Expect,-6} {dn,-6} {os,-7} {c.Desc}{flag}");
    if (dnWhy != "" || osWhy != "") Console.WriteLine($"{"",-26}.NET: {dnWhy} | openssl: {osWhy}");
}
Console.WriteLine($"rozbieznosci .NET vs openssl: {diffs}");
return 0;

// ---------- typy ----------
record Authority(string Cn, X509Certificate2 Cert);
class Leaf { public string? Cn; public string[] Dns = []; public string[] Ip = []; public string[] Email = []; public string[] Uri = []; }
class Constraints
{
    public class Set { public List<string> Dns = new(); public List<byte[]> Ip = new(); public List<string> Email = new(); }
    public Set Permitted = new();
    public Set Excluded = new();
}
