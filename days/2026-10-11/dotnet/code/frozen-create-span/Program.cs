using System.Collections.Frozen;

// Zrodlo danych: tablica/stackalloc/collection expression - bez posredniego Dictionary<,> czy List<,>.

Console.WriteLine("--- 1. FrozenDictionary.Create z ReadOnlySpan<KeyValuePair<,>> (collection expression) ---");
// Uwaga: wnioskowanie TKey/TValue z collection expression nie dziala - trzeba podac typy jawnie.
var kody = FrozenDictionary.Create<string, int>([new("PL", 48), new("DE", 49), new("FR", 33)]);
Console.WriteLine($"Count={kody.Count}, PL={kody["PL"]}, TryGetValue(\"XX\")={kody.TryGetValue("XX", out _)}");

Console.WriteLine("--- 2. Z komparatorem: UWAGA na kolejnosc argumentow (komparator PIERWSZY) ---");
var ci = FrozenDictionary.Create<string, int>(StringComparer.OrdinalIgnoreCase, [new("pl", 48), new("de", 49)]);
Console.WriteLine($"ci[\"PL\"]={ci["PL"]}, ci[\"De\"]={ci["De"]}, Comparer={ci.Comparer.GetType().Name}");

Console.WriteLine("--- 3. Ze stackalloc (struktury bez referencji; tu int->int) ---");
Span<KeyValuePair<int, int>> bufor = stackalloc KeyValuePair<int, int>[4];
for (int i = 0; i < bufor.Length; i++) bufor[i] = new(i, i * i);
var kwadraty = FrozenDictionary.Create<int, int>(bufor);
bufor[0] = new(0, 999); // mutacja zrodla po Create
Console.WriteLine($"kwadraty: {string.Join(", ", kwadraty.Select(kv => $"{kv.Key}->{kv.Value}"))}  (zrodlo zmutowane po Create: kwadraty[0]={kwadraty[0]})");

Console.WriteLine("--- 4. Duplikaty kluczy ---");
KeyValuePair<string, int>[] dup = [new("a", 1), new("a", 2), new("b", 3)];
var zSpan = FrozenDictionary.Create<string, int>(dup.AsSpan());
Console.WriteLine($"Create(span):         Count={zSpan.Count}, a={zSpan["a"]}");
var zLinq = dup.ToFrozenDictionary();
Console.WriteLine($"ToFrozenDictionary:   Count={zLinq.Count}, a={zLinq["a"]}");
var zDict = new Dictionary<string, int>();
try { foreach (var kv in dup) zDict.Add(kv.Key, kv.Value); }
catch (Exception e) { Console.WriteLine($"Dictionary.Add:       RZUCILO {e.GetType().Name}"); }

Console.WriteLine("--- 5. Pusty span ---");
var pusty = FrozenDictionary.Create<string, int>(ReadOnlySpan<KeyValuePair<string, int>>.Empty);
Console.WriteLine($"Count={pusty.Count}, ReferenceEquals(Empty)={ReferenceEquals(pusty, FrozenDictionary<string, int>.Empty)}");

Console.WriteLine("--- 6. Dla porownania: FrozenSet.Create(ReadOnlySpan<T>) - istnieje juz na net9.0, to NIE nowosc ---");
var zbior = FrozenSet.Create<string>(["admin", "root", "admin"]);
Console.WriteLine($"Count={zbior.Count}, Contains(root)={zbior.Contains("root")}");
var zbiorCi = FrozenSet.Create<string>(StringComparer.OrdinalIgnoreCase, ["Admin", "ROOT"]);
Console.WriteLine($"ci Contains(admin)={zbiorCi.Contains("admin")}");

Console.WriteLine("--- 7. Alokacje: Create(span) vs ToFrozenDictionary(IEnumerable) vs przez Dictionary ---");
var dane = new KeyValuePair<int, int>[100_000];
for (int i = 0; i < dane.Length; i++) dane[i] = new(i * 7, i);

// rozgrzewka
FrozenDictionary.Create<int, int>(dane.AsSpan());
dane.ToFrozenDictionary();
new Dictionary<int, int>(dane).ToFrozenDictionary();

foreach (var (nazwa, akcja) in new (string, Func<object>)[]
{
    ("Create(span)", () => FrozenDictionary.Create<int, int>(dane.AsSpan())),
    ("ToFrozenDictionary(array)", () => dane.ToFrozenDictionary()),
    ("new Dictionary + ToFrozen", () => new Dictionary<int, int>(dane).ToFrozenDictionary()),
})
{
    GC.Collect();
    long przed = GC.GetAllocatedBytesForCurrentThread();
    var wynik = akcja();
    long po = GC.GetAllocatedBytesForCurrentThread();
    Console.WriteLine($"{nazwa,-28} {(po - przed) / 1024,8} KB  (wynik: {wynik.GetType().Name})");
}
