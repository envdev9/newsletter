using System.Diagnostics;

// ============================================================================
// OrderedDictionary<TKey,TValue> (System.Collections.Generic, od .NET 9)
// Nowosc .NET 10:  TryAdd(key, value, out int index)
//                  TryGetValue(key, out value, out int index)
// ============================================================================

Console.WriteLine("--- 1. Podstawy: co dokladnie zwraca 'index' ---");
{
    var d = new OrderedDictionary<string, int>();
    bool a1 = d.TryAdd("alfa", 10, out int i1);
    bool a2 = d.TryAdd("beta", 20, out int i2);
    bool a3 = d.TryAdd("alfa", 999, out int i3);   // duplikat
    Console.WriteLine($"TryAdd(alfa)   -> {a1}, index={i1}");
    Console.WriteLine($"TryAdd(beta)   -> {a2}, index={i2}");
    Console.WriteLine($"TryAdd(alfa*)  -> {a3}, index={i3}  (indeks ISTNIEJACEGO wpisu), wartosc nadal {d["alfa"]}");

    bool g1 = d.TryGetValue("beta", out int vb, out int ib);
    bool g2 = d.TryGetValue("brak", out int vx, out int ix);
    Console.WriteLine($"TryGetValue(beta) -> {g1}, value={vb}, index={ib}");
    Console.WriteLine($"TryGetValue(brak) -> {g2}, value={vx}, index={ix}  (pudlo: -1)");
}

Console.WriteLine("--- 2. Po co: ile razy kolekcja liczy klucz (komparator-licznik, 1000 kluczy) ---");
{
    const int N = 1000;
    string[] keys = Enumerable.Range(0, N).Select(i => $"klucz-{i}").ToArray();

    // Wariant A: stara droga - TryGetValue + IndexOf + SetAt  (3 wyszukiwania w tym 2 po kluczu)
    var cmpA = new CountingComparer();
    var a = new OrderedDictionary<string, int>(cmpA);
    foreach (var k in keys) a.Add(k, 0);
    cmpA.Reset();
    foreach (var k in keys)
        if (a.TryGetValue(k, out int cur)) { int idx = a.IndexOf(k); a.SetAt(idx, cur + 1); }
    Console.WriteLine($"A) TryGetValue + IndexOf + SetAt : hash/klucz = {cmpA.Hashes / (double)N:0.0}, equals/klucz = {cmpA.Equals_ / (double)N:0.0}");

    // Wariant B: stara droga - TryGetValue + indexer (a[k] = ...)
    var cmpB = new CountingComparer();
    var b = new OrderedDictionary<string, int>(cmpB);
    foreach (var k in keys) b.Add(k, 0);
    cmpB.Reset();
    foreach (var k in keys)
        if (b.TryGetValue(k, out int cur)) b[k] = cur + 1;
    Console.WriteLine($"B) TryGetValue + indexer set     : hash/klucz = {cmpB.Hashes / (double)N:0.0}, equals/klucz = {cmpB.Equals_ / (double)N:0.0}");

    // Wariant C: .NET 10 - TryGetValue(out value, out index) + SetAt
    var cmpC = new CountingComparer();
    var c = new OrderedDictionary<string, int>(cmpC);
    foreach (var k in keys) c.Add(k, 0);
    cmpC.Reset();
    foreach (var k in keys)
        if (c.TryGetValue(k, out int cur, out int idx)) c.SetAt(idx, cur + 1);
    Console.WriteLine($"C) TryGetValue(out, out) + SetAt : hash/klucz = {cmpC.Hashes / (double)N:0.0}, equals/klucz = {cmpC.Equals_ / (double)N:0.0}");

    Console.WriteLine($"   wynik identyczny? A={a.Sum(p => p.Value)}, B={b.Sum(p => p.Value)}, C={c.Sum(p => p.Value)} (oczekiwane {N})");

    // Wariant D: licznik "dodaj albo zwieksz" - 1 TryAdd(out index) zamiast ContainsKey/Add/indexer
    string[] words = Enumerable.Range(0, 3000).Select(i => $"klucz-{i % 500}").ToArray();   // 500 unikalnych
    var cmpOld = new CountingComparer();
    var oldD = new OrderedDictionary<string, int>(cmpOld);
    foreach (var w in words)
    {
        if (oldD.TryGetValue(w, out int cur)) oldD[w] = cur + 1;
        else oldD.Add(w, 1);
    }
    var cmpNew = new CountingComparer();
    var newD = new OrderedDictionary<string, int>(cmpNew);
    foreach (var w in words)
    {
        if (!newD.TryAdd(w, 1, out int idx)) newD.SetAt(idx, newD.GetAt(idx).Value + 1);
    }
    Console.WriteLine($"D) licznik slow, 3000 wejsc/500 unikalnych: stary hash={cmpOld.Hashes}, nowy hash={cmpNew.Hashes}; " +
                      $"te same wyniki? {oldD.SequenceEqual(newD)}");
}

Console.WriteLine("--- 3. Haczyk: indeks to MIGAWKA - po RemoveAt/Insert wskazuje inny wpis ---");
{
    var d = new OrderedDictionary<string, int> { ["a"] = 1, ["b"] = 2, ["c"] = 3 };
    d.TryGetValue("c", out _, out int idx);
    Console.WriteLine($"indeks 'c' = {idx}");
    d.RemoveAt(0);                         // usuwamy 'a' - wszystko sie przesuwa
    Console.WriteLine("po RemoveAt(0) (z 3 wpisow zostaly 2, stary indeks wyszedl poza zakres):");
    try { d.SetAt(idx, 100); }
    catch (Exception e) { Console.WriteLine($"  SetAt({idx}) -> {e.GetType().Name}"); }

    var e2 = new OrderedDictionary<string, int> { ["a"] = 1, ["b"] = 2, ["c"] = 3 };
    e2.TryGetValue("b", out _, out int idxB);       // 1
    e2.Insert(0, "z", 0);                            // wstawiamy z przodu
    e2.SetAt(idxB, 777);                             // CICHO nadpisuje 'a', nie 'b'!
    Console.WriteLine($"po Insert(0): SetAt({idxB}, 777) -> {string.Join(", ", e2.Select(p => $"{p.Key}={p.Value}"))}");
    Console.WriteLine($"  klucz pod indeksem {idxB} to teraz '{e2.GetAt(idxB).Key}', nie 'b' (indeks 'b' = {e2.IndexOf("b")})");
}

Console.WriteLine("--- 4. Haczyk: TKey = int - indexer to KLUCZ, GetAt to INDEKS ---");
{
    var d = new OrderedDictionary<int, string>();
    d.Add(30, "trzydziesci");
    d.Add(10, "dziesiec");
    d.Add(20, "dwadziescia");
    d.TryGetValue(10, out var val, out int idx);
    Console.WriteLine($"d[10]={d[10]}  GetAt(1)={d.GetAt(1).Value}  TryGetValue(10) -> value={val}, index={idx}");
    try { Console.WriteLine(d[0]); } catch (Exception e) { Console.WriteLine($"d[0] -> {e.GetType().Name} (to klucz 0, nie pierwszy element)"); }
    Console.WriteLine($"d.GetAt(0)={d.GetAt(0).Key} (pierwszy element wg kolejnosci wstawienia)");
}

Console.WriteLine("--- 5. Przypadki brzegowe ---");
{
    var d = new OrderedDictionary<string, int>();
    try { d.TryAdd(null!, 1, out _); } catch (Exception e) { Console.WriteLine($"TryAdd(null, out) -> {e.GetType().Name}"); }
    try { d.TryGetValue(null!, out _, out _); } catch (Exception e) { Console.WriteLine($"TryGetValue(null, out, out) -> {e.GetType().Name}"); }

    var empty = new OrderedDictionary<string, int>();
    Console.WriteLine($"pusty slownik TryGetValue -> {empty.TryGetValue("x", out int v, out int i)}, v={v}, i={i}");

    // kolejnosc enumeracji nie zmienia sie przy nieudanym TryAdd
    var o = new OrderedDictionary<string, int> { ["x"] = 1, ["y"] = 2, ["z"] = 3 };
    o.TryAdd("x", 99, out int ix);
    Console.WriteLine($"po nieudanym TryAdd(x): {string.Join(", ", o.Select(p => p.Key))} (index zwrocony: {ix})");

    // zamiana kolejnosci: indeks z TryAdd po usunieciu z konca
    var p2 = new OrderedDictionary<string, int>();
    p2.TryAdd("a", 1, out int ia);
    p2.TryAdd("b", 2, out int ib);
    p2.Remove("b");
    p2.TryAdd("c", 3, out int ic);
    Console.WriteLine($"a:{ia} b:{ib} (usuniete) c:{ic}  -> indeks 'c' zajmuje miejsce po 'b'");
}

Console.WriteLine("--- 6. Praktyka: unikalne zdarzenia w kolejnosci pierwszego wystapienia + licznik + indeks pozycji ---");
{
    string[] log = ["login", "view", "view", "buy", "view", "login", "logout", "buy"];
    var seen = new OrderedDictionary<string, int>();
    var firstPositions = new List<int>();
    for (int pos = 0; pos < log.Length; pos++)
    {
        if (seen.TryAdd(log[pos], 1, out int idx)) firstPositions.Add(pos);
        else seen.SetAt(idx, seen.GetAt(idx).Value + 1);
    }
    foreach (var (kv, n) in seen.Zip(Enumerable.Range(0, seen.Count)))
        Console.WriteLine($"  [{n}] {kv.Key,-7} x{kv.Value}  (pierwszy raz na pozycji {firstPositions[n]})");
}

Console.WriteLine("--- 7. Koszt O(n) RemoveAt/Insert (bo indeksy sie przesuwaja) - zmierzone Stopwatch, 50 000 elem. ---");
{
    var d = new OrderedDictionary<int, int>();
    for (int i = 0; i < 50_000; i++) d.Add(i, i);
    var sw = Stopwatch.StartNew();
    for (int i = 0; i < 2000; i++) { var kv = d.GetAt(0); d.RemoveAt(0); d.Add(kv.Key, kv.Value); }   // rotacja z poczatku
    long front = sw.ElapsedMilliseconds;
    sw.Restart();
    for (int i = 0; i < 2000; i++) { var kv = d.GetAt(d.Count - 1); d.RemoveAt(d.Count - 1); d.Add(kv.Key, kv.Value); }   // z konca
    long back = sw.ElapsedMilliseconds;
    Console.WriteLine($"2000x RemoveAt(0)+Add: {front} ms,  2000x RemoveAt(last)+Add: {back} ms  (czasy orientacyjne, zmienne miedzy uruchomieniami)");
}

sealed class CountingComparer : IEqualityComparer<string>
{
    public long Hashes, Equals_;
    public void Reset() { Hashes = 0; Equals_ = 0; }
    public bool Equals(string? x, string? y) { Equals_++; return string.Equals(x, y, StringComparison.Ordinal); }
    public int GetHashCode(string s) { Hashes++; return StringComparer.Ordinal.GetHashCode(s); }
}
