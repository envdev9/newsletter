using System.Text.Json.Nodes;

// .NET 10: JsonObject.TryAdd(key, value, out int index) i
//          JsonObject.TryGetPropertyValue(key, out JsonNode? value, out int index).
// (GetAt/SetAt/IndexOf/Insert/RemoveAt - dostep po indeksie - sa starsze; nowy jest "out int".)

static void Try(string label, Action a)
{
    try { a(); Console.WriteLine($"{label}: NIE rzucilo"); }
    catch (Exception e) { Console.WriteLine($"{label}: RZUCILO {e.GetType().Name}: \"{e.Message}\""); }
}

Console.WriteLine("--- 1. Problem: 'dodaj jesli brak, a potem znajdz pozycje' = 2-3 wyszukiwania ---");
var stary = new JsonObject { ["id"] = 1, ["name"] = "Ala" };
bool juzJest = stary.ContainsKey("role");          // wyszukiwanie 1
if (!juzJest) stary.Add("role", "admin");          // wyszukiwanie 2 (Add sprawdza duplikat)
int pozycja = stary.IndexOf("role");               // wyszukiwanie 3
Console.WriteLine($"{stary.ToJsonString()}  pozycja 'role' = {pozycja}");

Console.WriteLine();
Console.WriteLine("--- 2. .NET 10: TryAdd(..., out int index) - jedno wywolanie ---");
var o = new JsonObject { ["id"] = 1, ["name"] = "Ala" };
bool dodano = o.TryAdd("role", "admin", out int idx);
Console.WriteLine($"TryAdd(role)  -> {dodano}, index = {idx}, JSON: {o.ToJsonString()}");
bool dodano2 = o.TryAdd("role", "guest", out int idx2);
Console.WriteLine($"TryAdd(role)  -> {dodano2}, index = {idx2} (indeks ISTNIEJACEJ wlasciwosci), JSON: {o.ToJsonString()}");

Console.WriteLine();
Console.WriteLine("--- 3. .NET 10: TryGetPropertyValue(..., out value, out int index) ---");
bool jest = o.TryGetPropertyValue("name", out var wartosc, out int idxName);
Console.WriteLine($"name  -> {jest}, value = {wartosc}, index = {idxName}");
bool brak = o.TryGetPropertyValue("nope", out var wartosc2, out int idxBrak);
Console.WriteLine($"nope  -> {brak}, value = {(wartosc2 is null ? "null" : wartosc2)}, index = {idxBrak}");

Console.WriteLine();
Console.WriteLine("--- 4. Praktyka: upsert z zachowaniem kolejnosci + wstawienie 'za' istniejacym kluczem ---");
var cfg = JsonNode.Parse("""{"host":"localhost","port":5432,"tls":false}""")!.AsObject();
// upsert: jesli klucz jest - podmien wartosc NA TEJ SAMEJ POZYCJI; jesli brak - dopisz na koncu
foreach (var (k, v) in new[] { ("port", (JsonNode)6432), ("timeout", 30) })
{
    if (cfg.TryAdd(k, v, out int i)) Console.WriteLine($"  dopisano '{k}' na pozycji {i}");
    else { cfg.SetAt(i, v); Console.WriteLine($"  podmieniono '{k}' na pozycji {i}"); }
}
// wstaw "user" tuz za "host" - pozycje bierzemy z jednego wywolania
if (cfg.TryGetPropertyValue("host", out _, out int hostIdx)) cfg.Insert(hostIdx + 1, "user", "app");
Console.WriteLine($"  wynik: {cfg.ToJsonString()}");

Console.WriteLine();
Console.WriteLine("--- 5. HACZYK A: indeks to MIGAWKA - Insert/RemoveAt przesuwa pozycje ---");
var p = new JsonObject { ["a"] = 1, ["b"] = 2, ["c"] = 3 };
p.TryGetPropertyValue("c", out _, out int idxC);
p.RemoveAt(0);
Console.WriteLine($"indeks 'c' sprzed RemoveAt(0): {idxC}, aktualny IndexOf(\"c\"): {p.IndexOf("c")}");
Try($"GetAt({idxC}) po usunieciu", () => Console.WriteLine($"   -> {p.GetAt(idxC)}"));

Console.WriteLine();
Console.WriteLine("--- 6. HACZYK B: wielkosc liter (PropertyNameCaseInsensitive) ---");
var ci = new JsonObject(new JsonNodeOptions { PropertyNameCaseInsensitive = true }) { ["Name"] = "Ala" };
bool trafilo = ci.TryGetPropertyValue("NAME", out var cv, out int cidx);
Console.WriteLine($"TryGetPropertyValue(\"NAME\") -> {trafilo}, value = {cv}, index = {cidx}");
bool dodanoCi = ci.TryAdd("NAME", "Ola", out int cidx2);
Console.WriteLine($"TryAdd(\"NAME\") -> {dodanoCi}, index = {cidx2}, JSON: {ci.ToJsonString()}");

Console.WriteLine();
Console.WriteLine("--- 7. HACZYK C: wezel z rodzicem - czy TryAdd zwroci false, czy rzuci? ---");
var rodzic = new JsonObject { ["x"] = 1 };
var dziecko = new JsonObject { ["v"] = 1 };
var zajeta = new JsonObject { ["dziecko"] = dziecko }; // 'dziecko' ma juz rodzica
Try("TryAdd nowego klucza z wezlem majacym rodzica", () => rodzic.TryAdd("nowy", dziecko, out _));
Try("TryAdd ISTNIEJACEGO klucza z wezlem majacym rodzica", () => rodzic.TryAdd("x", dziecko, out _));
Console.WriteLine($"   zajeta: {zajeta.ToJsonString()}, rodzic: {rodzic.ToJsonString()}");
