using System.Security.Cryptography;

namespace CtLab;

/// <summary>
/// Hand-rolled implementation of the wire structures from RFC 6962
/// ("Certificate Transparency"). No CT/Merkle NuGet package is used anywhere -
/// every struct is built byte-by-byte from the RFC so the encoding is fully
/// inspectable. Field names in comments match RFC 6962 section 3.
/// </summary>
public static class Rfc6962
{
    public const byte VersionV1 = 0;
    public const byte SignatureTypeCertificateTimestamp = 0;
    public const ushort LogEntryTypePrecert = 1;
    public const byte MerkleLeafTypeTimestampedEntry = 0;
    public const byte HashAlgoSha256 = 4;   // TLS HashAlgorithm.sha256
    public const byte SigAlgoEcdsa = 3;     // TLS SignatureAlgorithm.ecdsa

    /// <summary>
    /// Builds the byte string that is BOTH:
    ///  (a) signed directly (SHA-256/ECDSA) to produce an SCT's signature, and
    ///  (b) prefixed with a single 0x00 byte and hashed (SHA-256) to produce the
    ///      Merkle tree leaf hash for this entry.
    /// This is not a coincidence of this implementation: RFC 6962 section 3.2's
    /// "digitally-signed" input for an SCT, and section 3.4's TimestampedEntry
    /// used inside MerkleTreeLeaf, are byte-identical for v1/certificate_timestamp/
    /// timestamped_entry (all three tag values are 0), so both use this method.
    ///   version(1) | signature_type_or_leaf_type(1) | timestamp(8, BE ms) |
    ///   entry_type(2, BE) | signed_entry (PreCert: issuer_key_hash(32) + 3-byte-len tbs) |
    ///   extensions (2-byte length, empty here)
    /// </summary>
    public static byte[] BuildPrecertTimestampedEntry(byte[] issuerKeyHash32, byte[] tbsWithoutPoison, long timestampMs)
    {
        if (issuerKeyHash32.Length != 32) throw new ArgumentException("issuer_key_hash must be 32 bytes");
        if (tbsWithoutPoison.Length > 0xFFFFFF) throw new ArgumentException("tbs too large for 3-byte length");

        using var ms = new MemoryStream();
        ms.WriteByte(VersionV1);
        ms.WriteByte(SignatureTypeCertificateTimestamp); // == MerkleLeafTypeTimestampedEntry (both 0)
        WriteUInt64BE(ms, (ulong)timestampMs);
        WriteUInt16BE(ms, LogEntryTypePrecert);
        ms.Write(issuerKeyHash32);
        WriteUInt24BE(ms, (uint)tbsWithoutPoison.Length);
        ms.Write(tbsWithoutPoison);
        WriteUInt16BE(ms, 0); // CtExtensions, empty
        return ms.ToArray();
    }

    /// <summary>SHA-256(0x00 || MerkleTreeLeaf bytes) - RFC 6962 section 2.1 leaf hash.</summary>
    public static byte[] LeafHash(byte[] timestampedEntry)
    {
        var buf = new byte[timestampedEntry.Length + 1];
        buf[0] = 0x00;
        Buffer.BlockCopy(timestampedEntry, 0, buf, 1, timestampedEntry.Length);
        return SHA256.HashData(buf);
    }

    /// <summary>log_id = SHA-256 of the log's SubjectPublicKeyInfo (DER), RFC 6962 section 3.2.</summary>
    public static byte[] LogId(byte[] logSubjectPublicKeyInfoDer) => SHA256.HashData(logSubjectPublicKeyInfoDer);

    /// <summary>
    /// Signs timestampedEntry with the log's EC key and packages the full
    /// SignedCertificateTimestamp struct (RFC 6962 section 3.2):
    ///   sct_version(1) | log_id(32) | timestamp(8) | extensions(2-byte len, empty) |
    ///   hash_algo(1) | sig_algo(1) | signature (2-byte len + DER ECDSA signature)
    /// </summary>
    public static byte[] BuildSct(byte[] logId32, long timestampMs, byte[] timestampedEntry, ECDsa logPrivateKey)
    {
        byte[] signature = logPrivateKey.SignData(timestampedEntry, HashAlgorithmName.SHA256, DSASignatureFormat.Rfc3279DerSequence);

        using var ms = new MemoryStream();
        ms.WriteByte(VersionV1);
        ms.Write(logId32);
        WriteUInt64BE(ms, (ulong)timestampMs);
        WriteUInt16BE(ms, 0); // extensions
        ms.WriteByte(HashAlgoSha256);
        ms.WriteByte(SigAlgoEcdsa);
        WriteUInt16BE(ms, (ushort)signature.Length);
        ms.Write(signature);
        return ms.ToArray();
    }

    public sealed record ParsedSct(byte SctVersion, byte[] LogId, long TimestampMs, byte HashAlgo, byte SigAlgo, byte[] Signature);

    public static ParsedSct ParseSct(ReadOnlySpan<byte> sct)
    {
        int pos = 0;
        byte version = sct[pos]; pos += 1;
        byte[] logId = sct.Slice(pos, 32).ToArray(); pos += 32;
        long ts = (long)ReadUInt64BE(sct, ref pos);
        ushort extLen = ReadUInt16BE(sct, ref pos);
        pos += extLen;
        byte hashAlgo = sct[pos]; pos += 1;
        byte sigAlgo = sct[pos]; pos += 1;
        ushort sigLen = ReadUInt16BE(sct, ref pos);
        byte[] sig = sct.Slice(pos, sigLen).ToArray(); pos += sigLen;
        return new ParsedSct(version, logId, ts, hashAlgo, sigAlgo, sig);
    }

    /// <summary>Wraps one SCT into the SignedCertificateTimestampList (RFC 6962 section 3.3)
    /// that is the raw content of the X.509 extension 1.3.6.1.4.1.11129.2.4.2.</summary>
    public static byte[] BuildSctListExtensionValue(byte[] sct)
    {
        using var ms = new MemoryStream();
        // struct { opaque sct_list<1..2^16-1> } where sct_list is itself a list of opaque<1..2^16-1> entries.
        // With exactly one SCT: outer 2-byte length, then [2-byte len][sct bytes].
        ushort inner = (ushort)(2 + sct.Length);
        WriteUInt16BE(ms, inner);
        WriteUInt16BE(ms, (ushort)sct.Length);
        ms.Write(sct);
        return ms.ToArray();
    }

    public static List<byte[]> ParseSctListExtensionValue(ReadOnlySpan<byte> extValue)
    {
        var result = new List<byte[]>();
        int pos = 0;
        ushort total = ReadUInt16BE(extValue, ref pos);
        int end = pos + total;
        while (pos < end)
        {
            ushort len = ReadUInt16BE(extValue, ref pos);
            result.Add(extValue.Slice(pos, len).ToArray());
            pos += len;
        }
        return result;
    }

    public static bool VerifySctSignature(ParsedSct sct, byte[] timestampedEntryThatWasSigned, ECDsa logPublicKey)
        => logPublicKey.VerifyData(timestampedEntryThatWasSigned, sct.Signature, HashAlgorithmName.SHA256, DSASignatureFormat.Rfc3279DerSequence);

    // ---- RFC 6962 section 2.1 Merkle Tree Hashing ----

    /// <summary>MTH() of the whole tree: recursive definition straight from RFC 6962 section 2.1.
    /// Also records, for every internal split, enough information to answer an
    /// inclusion-proof (audit path) query later - see <see cref="AuditPath"/>.</summary>
    public sealed class MerkleTree
    {
        private readonly byte[][] _leaves;
        public MerkleTree(IReadOnlyList<byte[]> leafHashes) => _leaves = leafHashes.ToArray();

        public byte[] Root => Mth(0, _leaves.Length);

        private byte[] Mth(int start, int count)
        {
            if (count == 0) return SHA256.HashData(ReadOnlySpan<byte>.Empty); // MTH({}) = SHA-256()
            if (count == 1) return _leaves[start];
            int split = LargestPowerOfTwoLessThan(count);
            var left = Mth(start, split);
            var right = Mth(start + split, count - split);
            return NodeHash(left, right);
        }

        /// <summary>Audit path for leaf at <paramref name="index"/> (0-based) in a tree of
        /// <c>_leaves.Length</c> entries, ordered from the leaf towards the root, each entry
        /// tagged with whether it is the LEFT or RIGHT sibling at that level.</summary>
        public List<(byte[] Hash, bool IsRightSibling)> AuditPath(int index)
        {
            var path = new List<(byte[], bool)>();
            BuildPath(0, _leaves.Length, index, path);
            return path;
        }

        private void BuildPath(int start, int count, int index, List<(byte[], bool)> path)
        {
            if (count == 1) return;
            int split = LargestPowerOfTwoLessThan(count);
            if (index < split)
            {
                path.Add((Mth(start + split, count - split), true)); // sibling is the right subtree
                BuildPath(start, split, index, path);
            }
            else
            {
                path.Add((Mth(start, split), false)); // sibling is the left subtree
                BuildPath(start + split, count - split, index - split, path);
            }
            // Path must read leaf -> root; recursion above appends root-ward siblings
            // in leaf-to-root order already because we add before recursing deeper...
        }

        public static byte[] NodeHash(byte[] left, byte[] right)
        {
            var buf = new byte[1 + left.Length + right.Length];
            buf[0] = 0x01;
            Buffer.BlockCopy(left, 0, buf, 1, left.Length);
            Buffer.BlockCopy(right, 0, buf, 1 + left.Length, right.Length);
            return SHA256.HashData(buf);
        }

        public static byte[] VerifyAuditPath(byte[] leafHash, List<(byte[] Hash, bool IsRightSibling)> path)
        {
            var acc = leafHash;
            // path was built root-ward starting from the top split, i.e. path[0] is the
            // sibling at the TOP level and path[^1] is the sibling closest to the leaf.
            // Recompute in the same top-down recursive shape by folding from the end.
            for (int i = path.Count - 1; i >= 0; i--)
            {
                var (sib, isRight) = path[i];
                acc = isRight ? NodeHash(acc, sib) : NodeHash(sib, acc);
            }
            return acc;
        }

        private static int LargestPowerOfTwoLessThan(int n)
        {
            int k = 1;
            while (k * 2 < n) k *= 2;
            return k;
        }
    }

    // ---- Signed Tree Head (RFC 6962 section 3.5 / 3.2 TreeHeadSignature) ----

    /// <summary>digitally-signed TreeHeadSignature content:
    /// version(1) | signature_type=tree_hash(1) | timestamp(8) | tree_size(8) | root_hash(32)</summary>
    public static byte[] BuildTreeHeadSignedContent(long timestampMs, long treeSize, byte[] rootHash32)
    {
        using var ms = new MemoryStream();
        ms.WriteByte(VersionV1);
        ms.WriteByte(1); // SignatureType.tree_hash
        WriteUInt64BE(ms, (ulong)timestampMs);
        WriteUInt64BE(ms, (ulong)treeSize);
        ms.Write(rootHash32);
        return ms.ToArray();
    }

    private static void WriteUInt16BE(Stream s, ushort v) { s.WriteByte((byte)(v >> 8)); s.WriteByte((byte)v); }
    private static void WriteUInt24BE(Stream s, uint v) { s.WriteByte((byte)(v >> 16)); s.WriteByte((byte)(v >> 8)); s.WriteByte((byte)v); }
    private static void WriteUInt64BE(Stream s, ulong v) { for (int i = 7; i >= 0; i--) s.WriteByte((byte)(v >> (i * 8))); }

    private static ushort ReadUInt16BE(ReadOnlySpan<byte> b, ref int pos)
    {
        ushort v = (ushort)((b[pos] << 8) | b[pos + 1]);
        pos += 2;
        return v;
    }

    private static ulong ReadUInt64BE(ReadOnlySpan<byte> b, ref int pos)
    {
        ulong v = 0;
        for (int i = 0; i < 8; i++) v = (v << 8) | b[pos + i];
        pos += 8;
        return v;
    }
}
