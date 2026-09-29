using System.Formats.Asn1;

namespace CtLab;

/// <summary>
/// Minimal, purpose-built DER surgery on X.509 TBSCertificate structures.
/// This is exactly the operation a CA (or a CT verifier) must perform:
/// take a certificate, and produce the TBSCertificate bytes with exactly
/// one named extension removed, everything else byte-for-byte unchanged.
///
/// Used two ways in this lab:
///   1) precert -> TBS with the "CT poison" extension (1.3.6.1.4.1.11129.2.4.3) removed
///      => this is what actually gets hashed into the Merkle tree leaf.
///   2) final certificate -> TBS with the "SCT list" extension (1.3.6.1.4.1.11129.2.4.2)
///      removed => a verifier reconstructs the precert this way, with NO access to the
///      original precert file, and it must match (1) byte-for-byte.
/// </summary>
public static class Asn1Surgery
{
    private static readonly Asn1Tag ExplicitExtensionsTag = new(TagClass.ContextSpecific, 3, true);

    public static byte[] PemToDer(string pem)
    {
        const string begin = "-----BEGIN";
        var lines = pem.Split('\n');
        var sb = new System.Text.StringBuilder();
        foreach (var raw in lines)
        {
            var l = raw.Trim();
            if (l.Length == 0 || l.StartsWith(begin) || l.StartsWith("-----END")) continue;
            sb.Append(l);
        }
        return Convert.FromBase64String(sb.ToString());
    }

    /// <summary>Raw DER bytes of the TBSCertificate (first element of the Certificate SEQUENCE).</summary>
    public static byte[] ExtractTbsCertificate(byte[] certDer)
    {
        var reader = new AsnReader(certDer, AsnEncodingRules.DER);
        var certSeq = reader.ReadSequence();
        return certSeq.ReadEncodedValue().ToArray();
    }

    /// <summary>Raw DER bytes of subjectPublicKeyInfo out of a (self-signed CA) certificate.</summary>
    public static byte[] ExtractSubjectPublicKeyInfo(byte[] certDer)
    {
        var tbs = ExtractTbsCertificate(certDer);
        var seq = new AsnReader(tbs, AsnEncodingRules.DER).ReadSequence();

        SkipOptionalExplicitVersion(seq);
        seq.ReadEncodedValue(); // serialNumber
        seq.ReadEncodedValue(); // signature AlgorithmIdentifier
        seq.ReadEncodedValue(); // issuer
        seq.ReadEncodedValue(); // validity
        seq.ReadEncodedValue(); // subject
        return seq.ReadEncodedValue().ToArray(); // subjectPublicKeyInfo
    }

    /// <summary>
    /// Returns the DER bytes of TBSCertificate with the extension whose OID is
    /// <paramref name="oidToRemove"/> deleted from the extensions SEQUENCE. All other
    /// bytes (version, serial, issuer, validity, subject, spki, remaining extensions,
    /// in their original order) are copied through unchanged.
    /// </summary>
    public static byte[] RemoveExtension(byte[] certDer, string oidToRemove)
    {
        var tbs = ExtractTbsCertificate(certDer);
        var seq = new AsnReader(tbs, AsnEncodingRules.DER).ReadSequence();

        var writer = new AsnWriter(AsnEncodingRules.DER);
        bool removed = false;
        using (writer.PushSequence())
        {
            while (seq.HasData)
            {
                var tag = seq.PeekTag();
                if (tag.TagClass == TagClass.ContextSpecific && tag.TagValue == 3 && tag.IsConstructed)
                {
                    var extWrapper = seq.ReadSequence(ExplicitExtensionsTag);
                    var extList = extWrapper.ReadSequence();

                    using (writer.PushSequence(ExplicitExtensionsTag))
                    using (writer.PushSequence())
                    {
                        while (extList.HasData)
                        {
                            var extRaw = extList.ReadEncodedValue();
                            var oid = new AsnReader(extRaw, AsnEncodingRules.DER)
                                .ReadSequence()
                                .ReadObjectIdentifier();
                            if (oid == oidToRemove)
                            {
                                removed = true;
                                continue;
                            }
                            writer.WriteEncodedValue(extRaw.Span);
                        }
                    }
                }
                else
                {
                    var raw = seq.ReadEncodedValue();
                    writer.WriteEncodedValue(raw.Span);
                }
            }
        }

        if (!removed)
            throw new InvalidOperationException($"Extension {oidToRemove} not found - nothing removed.");

        return writer.Encode();
    }

    private static void SkipOptionalExplicitVersion(AsnReader seq)
    {
        var tag = seq.PeekTag();
        if (tag.TagClass == TagClass.ContextSpecific && tag.TagValue == 0 && tag.IsConstructed)
        {
            seq.ReadEncodedValue();
        }
    }
}
