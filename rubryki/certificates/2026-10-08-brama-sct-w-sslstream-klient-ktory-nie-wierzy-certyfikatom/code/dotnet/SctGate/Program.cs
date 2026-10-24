// SctGate: SslStream, ktory odrzuca polaczenie, jesli certyfikat serwera nie niesie waznego SCT (RFC 6962).
// Wszystko dziala w jednym procesie na loopbacku; klucze prywatne zyja tylko w pamieci.
// Na dysk (katalog z argv[0]) trafiaja wylacznie certyfikaty i klucze PUBLICZNE (do kontroli niezaleznym parserem).
using System.Buffers.Binary;
using System.Formats.Asn1;
using System.Net;
using System.Net.Security;
using System.Net.Sockets;
using System.Security.Authentication;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;

const string SctOid = "1.3.6.1.4.1.11129.2.4.2";
string work = args.Length > 0 ? args[0] : "work";
Directory.CreateDirectory(work);

// ---------- PKI w pamieci ----------
CertAuthority root = CertAuthority.Create("SctGate Root CA");
CertAuthority rogue = CertAuthority.Create("Rogue Root CA");
CtLog log1 = CtLog.Create("log1");
CtLog log2 = CtLog.Create("log2");
CtLog stranger = CtLog.Create("stranger"); // nie jest na liscie zaufanych logow klienta

var trusted = new Dictionary<string, ECDsa>
{
    [Convert.ToHexString(log1.LogId)] = log1.PublicKey,
    [Convert.ToHexString(log2.LogId)] = log2.PublicKey,
};

const string Host = "srv.example.test";
long nowMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
long hourAgo = nowMs - 3_600_000;

// ---------- Scenariusze ----------
var cases = new List<Scenario>();
void Add(string id, string desc, bool expectAccept, X509Certificate2 cert, string host, int? gateMin)
    => cases.Add(new Scenario(id, desc, expectAccept, cert, host, gateMin));

Add("S0", "bez callbacka (domyslna walidacja), root nieznany systemowi", false,
    Leaf(root, Host, new Sct(log1, hourAgo)), Host, null);
Add("S1", "NAIWNY callback (lancuch+nazwa), cert BEZ SCT", true,
    Leaf(root, Host), Host, -1);
Add("S2", "brama SCT min=1, jeden wazny SCT z log1", true,
    Leaf(root, Host, new Sct(log1, hourAgo)), Host, 1);
Add("S3", "brama SCT min=1, cert BEZ SCT", false,
    Leaf(root, Host), Host, 1);
Add("S4", "brama SCT min=1, SCT od nieznanego logu", false,
    Leaf(root, Host, new Sct(stranger, hourAgo)), Host, 1);
Add("S5", "brama SCT min=1, SCT z odwroconym bitem w podpisie", false,
    Leaf(root, Host, new Sct(log1, hourAgo, FlipSigBit: true)), Host, 1);
Add("S6", "brama SCT min=1, SCT poprawnie podpisany, timestamp +1 dzien", false,
    Leaf(root, Host, new Sct(log1, nowMs + 86_400_000)), Host, 1);
X509Certificate2 donor = Leaf(root, Host, new Sct(log1, hourAgo));
Add("S7", "brama SCT min=1, SCT przeniesiony z innego certu (inny SAN)", false,
    Transplant(root, "evil.example.test", donor), "evil.example.test", 1);
Add("S8", "brama SCT min=2, dwa SCT z log1 i log2", true,
    Leaf(root, Host, new Sct(log1, hourAgo), new Sct(log2, hourAgo)), Host, 2);
Add("S9", "brama SCT min=2, tylko jeden SCT", false,
    Leaf(root, Host, new Sct(log1, hourAgo)), Host, 2);
Add("S10", "brama SCT min=2, dwa SCT z TEGO SAMEGO logu", false,
    Leaf(root, Host, new Sct(log1, hourAgo), new Sct(log1, hourAgo + 1000)), Host, 2);
Add("S11", "brama SCT min=1, SCT-smiec (nieznany log) + wazny SCT", true,
    Leaf(root, Host, new Sct(stranger, hourAgo), new Sct(log2, hourAgo)), Host, 1);
Add("S12", "brama SCT min=1, wazny SCT, ale zly host (TargetHost)", false,
    Leaf(root, Host, new Sct(log1, hourAgo)), "other.example.test", 1);
Add("S13", "brama SCT min=1, wazny SCT, ale cert z OBCEGO roota", false,
    Leaf(rogue, Host, new Sct(log1, hourAgo)), Host, 1);
Add("S14", "brama SCT min=1, SCT podpisany dla zlego issuer_key_hash", false,
    Leaf(root, Host, new Sct(log1, hourAgo, WrongIssuerHash: true)), Host, 1);
Add("S15", "brama SCT min=1, lista SCT obcieta (malformed)", false,
    LeafEx(root, Host, true, new[] { new Sct(log1, hourAgo) }), Host, 1);

// ---------- Uruchomienie ----------
Console.WriteLine($"{"id",-4} {"oczek.",-7} {"wynik",-7} {"opis"}");
int mismatches = 0;
foreach (var c in cases)
{
    string? gateReason = null;
    RemoteCertificateValidationCallback? cb = c.GateMin switch
    {
        null => null,
        -1 => (s, cert, chain, err) =>
        {
            // typowy "naprawiamy walidacje wlasnym rootem" bez zadnej polityki CT
            if ((err & SslPolicyErrors.RemoteCertificateNameMismatch) != 0) return false;
            using var x = new X509Certificate2(cert!);
            using var ch = BuildChain(root.Cert, x);
            return ch.Build(x);
        },
        int min => (s, cert, chain, err) =>
        {
            if ((err & SslPolicyErrors.RemoteCertificateNameMismatch) != 0) { gateReason = "nazwa hosta nie pasuje"; return false; }
            using var x = new X509Certificate2(cert!);
            using var ch = BuildChain(root.Cert, x);
            if (!ch.Build(x))
            {
                gateReason = "lancuch: " + string.Join(",", ch.ChainStatus.Select(st => st.Status));
                return false;
            }
            var r = SctPolicy.Evaluate(x, ch.ChainElements[1].Certificate, trusted, min, DateTimeOffset.UtcNow);
            gateReason = r.Detail;
            return r.Ok;
        },
    };

    var hs = await Handshake(c.Cert, c.Host, cb);
    bool accepted = hs.ClientOk;
    if (accepted != c.ExpectAccept) mismatches++;
    string ex = c.ExpectAccept ? "ACCEPT" : "REJECT";
    string got = accepted ? "ACCEPT" : "REJECT";
    Console.WriteLine($"{c.Id,-4} {ex,-7} {got,-7} {c.Desc}");
    if (gateReason != null) Console.WriteLine($"{"",20}brama : {gateReason}");
    Console.WriteLine($"{"",20}klient: {hs.ClientMsg}");
    if (!accepted) Console.WriteLine($"{"",20}serwer: {hs.ServerMsg}");
}
Console.WriteLine($"rozbieznosci oczekiwania vs wynik: {mismatches}");

// ---------- Artefakty PUBLICZNE do kontroli niezaleznym parserem ----------
File.WriteAllText(Path.Combine(work, "root.pem"), root.Cert.ExportCertificatePem());
File.WriteAllText(Path.Combine(work, "log1-pub.pem"), log1.PublicKey.ExportSubjectPublicKeyInfoPem());
File.WriteAllText(Path.Combine(work, "log2-pub.pem"), log2.PublicKey.ExportSubjectPublicKeyInfoPem());
File.WriteAllText(Path.Combine(work, "leaf-S2.pem"), cases.First(c => c.Id == "S2").Cert.ExportCertificatePem());
File.WriteAllText(Path.Combine(work, "leaf-S5.pem"), cases.First(c => c.Id == "S5").Cert.ExportCertificatePem());
File.WriteAllText(Path.Combine(work, "leaf-S7.pem"), cases.First(c => c.Id == "S7").Cert.ExportCertificatePem());
File.WriteAllText(Path.Combine(work, "leaf-S8.pem"), cases.First(c => c.Id == "S8").Cert.ExportCertificatePem());
Console.WriteLine("zapisano certyfikaty/klucze PUBLICZNE do: " + work);
return mismatches == 0 ? 0 : 1;

// =====================================================================================
X509Chain BuildChain(X509Certificate2 trustedRoot, X509Certificate2 leafCert)
{
    var ch = new X509Chain();
    ch.ChainPolicy.TrustMode = X509ChainTrustMode.CustomRootTrust;
    ch.ChainPolicy.CustomTrustStore.Add(trustedRoot);
    ch.ChainPolicy.RevocationMode = X509RevocationMode.NoCheck;
    return ch;
}

static async Task<(bool ClientOk, string ClientMsg, string ServerMsg, string Proto)> Handshake(
    X509Certificate2 serverCert, string targetHost, RemoteCertificateValidationCallback? cb)
{
    var listener = new TcpListener(IPAddress.Loopback, 0);
    listener.Start();
    int port = ((IPEndPoint)listener.LocalEndpoint).Port;
    using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(15));

    var server = Task.Run(async () =>
    {
        try
        {
            using var tcp = await listener.AcceptTcpClientAsync(cts.Token);
            using var ss = new SslStream(tcp.GetStream(), false);
            await ss.AuthenticateAsServerAsync(new SslServerAuthenticationOptions { ServerCertificate = serverCert }, cts.Token);
            var buf = new byte[5];
            await ss.ReadExactlyAsync(buf, cts.Token);
            await ss.WriteAsync("pong"u8.ToArray(), cts.Token);
            return $"handshake OK, odebrano \"{System.Text.Encoding.ASCII.GetString(buf)}\"";
        }
        catch (Exception e) { return Short(e); }
    });

    string cmsg; bool ok = false; string proto = "-";
    try
    {
        using var tcp = new TcpClient();
        await tcp.ConnectAsync(IPAddress.Loopback, port, cts.Token);
        using var cs = new SslStream(tcp.GetStream(), false, cb);
        await cs.AuthenticateAsClientAsync(new SslClientAuthenticationOptions { TargetHost = targetHost }, cts.Token);
        proto = cs.SslProtocol.ToString();
        await cs.WriteAsync("hello"u8.ToArray(), cts.Token);
        var rb = new byte[4];
        await cs.ReadExactlyAsync(rb, cts.Token);
        ok = true;
        cmsg = $"handshake OK ({proto}), odpowiedz \"{System.Text.Encoding.ASCII.GetString(rb)}\"";
    }
    catch (Exception e) { cmsg = Short(e); }
    string smsg = await server;
    listener.Stop();
    return (ok, cmsg, smsg, proto);
}

static string Short(Exception e)
{
    string m = e.Message.Split('\n')[0];
    return e.GetType().Name + ": " + m + (e.InnerException != null ? " [inner " + e.InnerException.GetType().Name + ": " + e.InnerException.Message.Split('\n')[0] + "]" : "");
}

// ---------- wystawianie certyfikatow ----------
X509Certificate2 Leaf(CertAuthority ca, string host, params Sct[] specs)
    => LeafEx(ca, host, false, specs);

X509Certificate2 LeafEx(CertAuthority ca, string host, bool truncateList, Sct[] specs)
{
    var key = ECDsa.Create(ECCurve.NamedCurves.nistP256);
    byte[] serial = new byte[8];
    RandomNumberGenerator.Fill(serial);
    serial[0] &= 0x3F; serial[0] |= 0x01;
    var nb = DateTimeOffset.UtcNow.AddDays(-1);
    var na = DateTimeOffset.UtcNow.AddDays(30);
    nb = new DateTimeOffset(nb.Year, nb.Month, nb.Day, nb.Hour, nb.Minute, nb.Second, TimeSpan.Zero);
    na = new DateTimeOffset(na.Year, na.Month, na.Day, na.Hour, na.Minute, na.Second, TimeSpan.Zero);

    X509Certificate2 pre = IssueRaw(ca, key, host, serial, nb, na, null);
    if (specs.Length == 0) return pre.CopyWithPrivateKey(key);

    byte[] tbs = Der.RawTbs(pre.RawData);
    byte[] issuerHash = SHA256.HashData(ca.Cert.PublicKey.ExportSubjectPublicKeyInfo());
    var scts = new List<byte[]>();
    foreach (var s in specs)
    {
        byte[] ih = s.WrongIssuerHash ? SHA256.HashData("nie-ten-issuer"u8.ToArray()) : issuerHash;
        scts.Add(s.Log.IssueSct(s.TimestampMs, ih, tbs, s.FlipSigBit));
    }
    byte[] list = SctCodec.EncodeList(scts, truncateList);
    X509Certificate2 fin = IssueRaw(ca, key, host, serial, nb, na, list);
    // kontrola: po wycieciu SCT finalny cert ma TBS bajt-w-bajt rowny TBS precertu
    if (!Der.StripExtension(fin.RawData, SctOid).AsSpan().SequenceEqual(tbs))
        throw new InvalidOperationException("TBS po wycieciu SCT != TBS precertu");
    return fin.CopyWithPrivateKey(key);
}

// bierze rozszerzenie SCT z donora i wkleja do certu o innym SAN (ten sam serial i daty)
X509Certificate2 Transplant(CertAuthority ca, string host, X509Certificate2 donorCert)
{
    var key = ECDsa.Create(ECCurve.NamedCurves.nistP256);
    var donorExt = donorCert.Extensions[SctOid]!;
    var cert = IssueRaw(ca, key, host, donorCert.GetSerialNumber().Reverse().ToArray(), donorCert.NotBefore, donorCert.NotAfter, donorExt.RawData);
    return cert.CopyWithPrivateKey(key);
}

static X509Certificate2 IssueRaw(CertAuthority ca, ECDsa key, string host, byte[] serial, DateTimeOffset nb, DateTimeOffset na, byte[]? sctExtDerOctets)
{
    var req = new CertificateRequest("CN=" + host, key, HashAlgorithmName.SHA256);
    req.CertificateExtensions.Add(new X509BasicConstraintsExtension(false, false, 0, true));
    req.CertificateExtensions.Add(new X509KeyUsageExtension(X509KeyUsageFlags.DigitalSignature, true));
    req.CertificateExtensions.Add(new X509EnhancedKeyUsageExtension(new OidCollection { new Oid("1.3.6.1.5.5.7.3.1") }, false));
    var san = new SubjectAlternativeNameBuilder();
    san.AddDnsName(host);
    req.CertificateExtensions.Add(san.Build());
    if (sctExtDerOctets != null)
        req.CertificateExtensions.Add(new X509Extension(new Oid(SctOid), sctExtDerOctets, false));
    return req.Create(ca.Cert, nb, na, serial);
}

// =====================================================================================
record Sct(CtLog Log, long TimestampMs, bool FlipSigBit = false, bool WrongIssuerHash = false);
record Scenario(string Id, string Desc, bool ExpectAccept, X509Certificate2 Cert, string Host, int? GateMin);

sealed class CertAuthority
{
    public required X509Certificate2 Cert { get; init; }
    public static CertAuthority Create(string name)
    {
        var key = ECDsa.Create(ECCurve.NamedCurves.nistP256);
        var req = new CertificateRequest("CN=" + name, key, HashAlgorithmName.SHA256);
        req.CertificateExtensions.Add(new X509BasicConstraintsExtension(true, false, 0, true));
        req.CertificateExtensions.Add(new X509KeyUsageExtension(X509KeyUsageFlags.KeyCertSign | X509KeyUsageFlags.CrlSign, true));
        req.CertificateExtensions.Add(new X509SubjectKeyIdentifierExtension(req.PublicKey, false));
        return new CertAuthority { Cert = req.CreateSelfSigned(DateTimeOffset.UtcNow.AddDays(-2), DateTimeOffset.UtcNow.AddDays(365)) };
    }
}

sealed class CtLog
{
    readonly ECDsa _key;
    public byte[] LogId { get; }
    public ECDsa PublicKey { get; }
    CtLog(ECDsa key)
    {
        _key = key;
        byte[] spki = key.ExportSubjectPublicKeyInfo();
        LogId = SHA256.HashData(spki);
        PublicKey = ECDsa.Create();
        PublicKey.ImportSubjectPublicKeyInfo(spki, out _);
    }
    public static CtLog Create(string _) => new(ECDsa.Create(ECCurve.NamedCurves.nistP256));

    public byte[] IssueSct(long tsMs, byte[] issuerKeyHash, byte[] tbsPrecert, bool flipSigBit)
    {
        byte[] signed = SctCodec.SignedData(tsMs, issuerKeyHash, tbsPrecert);
        byte[] sig = _key.SignData(signed, HashAlgorithmName.SHA256, DSASignatureFormat.Rfc3279DerSequence);
        if (flipSigBit) sig[sig.Length - 1] ^= 0x01;
        return SctCodec.EncodeSct(LogId, tsMs, sig);
    }
}

static class SctCodec
{
    // digitally-signed struct z RFC 6962 par. 3.2 (precert_entry)
    public static byte[] SignedData(long tsMs, byte[] issuerKeyHash, byte[] tbs)
    {
        using var ms = new MemoryStream();
        ms.WriteByte(0);                      // sct_version v1
        ms.WriteByte(0);                      // signature_type = certificate_timestamp
        Span<byte> t = stackalloc byte[8]; BinaryPrimitives.WriteInt64BigEndian(t, tsMs); ms.Write(t);
        ms.WriteByte(0); ms.WriteByte(1);     // entry_type = precert_entry
        ms.Write(issuerKeyHash);              // 32 B
        ms.WriteByte((byte)(tbs.Length >> 16)); ms.WriteByte((byte)(tbs.Length >> 8)); ms.WriteByte((byte)tbs.Length); // uint24
        ms.Write(tbs);
        ms.WriteByte(0); ms.WriteByte(0);     // extensions<0..2^16-1> = pusta
        return ms.ToArray();
    }

    public static byte[] EncodeSct(byte[] logId, long tsMs, byte[] sigDer)
    {
        using var ms = new MemoryStream();
        ms.WriteByte(0);
        ms.Write(logId);
        Span<byte> t = stackalloc byte[8]; BinaryPrimitives.WriteInt64BigEndian(t, tsMs); ms.Write(t);
        ms.WriteByte(0); ms.WriteByte(0);     // extensions pusta
        ms.WriteByte(4); ms.WriteByte(3);     // hash = sha256, sig = ecdsa
        ms.WriteByte((byte)(sigDer.Length >> 8)); ms.WriteByte((byte)sigDer.Length);
        ms.Write(sigDer);
        return ms.ToArray();
    }

    // zwraca zawartosc extnValue: DER OCTET STRING( SignedCertificateTimestampList )
    public static byte[] EncodeList(List<byte[]> scts, bool truncate)
    {
        using var body = new MemoryStream();
        foreach (var s in scts) { body.WriteByte((byte)(s.Length >> 8)); body.WriteByte((byte)s.Length); body.Write(s); }
        byte[] b = body.ToArray();
        var list = new byte[2 + b.Length];
        BinaryPrimitives.WriteUInt16BigEndian(list, (ushort)b.Length);
        b.CopyTo(list, 2);
        if (truncate) list = list[..(list.Length - 10)]; // psuje dlugosci
        var w = new AsnWriter(AsnEncodingRules.DER);
        w.WriteOctetString(list);
        return w.Encode();
    }
}

sealed record PolicyResult(bool Ok, string Detail);

static class SctPolicy
{
    public static PolicyResult Evaluate(X509Certificate2 leaf, X509Certificate2 issuer,
        Dictionary<string, ECDsa> trustedLogs, int minDistinctLogs, DateTimeOffset now)
    {
        var ext = leaf.Extensions["1.3.6.1.4.1.11129.2.4.2"];
        if (ext == null) return new(false, "brak rozszerzenia SCT");

        byte[] tbs = Der.StripExtension(leaf.RawData, "1.3.6.1.4.1.11129.2.4.2");
        byte[] issuerHash = SHA256.HashData(issuer.PublicKey.ExportSubjectPublicKeyInfo());
        var okLogs = new HashSet<string>();
        var notes = new List<string>();
        try
        {
            byte[] list = new AsnReader(ext.RawData, AsnEncodingRules.DER).ReadOctetString();
            int total = BinaryPrimitives.ReadUInt16BigEndian(list);
            if (total != list.Length - 2) return new(false, $"malformed: dlugosc listy {total} != {list.Length - 2}");
            int p = 2;
            int idx = 0;
            while (p < list.Length)
            {
                int len = BinaryPrimitives.ReadUInt16BigEndian(list.AsSpan(p)); p += 2;
                var sct = list.AsSpan(p, len); p += len;
                notes.Add($"SCT#{idx++}: " + CheckOne(sct, tbs, issuerHash, trustedLogs, now, okLogs));
            }
        }
        catch (Exception e) when (e is ArgumentException or AsnContentException or IndexOutOfRangeException or CryptographicException)
        {
            return new(false, "malformed: " + e.GetType().Name);
        }
        string summary = $"{okLogs.Count} wazny(ch) z roznych logow (wymagane {minDistinctLogs}); " + string.Join("; ", notes);
        return new(okLogs.Count >= minDistinctLogs, summary);
    }

    static string CheckOne(ReadOnlySpan<byte> s, byte[] tbs, byte[] issuerHash, Dictionary<string, ECDsa> logs, DateTimeOffset now, HashSet<string> okLogs)
    {
        if (s[0] != 0) return "wersja != v1";
        string logId = Convert.ToHexString(s.Slice(1, 32));
        long ts = BinaryPrimitives.ReadInt64BigEndian(s.Slice(33, 8));
        int extLen = BinaryPrimitives.ReadUInt16BigEndian(s.Slice(41));
        int q = 43 + extLen;
        if (s[q] != 4 || s[q + 1] != 3) return "nieobslugiwany algorytm podpisu";
        int sigLen = BinaryPrimitives.ReadUInt16BigEndian(s.Slice(q + 2));
        var sig = s.Slice(q + 4, sigLen).ToArray();
        if (q + 4 + sigLen != s.Length) return "malformed: nadmiarowe bajty";

        if (!logs.TryGetValue(logId, out var key)) return $"nieznany log {logId[..8]}...";
        if (ts > now.ToUnixTimeMilliseconds()) return "timestamp z przyszlosci";
        byte[] signed = SctCodec.SignedData(ts, issuerHash, tbs);
        if (!key.VerifyData(signed, sig, HashAlgorithmName.SHA256, DSASignatureFormat.Rfc3279DerSequence))
            return $"zly podpis (log {logId[..8]}...)";
        okLogs.Add(logId);
        return $"OK (log {logId[..8]}...)";
    }
}

static class Der
{
    // surowe bajty TBSCertificate z certyfikatu
    public static byte[] RawTbs(byte[] certDer)
    {
        var cert = new AsnReader(certDer, AsnEncodingRules.DER).ReadSequence();
        return cert.ReadEncodedValue().ToArray();
    }

    // TBSCertificate z wycietym rozszerzeniem o danym OID (rekonstrukcja precertu wg RFC 6962 par. 3.2)
    public static byte[] StripExtension(byte[] certDer, string oid)
    {
        var tbs = new AsnReader(certDer, AsnEncodingRules.DER).ReadSequence().ReadSequence();
        var w = new AsnWriter(AsnEncodingRules.DER);
        using (w.PushSequence())
        {
            while (tbs.HasData)
            {
                var tag = tbs.PeekTag();
                if (tag.TagClass == TagClass.ContextSpecific && tag.TagValue == 3)
                {
                    var exts = tbs.ReadSequence(tag).ReadSequence();
                    using (w.PushSequence(tag))
                    using (w.PushSequence())
                    {
                        while (exts.HasData)
                        {
                            byte[] raw = exts.PeekEncodedValue().ToArray();
                            string o = exts.ReadSequence().ReadObjectIdentifier();
                            if (o != oid) w.WriteEncodedValue(raw);
                        }
                    }
                }
                else w.WriteEncodedValue(tbs.ReadEncodedValue().Span);
            }
        }
        return w.Encode();
    }
}
