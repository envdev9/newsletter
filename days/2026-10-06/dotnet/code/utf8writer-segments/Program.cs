using System.Buffers;
using System.Text;
using System.Text.Json;

// .NET 10: Utf8JsonWriter.WriteStringValueSegment (char / byte) i WriteBase64StringSegment.

static string Json(Action<Utf8JsonWriter> write)
{
    var ms = new MemoryStream();
    using (var w = new Utf8JsonWriter(ms)) write(w);
    return Encoding.UTF8.GetString(ms.ToArray());
}

static void Try(string label, Action a)
{
    try { a(); Console.WriteLine($"{label}: NIE rzucilo"); }
    catch (Exception e) { Console.WriteLine($"{label}: RZUCILO {e.GetType().Name}: \"{e.Message}\""); }
}

Console.WriteLine("--- 1. Segmenty daja ten sam JSON co jedno WriteStringValue (escaping dziala ponad granicami) ---");
string tekst = "Zazolc \"gesla\" jazn\n\tend";
string jednym = Json(w => w.WriteStringValue(tekst));
string kawalkami = Json(w =>
{
    w.WriteStringValueSegment(tekst.AsSpan(0, 8), isFinalSegment: false);
    w.WriteStringValueSegment(tekst.AsSpan(8, 9), isFinalSegment: false);
    w.WriteStringValueSegment(tekst.AsSpan(17), isFinalSegment: true);
});
Console.WriteLine($"jednym:    {jednym}");
Console.WriteLine($"kawalkami: {kawalkami}");
Console.WriteLine($"rowne: {jednym == kawalkami}");

Console.WriteLine();
Console.WriteLine("--- 2. Base64: kawalki NIE musza byc wielokrotnoscia 3 bajtow ---");
byte[] dane = new byte[10_000];
Random.Shared.NextBytes(dane);
string oczekiwane = "\"" + Convert.ToBase64String(dane) + "\"";
string b64 = Json(w =>
{
    // 1000 bajtow (nie wielokrotnosc 3) w kazdym kawalku
    for (int i = 0; i < dane.Length; i += 1000)
        w.WriteBase64StringSegment(dane.AsSpan(i, 1000), isFinalSegment: i + 1000 >= dane.Length);
});
Console.WriteLine($"zgodne z Convert.ToBase64String: {b64 == oczekiwane} (dlugosc {b64.Length})");

Console.WriteLine();
Console.WriteLine("--- 3. Pomiar: 64 MB tekstu do strumienia - jeden string vs strumieniowo w kawalkach 8 KB ---");
const int Chunk = 8 * 1024;
const int Total = 64 * 1024 * 1024;
char[] bufor = new char[Chunk];
Array.Fill(bufor, 'x');
bufor[10] = '"'; // wymusza escaping w kazdym kawalku

// Podejscie A: caly tekst w jednym stringu
GC.Collect(); GC.WaitForPendingFinalizers();
long a0 = GC.GetAllocatedBytesForCurrentThread();
{
    string caly = string.Create(Total, bufor, (span, b) =>
    {
        for (int i = 0; i < span.Length; i += Chunk) b.AsSpan().CopyTo(span.Slice(i));
    });
    long a1 = GC.GetAllocatedBytesForCurrentThread();
    using var w = new Utf8JsonWriter(Stream.Null);
    w.WriteStringValue(caly);
    w.Flush();
    long a2 = GC.GetAllocatedBytesForCurrentThread();
    Console.WriteLine($"A) caly string: alokacje na zbudowanie stringa {(a1 - a0) / 1024 / 1024} MB, na sam zapis {(a2 - a1) / 1024 / 1024} MB");
}

// Podejscie B: kawalki BEZ Flush - writer buforuje cale wyjscie w pamieci
long b0 = GC.GetAllocatedBytesForCurrentThread();
{
    using var w = new Utf8JsonWriter(Stream.Null);
    for (int i = 0; i < Total; i += Chunk)
        w.WriteStringValueSegment(bufor, isFinalSegment: i + Chunk >= Total);
    w.Flush();
}
long b1 = GC.GetAllocatedBytesForCurrentThread();
Console.WriteLine($"B) segmenty 8 KB, BEZ Flush miedzy kawalkami: alokacje lacznie {(b1 - b0) / 1024 / 1024} MB");

// Podejscie C: kawalki + Flush po kazdym - prawdziwy streaming
long c0 = GC.GetAllocatedBytesForCurrentThread();
{
    using var w = new Utf8JsonWriter(Stream.Null);
    for (int i = 0; i < Total; i += Chunk)
    {
        w.WriteStringValueSegment(bufor, isFinalSegment: i + Chunk >= Total);
        w.Flush();
    }
}
long c1 = GC.GetAllocatedBytesForCurrentThread();
Console.WriteLine($"C) segmenty 8 KB, Flush po kazdym: alokacje lacznie {(c1 - c0) / 1024} KB");

Console.WriteLine();
Console.WriteLine("--- 4. HACZYK A: nie mozna mieszac kodowan w jednym stringu (UTF-16 vs UTF-8) ---");
Try("char potem byte", () => Json(w =>
{
    w.WriteStringValueSegment("abc".AsSpan(), false);
    w.WriteStringValueSegment("def"u8, true);
}));

Console.WriteLine();
Console.WriteLine("--- 5. HACZYK B: cięcie wielobajtowego znaku miedzy kawalkami ---");
byte[] zUtf8 = Encoding.UTF8.GetBytes("zażółć"); // 'ż','ó','ł','ć' = 2 bajty kazdy
Try("UTF-8: ciecie w srodku 'ż' (po 3 bajtach)", () => Console.WriteLine("   -> " + Json(w =>
{
    w.WriteStringValueSegment(zUtf8.AsSpan(0, 3), false);
    w.WriteStringValueSegment(zUtf8.AsSpan(3), true);
})));
string emoji = "a\U0001F600b"; // para surrogatow
Try("UTF-16: ciecie pary surrogatow", () => Console.WriteLine("   -> " + Json(w =>
{
    w.WriteStringValueSegment(emoji.AsSpan(0, 2), false); // 'a' + wysoki surrogat
    w.WriteStringValueSegment(emoji.AsSpan(2), true);     // niski surrogat + 'b'
})));
Try("UTF-16: samotny wysoki surrogat jako OSTATNI kawalek", () => Console.WriteLine("   -> " + Json(w =>
{
    w.WriteStringValueSegment(emoji.AsSpan(0, 2), true);
})));

Console.WriteLine();
Console.WriteLine("--- 6. HACZYK C: niezakonczony string (brak isFinalSegment: true) ---");
Try("zamkniecie obiektu w trakcie stringa", () => Json(w =>
{
    w.WriteStartObject();
    w.WritePropertyName("k");
    w.WriteStringValueSegment("abc".AsSpan(), false);
    w.WriteEndObject();
}));
Try("Dispose bez finalnego kawalka", () => Console.WriteLine("   -> " + Json(w =>
{
    w.WriteStringValueSegment("abc".AsSpan(), false);
})));
