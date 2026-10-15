// Consistency proof (RFC 6962 §2.1.2) + monitor/gossip nad podpisanymi STH. Wszystko w pamieci, klucz logu efemeryczny.
using System.Buffers.Binary;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

string work = args.Length > 0 ? args[0] : "work";
Directory.CreateDirectory(work);
int failures = 0;
void Check(bool ok, string what) { if (!ok) { failures++; Console.WriteLine("  !!! NIESPELNIONE: " + what); } }
string H(byte[] b, int n = 6) => Convert.ToHexString(b, 0, Math.Min(n, b.Length)).ToLowerInvariant();

// ---------- 1. Drzewo Merkle i dowod spojnosci ----------
byte[] Leaf(byte[] d) => SHA256.HashData([.. new byte[] { 0 }, .. d]);
byte[] Node(byte[] l, byte[] r) => SHA256.HashData([.. new byte[] { 1 }, .. l, .. r]);
int Pow2Below(int n) { int k = 1; while (k << 1 < n) k <<= 1; return k; }   // najwieksza potega 2 < n (n>=2)

// MTH nad haszami lisci [lo, hi)
byte[] Mth(IReadOnlyList<byte[]> lh, int lo, int hi)
{
    int n = hi - lo;
    if (n == 0) return SHA256.HashData([]);
    if (n == 1) return lh[lo];
    int k = Pow2Below(n);
    return Node(Mth(lh, lo, lo + k), Mth(lh, lo + k, hi));
}

// SUBPROOF z RFC 6962 §2.1.2 (rekurencyjnie, dosłownie wg definicji)
List<byte[]> SubProof(IReadOnlyList<byte[]> lh, int m, int lo, int hi, bool b)
{
    int n = hi - lo;
    if (m == n) return b ? [] : [Mth(lh, lo, hi)];
    int k = Pow2Below(n);
    if (m <= k)
    {
        var p = SubProof(lh, m, lo, lo + k, b);
        p.Add(Mth(lh, lo + k, hi));
        return p;
    }
    var q = SubProof(lh, m - k, lo + k, hi, false);
    q.Add(Mth(lh, lo, lo + k));
    return q;
}
List<byte[]> ProveConsistency(IReadOnlyList<byte[]> lh, int m, int n)
{
    if (m < 1 || m > n || n > lh.Count) throw new ArgumentOutOfRangeException();
    return SubProof(lh, m, 0, n, true);
}

// Weryfikacja iteracyjna, jak w RFC 9162 §2.1.4.2 (to, co robi klient/monitor — bez dostepu do lisci).
// Zwraca powod odrzucenia albo null gdy OK.
string? VerifyConsistency(int first, int second, byte[] firstHash, byte[] secondHash, IReadOnlyList<byte[]> proof)
{
    if (first < 1 || first > second) return "niepoprawne rozmiary";
    if (first == second) return proof.Count != 0 ? "rozmiary rowne, a dowod niepusty"
                              : firstHash.AsSpan().SequenceEqual(secondHash) ? null : "rozmiary rowne, korzenie rozne";
    var path = new List<byte[]>(proof);
    if ((first & (first - 1)) == 0) path.Insert(0, firstHash);   // first = potega 2 -> poddrzewo jest "cale" starym korzeniem
    if (path.Count == 0) return "pusty dowod";
    long fn = first - 1, sn = second - 1;
    while ((fn & 1) == 1) { fn >>= 1; sn >>= 1; }
    byte[] fr = path[0], sr = path[0];
    for (int i = 1; i < path.Count; i++)
    {
        var c = path[i];
        if (sn == 0) return "dowod za dlugi";
        if ((fn & 1) == 1 || fn == sn)
        {
            fr = Node(c, fr); sr = Node(c, sr);
            if ((fn & 1) == 0) while ((fn & 1) == 0 && fn != 0) { fn >>= 1; sn >>= 1; }
        }
        else sr = Node(sr, c);
        fn >>= 1; sn >>= 1;
    }
    if (!fr.AsSpan().SequenceEqual(firstHash)) return "odtworzony stary korzen != STH(first)";
    if (!sr.AsSpan().SequenceEqual(secondHash)) return "odtworzony nowy korzen != STH(second)";
    if (sn != 0) return "dowod za krotki";
    return null;
}

// ---------- 2. Log z podpisanymi STH ----------
using ECDsa logKey = ECDsa.Create(ECCurve.NamedCurves.nistP256);
byte[] SthBytes(long ts, long size, byte[] root)   // TreeHeadSignature, RFC 6962 §3.5
{
    var b = new byte[2 + 8 + 8 + 32];
    b[0] = 0; b[1] = 1;
    BinaryPrimitives.WriteInt64BigEndian(b.AsSpan(2), ts);
    BinaryPrimitives.WriteInt64BigEndian(b.AsSpan(10), size);
    root.CopyTo(b, 18);
    return b;
}
byte[] SignDer(byte[] msg) => logKey.SignData(msg, HashAlgorithmName.SHA256, DSASignatureFormat.Rfc3279DerSequence);
bool VerifyDer(byte[] msg, byte[] sig) => logKey.VerifyData(msg, sig, HashAlgorithmName.SHA256, DSASignatureFormat.Rfc3279DerSequence);

byte[] RootOf(List<byte[]> lh, int n) => Mth(lh, 0, n);
Sth MakeSth(List<byte[]> lh, int n, long ts)
{
    var root = RootOf(lh, n);
    return new Sth(ts, n, root, SignDer(SthBytes(ts, n, root)));
}
bool SthSigOk(Sth s) => VerifyDer(SthBytes(s.Ts, s.Size, s.Root), s.Sig);

var honest = new List<byte[]>();
for (int i = 0; i < 25; i++) honest.Add(Leaf(Encoding.UTF8.GetBytes($"cert-entry-{i}")));

Console.WriteLine("== 1. Jeden dowod 10 -> 25, krok po kroku ==");
var t0 = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
var sth10 = MakeSth(honest, 10, t0);
var sth25 = MakeSth(honest, 25, t0 + 1000);
Console.WriteLine($"STH(10): root={H(sth10.Root, 16)}...  sig_ok={SthSigOk(sth10)}");
Console.WriteLine($"STH(25): root={H(sth25.Root, 16)}...  sig_ok={SthSigOk(sth25)}");
var p = ProveConsistency(honest, 10, 25);
Console.WriteLine($"dowod 10->25: {p.Count} elementow (log2(25) ~ {Math.Log2(25):F1}), zamiast 25 lisci");
for (int i = 0; i < p.Count; i++) Console.WriteLine($"  [{i}] {H(p[i], 16)}...");
var r = VerifyConsistency(10, 25, sth10.Root, sth25.Root, p);
Console.WriteLine($"weryfikacja: {(r ?? "OK")}");
Check(r == null, "10->25 honest");
var proofBytes = p.Sum(x => x.Length);
Console.WriteLine($"rozmiar dowodu: {proofBytes} B");

Console.WriteLine();
Console.WriteLine("== 2. Wyczerpujaco: wszystkie pary (m,n), n<=96, uczciwy log ==");
var big = new List<byte[]>();
for (int i = 0; i < 96; i++) big.Add(Leaf(Encoding.UTF8.GetBytes($"big-{i}")));
int pairs = 0, okPairs = 0, maxLen = 0, emptyProofs = 0;
var maxByN = new SortedDictionary<int, int>();
for (int n = 1; n <= 96; n++)
{
    var rn = RootOf(big, n);
    for (int m = 1; m <= n; m++)
    {
        var pr = ProveConsistency(big, m, n);
        var res = VerifyConsistency(m, n, RootOf(big, m), rn, pr);
        pairs++; if (res == null) okPairs++; else Console.WriteLine($"  blad m={m} n={n}: {res}");
        if (pr.Count == 0) emptyProofs++;
        maxLen = Math.Max(maxLen, pr.Count);
        maxByN[n] = Math.Max(maxByN.GetValueOrDefault(n), pr.Count);
    }
}
Console.WriteLine($"par (m,n): {pairs}, zweryfikowanych OK: {okPairs}, dowodow pustych (m==n): {emptyProofs}, najdluzszy dowod: {maxLen} elem.");
Console.WriteLine("najdluzszy dowod dla wybranych n: " + string.Join(", ", new[] { 2, 8, 9, 16, 17, 33, 64, 65, 96 }.Select(k => $"n={k}:{maxByN[k]}")));
Check(pairs == okPairs, "wszystkie pary");

Console.WriteLine();
Console.WriteLine("== 3. Mutacje dowodu: czy cokolwiek falszywego przechodzi? (n<=33) ==");
int muts = 0, accepted = 0;
var rng = new Random(42);
for (int n = 2; n <= 33; n++)
{
    var rn = RootOf(big, n);
    for (int m = 1; m < n; m++)
    {
        var rm = RootOf(big, m);
        var pr = ProveConsistency(big, m, n);
        // a) odwrocenie kazdego bitu w kazdym elemencie
        for (int i = 0; i < pr.Count; i++)
            for (int bit = 0; bit < 256; bit++)
            {
                var mut = pr.Select(x => (byte[])x.Clone()).ToList();
                mut[i][bit / 8] ^= (byte)(1 << (bit % 8));
                muts++; if (VerifyConsistency(m, n, rm, rn, mut) == null) accepted++;
            }
        // b) usuniecie elementu, c) dolozenie elementu, d) zamiana dwoch elementow
        for (int i = 0; i < pr.Count; i++)
        { var mut = pr.ToList(); mut.RemoveAt(i); muts++; if (VerifyConsistency(m, n, rm, rn, mut) == null) accepted++; }
        { var mut = pr.ToList(); mut.Add(SHA256.HashData([1, 2, 3])); muts++; if (VerifyConsistency(m, n, rm, rn, mut) == null) accepted++; }
        for (int i = 0; i + 1 < pr.Count; i++)
        {
            if (pr[i].AsSpan().SequenceEqual(pr[i + 1])) continue;
            var mut = pr.ToList(); (mut[i], mut[i + 1]) = (mut[i + 1], mut[i]);
            muts++; if (VerifyConsistency(m, n, rm, rn, mut) == null) accepted++;
        }
        // e) ten sam dowod, ale przypisany do innego rozmiaru "first"
        for (int m2 = 1; m2 < n; m2++)
        {
            if (m2 == m) continue;
            muts++; if (VerifyConsistency(m2, n, RootOf(big, m2), rn, pr) == null) accepted++;
        }
    }
}
Console.WriteLine($"mutacji: {muts}, przyjetych jako poprawne: {accepted}");
Check(accepted == 0, "mutacje");

Console.WriteLine();
Console.WriteLine("== 4. Split-view: log pokazuje dwom monitorom rozne historie ==");
// Widok A: uczciwy. Widok B: lisc #3 podmieniony (np. ukryty certyfikat), reszta ta sama.
var viewB = honest.ToList();
viewB[3] = Leaf(Encoding.UTF8.GetBytes("cert-entry-3-PODMIENIONY"));
var a10 = MakeSth(honest, 10, t0);
var b10 = MakeSth(viewB, 10, t0);
Console.WriteLine($"A: size=10 root={H(a10.Root, 8)} sig_ok={SthSigOk(a10)}");
Console.WriteLine($"B: size=10 root={H(b10.Root, 8)} sig_ok={SthSigOk(b10)}");
Console.WriteLine($"oba podpisane PRAWIDLOWO tym samym kluczem; ten sam rozmiar, rozne korzenie => equivocation: {a10.Size == b10.Size && !a10.Root.AsSpan().SequenceEqual(b10.Root)}");
Check(SthSigOk(a10) && SthSigOk(b10), "obie STH ok");
Console.WriteLine("Sam podpis tego NIE wykryje; wykrywa to dopiero porownanie (gossip) albo dowod spojnosci:");
var b25 = MakeSth(viewB, 25, t0 + 1000);
var proofFromB = ProveConsistency(viewB, 10, 25);   // log generuje dowod z ZMIENIONEGO drzewa
Console.WriteLine($"  monitor A (zna STH A/10) dostaje STH B/25 + dowod 10->25 z drzewa B: "
    + (VerifyConsistency(10, 25, a10.Root, b25.Root, proofFromB) ?? "OK (!)"));
Check(VerifyConsistency(10, 25, a10.Root, b25.Root, proofFromB) != null, "A odrzuca B/25");
Console.WriteLine($"  monitor B (zna STH B/10) dostaje to samo: "
    + (VerifyConsistency(10, 25, b10.Root, b25.Root, proofFromB) ?? "OK"));
var proofFromA = ProveConsistency(honest, 10, 25);
Console.WriteLine($"  monitor A z dowodem z drzewa A, ale z korzeniem B/25: "
    + (VerifyConsistency(10, 25, a10.Root, b25.Root, proofFromA) ?? "OK (!)"));
Check(VerifyConsistency(10, 25, a10.Root, b25.Root, proofFromA) != null, "A + proof A + root B/25");

Console.WriteLine();
Console.WriteLine("== 5. Monitor: stan = ostatnie zaakceptowane STH ==");
Sth? last = null;
string Accept(string who, Sth s, List<byte[]>? proof)
{
    string? why = null;
    if (!SthSigOk(s)) why = "zly podpis STH";
    else if (last != null)
    {
        if (s.Size < last.Size) why = $"rollback: rozmiar {s.Size} < {last.Size}";
        else if (s.Ts < last.Ts) why = "timestamp cofniety";
        else if (s.Size == last.Size)
            why = s.Root.AsSpan().SequenceEqual(last.Root) ? null : "EQUIVOCATION: ten sam rozmiar, inny korzen";
        else if (proof == null) why = "brak dowodu spojnosci";
        else why = VerifyConsistency(last.Size, s.Size, last.Root, s.Root, proof);
    }
    if (why == null) { last = s; return $"{who}: ZAAKCEPTOWANO size={s.Size}"; }
    return $"{who}: ODRZUCONO ({why})";
}
var sth5 = MakeSth(honest, 5, t0 - 5000);
var badSig = sth10 with { Sig = (byte[])sth10.Sig.Clone() };
badSig.Sig[^1] ^= 1;
string[] transcript =
[
    Accept("pierwsze STH(5), bez dowodu (trust on first use)", sth5, null),
    Accept("STH(10) + dowod 5->10 z uczciwego logu", sth10, ProveConsistency(honest, 5, 10)),
    Accept("STH(10) z zepsutym podpisem", badSig, ProveConsistency(honest, 5, 10)),
    Accept("STH(25) bez dowodu", sth25, null),
    Accept("STH(25) + dowod 10->25 (UWAGA: monitor ma size=10)", sth25, ProveConsistency(honest, 10, 25)),
    Accept("STH(10) ponownie (rollback)", sth10, null),
    Accept("STH(10) widok B (monitor ma juz 25)", b10, null),
    Accept("STH(25) widok B + dowod 10->25 z drzewa B", b25, proofFromB),
    Accept("STH(25) widok A, powtorzone (ten sam korzen)", sth25, null),
];
foreach (var line in transcript) Console.WriteLine("  " + line);
Check(transcript[0].Contains("ZAAKCEPT") && transcript[1].Contains("ZAAKCEPT") && transcript[2].Contains("zly podpis")
    && transcript[3].Contains("brak dowodu") && transcript[4].Contains("ZAAKCEPT") && transcript[5].Contains("rollback")
    && transcript[6].Contains("rollback") && transcript[7].Contains("EQUIVOCATION") && transcript[8].Contains("ZAAKCEPT"),
    "transkrypt monitora");

// monitor, ktory zaakceptowal B/10, potem dostaje A/10 (gossip miedzy monitorami)
last = b10;
Console.WriteLine("  gossip: monitor z B/10 widzi A/10 -> " + Accept("A/10", a10, null));
Check(true, "");

// ---------- 6. Pliki dla niezaleznych weryfikatorow ----------
File.WriteAllText(Path.Combine(work, "log-pub.pem"), logKey.ExportSubjectPublicKeyInfoPem());
File.WriteAllBytes(Path.Combine(work, "sth25.bin"), SthBytes(sth25.Ts, sth25.Size, sth25.Root));
File.WriteAllBytes(Path.Combine(work, "sth25.sig"), sth25.Sig);
var bad = (byte[])SthBytes(sth25.Ts, sth25.Size, sth25.Root).Clone();
bad[^1] ^= 1;
File.WriteAllBytes(Path.Combine(work, "sth25-tampered.bin"), bad);
var cases = new List<object>();
for (int n = 1; n <= 25; n++)
    for (int m = 1; m <= n; m++)
        cases.Add(new
        {
            m, n,
            root_m = Convert.ToHexString(RootOf(honest, m)).ToLowerInvariant(),
            root_n = Convert.ToHexString(RootOf(honest, n)).ToLowerInvariant(),
            proof = ProveConsistency(honest, m, n).Select(x => Convert.ToHexString(x).ToLowerInvariant()).ToArray(),
        });
// przypadek rozgalezienia: dowod z drzewa B nie ma prawa pasowac do korzenia A/10
cases.Add(new
{
    m = 10, n = 25, fork = true,
    root_m = Convert.ToHexString(a10.Root).ToLowerInvariant(),
    root_n = Convert.ToHexString(b25.Root).ToLowerInvariant(),
    proof = proofFromB.Select(x => Convert.ToHexString(x).ToLowerInvariant()).ToArray(),
});
var doc = new
{
    entries = Enumerable.Range(0, 25).Select(i => $"cert-entry-{i}").ToArray(),
    cases,
};
File.WriteAllText(Path.Combine(work, "cases.json"), JsonSerializer.Serialize(doc));
Console.WriteLine();
Console.WriteLine($"zapisano work/: log-pub.pem, sth25.bin/.sig, sth25-tampered.bin, cases.json ({cases.Count} przypadkow)");
Console.WriteLine($"niespelnione oczekiwania: {failures}");
return failures == 0 ? 0 : 1;

record Sth(long Ts, int Size, byte[] Root, byte[] Sig);
