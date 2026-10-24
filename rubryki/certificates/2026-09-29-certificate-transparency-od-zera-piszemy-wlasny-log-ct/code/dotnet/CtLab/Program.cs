using System.Globalization;
using System.Security.Cryptography;
using CtLab;

if (args.Length == 0)
{
    PrintUsage();
    return 1;
}

try
{
    switch (args[0])
    {
        case "selftest-merkle": return SelfTestMerkle();
        case "strip": return CmdStrip(args);
        case "spki-hash": return CmdSpkiHash(args);
        case "issue-sct": return CmdIssueSct(args);
        case "merkle-demo": return CmdMerkleDemo(args);
        case "sth": return CmdSth(args);
        case "verify-final": return CmdVerifyFinal(args);
        default:
            PrintUsage();
            return 1;
    }
}
catch (Exception ex)
{
    Console.Error.WriteLine("ERROR: " + ex);
    return 2;
}

static void PrintUsage()
{
    Console.WriteLine("""
        Usage:
          selftest-merkle
          strip <cert.pem> <oid> <out.bin>
          spki-hash <ca.pem>
          issue-sct <ca.pem> <precert.pem> <logkey.pem> <logpub.pem> <timestampMsEpoch> <out-sctlist-extvalue.bin> <out-leafhash.bin> [out-extfile-fragment.txt]
          merkle-demo <our-leafhash.bin> <fillerCount> <ourIndex>
          sth <treeroot.bin> <treeSize> <timestampMsEpoch> <logkey.pem> <logpub.pem>
          verify-final <final.pem> <logpub.pem> <ca.pem> <precert-stripped-tbs.bin>
        """);
}

static byte[] ReadPemKeyPublic(string path)
{
    var ecdsa = ECDsa.Create();
    ecdsa.ImportFromPem(File.ReadAllText(path));
    return ecdsa.ExportSubjectPublicKeyInfo();
}

static ECDsa LoadPrivate(string path)
{
    var ecdsa = ECDsa.Create();
    ecdsa.ImportFromPem(File.ReadAllText(path));
    return ecdsa;
}

static ECDsa LoadPublic(string path)
{
    var ecdsa = ECDsa.Create();
    ecdsa.ImportFromPem(File.ReadAllText(path));
    return ecdsa;
}

static int CmdStrip(string[] args)
{
    // strip <cert.pem> <oid> <out.bin>
    var certDer = Asn1Surgery.PemToDer(File.ReadAllText(args[1]));
    var tbs = Asn1Surgery.RemoveExtension(certDer, args[2]);
    File.WriteAllBytes(args[3], tbs);
    Console.WriteLine($"tbs-without-{args[2]}: {tbs.Length} bytes, sha256={Convert.ToHexString(SHA256.HashData(tbs))}");
    return 0;
}

static int CmdSpkiHash(string[] args)
{
    var certDer = Asn1Surgery.PemToDer(File.ReadAllText(args[1]));
    var spki = Asn1Surgery.ExtractSubjectPublicKeyInfo(certDer);
    Console.WriteLine($"spki: {spki.Length} bytes, sha256={Convert.ToHexString(SHA256.HashData(spki))}");
    return 0;
}

static int CmdIssueSct(string[] args)
{
    // issue-sct <ca.pem> <precert.pem> <logkey.pem> <logpub.pem> <timestampMsEpoch> <out-ext.bin> <out-leafhash.bin>
    var caDer = Asn1Surgery.PemToDer(File.ReadAllText(args[1]));
    var precertDer = Asn1Surgery.PemToDer(File.ReadAllText(args[2]));
    var logPriv = LoadPrivate(args[3]);
    var logPubSpki = ReadPemKeyPublic(args[4]);
    long timestampMs = long.Parse(args[5], CultureInfo.InvariantCulture);

    var issuerKeyHash = SHA256.HashData(Asn1Surgery.ExtractSubjectPublicKeyInfo(caDer));
    var tbsNoPoison = Asn1Surgery.RemoveExtension(precertDer, "1.3.6.1.4.1.11129.2.4.3");
    var timestampedEntry = Rfc6962.BuildPrecertTimestampedEntry(issuerKeyHash, tbsNoPoison, timestampMs);
    var leafHash = Rfc6962.LeafHash(timestampedEntry);
    var logId = Rfc6962.LogId(logPubSpki);
    var sct = Rfc6962.BuildSct(logId, timestampMs, timestampedEntry, logPriv);
    var extValue = Rfc6962.BuildSctListExtensionValue(sct);

    File.WriteAllBytes(args[6], extValue);
    File.WriteAllBytes(args[7], leafHash);
    if (args.Length > 8)
    {
        // Ready-to-use fragment for an openssl -extfile: exact line needed to embed
        // this SCT list into the final certificate, no manual hex-copying required.
        File.WriteAllText(args[8], $"1.3.6.1.4.1.11129.2.4.2=DER:{Convert.ToHexString(extValue)}\n");
    }

    Console.WriteLine($"issuer_key_hash = {Convert.ToHexString(issuerKeyHash)}");
    Console.WriteLine($"tbs_without_poison = {tbsNoPoison.Length} bytes, sha256={Convert.ToHexString(SHA256.HashData(tbsNoPoison))}");
    Console.WriteLine($"log_id = {Convert.ToHexString(logId)}");
    Console.WriteLine($"timestampedEntry ({timestampedEntry.Length} bytes) = {Convert.ToHexString(timestampedEntry)}");
    Console.WriteLine($"leaf_hash = {Convert.ToHexString(leafHash)}");
    Console.WriteLine($"sct ({sct.Length} bytes) = {Convert.ToHexString(sct)}");
    Console.WriteLine($"sct base64 = {Convert.ToBase64String(sct)}");
    Console.WriteLine($"sct-list extension value ({extValue.Length} bytes) hex = {Convert.ToHexString(extValue)}");

    // Round-trip sanity: parse our own SCT bytes back and verify the signature right here.
    var parsed = Rfc6962.ParseSct(sct);
    var logPub = LoadPublic(args[4]);
    bool ok = Rfc6962.VerifySctSignature(parsed, timestampedEntry, logPub);
    Console.WriteLine($"self-check: parse SCT + verify signature with log public key -> {(ok ? "OK" : "FAILED")}");
    if (!ok) return 3;
    return 0;
}

static int CmdMerkleDemo(string[] args)
{
    // merkle-demo <our-leafhash.bin> <fillerCount> <ourIndex>
    var ourLeaf = File.ReadAllBytes(args[1]);
    int fillerCount = int.Parse(args[2], CultureInfo.InvariantCulture);
    int ourIndex = int.Parse(args[3], CultureInfo.InvariantCulture);

    var leaves = new List<byte[]>();
    for (int i = 0; i < fillerCount + 1; i++)
    {
        if (i == ourIndex) { leaves.Add(ourLeaf); continue; }
        // Synthetic filler leaf hashes standing in for "other, unrelated entries logged
        // that day" - NOT real MerkleTreeLeaf structures, just SHA-256 of a label, purely
        // to give the demo tree more than one entry. Clearly not a real certificate.
        leaves.Add(SHA256.HashData(System.Text.Encoding.ASCII.GetBytes($"prasowka-demo-filler-leaf-{i}")));
    }

    var tree = new Rfc6962.MerkleTree(leaves);
    var root = tree.Root;
    var path = tree.AuditPath(ourIndex);
    var recomputed = Rfc6962.MerkleTree.VerifyAuditPath(ourLeaf, path);

    Console.WriteLine($"tree_size = {leaves.Count}, our_index = {ourIndex}");
    Console.WriteLine($"root = {Convert.ToHexString(root)}");
    Console.WriteLine($"audit_path ({path.Count} entries, leaf->root):");
    foreach (var (hash, isRight) in path)
        Console.WriteLine($"  {(isRight ? "right" : "left ")} sibling {Convert.ToHexString(hash)}");
    Console.WriteLine($"recomputed root from leaf+audit_path = {Convert.ToHexString(recomputed)}");
    Console.WriteLine(recomputed.SequenceEqual(root)
        ? "inclusion proof verification: OK (recomputed root == published root)"
        : "inclusion proof verification: FAILED");
    File.WriteAllBytes(Path.Combine(Path.GetDirectoryName(args[1])!, "tree-root.bin"), root);
    return recomputed.SequenceEqual(root) ? 0 : 4;
}

static int CmdSth(string[] args)
{
    // sth <treeroot.bin> <treeSize> <timestampMsEpoch> <logkey.pem> <logpub.pem>
    var root = File.ReadAllBytes(args[1]);
    long treeSize = long.Parse(args[2], CultureInfo.InvariantCulture);
    long timestampMs = long.Parse(args[3], CultureInfo.InvariantCulture);
    var logPriv = LoadPrivate(args[4]);
    var logPub = LoadPublic(args[5]);

    var signedContent = Rfc6962.BuildTreeHeadSignedContent(timestampMs, treeSize, root);
    var signature = logPriv.SignData(signedContent, HashAlgorithmName.SHA256, DSASignatureFormat.Rfc3279DerSequence);
    bool ok = logPub.VerifyData(signedContent, signature, HashAlgorithmName.SHA256, DSASignatureFormat.Rfc3279DerSequence);

    Console.WriteLine($"STH: tree_size={treeSize} timestamp={timestampMs} root={Convert.ToHexString(root)}");
    Console.WriteLine($"TreeHeadSignature signed content = {Convert.ToHexString(signedContent)}");
    Console.WriteLine($"signature = {Convert.ToHexString(signature)}");
    Console.WriteLine($"verify(signature, log public key) -> {(ok ? "OK" : "FAILED")}");

    // Tamper check: flip a byte in the root and confirm the same signature now fails.
    var tamperedRoot = (byte[])root.Clone();
    tamperedRoot[0] ^= 0xFF;
    var tamperedContent = Rfc6962.BuildTreeHeadSignedContent(timestampMs, treeSize, tamperedRoot);
    bool tamperedOk = logPub.VerifyData(tamperedContent, signature, HashAlgorithmName.SHA256, DSASignatureFormat.Rfc3279DerSequence);
    Console.WriteLine($"verify same signature against a tampered root -> {(tamperedOk ? "OK (BUG!)" : "rejected, as expected")}");
    return ok && !tamperedOk ? 0 : 5;
}

static int CmdVerifyFinal(string[] args)
{
    // verify-final <final.pem> <logpub.pem> <ca.pem> <precert-stripped-tbs.bin>
    var finalDer = Asn1Surgery.PemToDer(File.ReadAllText(args[1]));
    var logPub = LoadPublic(args[2]);
    var caDer = Asn1Surgery.PemToDer(File.ReadAllText(args[3]));
    var precertStrippedTbs = File.ReadAllBytes(args[4]);

    using var cert = System.Security.Cryptography.X509Certificates.X509CertificateLoader.LoadCertificate(finalDer);
    var ext = cert.Extensions["1.3.6.1.4.1.11129.2.4.2"]
        ?? throw new InvalidOperationException("final certificate carries no SCT list extension");
    var sctList = Rfc6962.ParseSctListExtensionValue(ext.RawData);
    Console.WriteLine($"final certificate carries {sctList.Count} SCT(s) in extension 1.3.6.1.4.1.11129.2.4.2 (critical={ext.Critical})");

    var issuerKeyHash = SHA256.HashData(Asn1Surgery.ExtractSubjectPublicKeyInfo(caDer));

    // Reconstruct the precert TBS purely from the FINAL certificate - a real verifier
    // (or monitor) never sees the original precert.pem file, only the issued certificate.
    var tbsReconstructed = Asn1Surgery.RemoveExtension(finalDer, "1.3.6.1.4.1.11129.2.4.2");
    bool tbsMatches = tbsReconstructed.AsSpan().SequenceEqual(precertStrippedTbs);
    Console.WriteLine($"reconstructed precert TBS from final cert: {tbsReconstructed.Length} bytes, sha256={Convert.ToHexString(SHA256.HashData(tbsReconstructed))}");
    Console.WriteLine($"original precert TBS (poison removed):    {precertStrippedTbs.Length} bytes, sha256={Convert.ToHexString(SHA256.HashData(precertStrippedTbs))}");
    Console.WriteLine(tbsMatches
        ? "TBS reconstruction: OK - byte-identical to what was actually logged"
        : "TBS reconstruction: MISMATCH");

    bool allOk = tbsMatches;
    foreach (var sctBytes in sctList)
    {
        var parsed = Rfc6962.ParseSct(sctBytes);
        var timestampedEntry = Rfc6962.BuildPrecertTimestampedEntry(issuerKeyHash, tbsReconstructed, parsed.TimestampMs);
        bool sigOk = Rfc6962.VerifySctSignature(parsed, timestampedEntry, logPub);
        Console.WriteLine($"SCT: version={parsed.SctVersion} log_id={Convert.ToHexString(parsed.LogId)} timestamp_ms={parsed.TimestampMs} " +
                           $"hash_algo={parsed.HashAlgo} sig_algo={parsed.SigAlgo} signature_len={parsed.Signature.Length} -> verify: {(sigOk ? "OK" : "FAILED")}");
        allOk &= sigOk;
    }

    return allOk ? 0 : 6;
}

static int SelfTestMerkle()
{
    int fails = 0;
    var rng = new Random(42);
    foreach (int n in new[] { 1, 2, 3, 4, 5, 6, 7, 8, 13, 17 })
    {
        var leaves = new List<byte[]>();
        for (int i = 0; i < n; i++)
            leaves.Add(SHA256.HashData(BitConverter.GetBytes(rng.Next())));
        var tree = new Rfc6962.MerkleTree(leaves);
        var root = tree.Root;
        for (int idx = 0; idx < n; idx++)
        {
            var path = tree.AuditPath(idx);
            var recomputed = Rfc6962.MerkleTree.VerifyAuditPath(leaves[idx], path);
            bool ok = recomputed.SequenceEqual(root);
            if (!ok) fails++;
            Console.WriteLine($"n={n,3} idx={idx,3} path_len={path.Count,2} -> {(ok ? "OK" : "FAIL")}");
        }
    }
    Console.WriteLine(fails == 0 ? "selftest-merkle: ALL OK" : $"selftest-merkle: {fails} FAILURES");
    return fails == 0 ? 0 : 1;
}
