using System.Text.Json;
using System.Text.Json.Serialization;

// Graf z cyklem: Pracownik -> Szef -> Podwladni -> Pracownik ...
var szef = new Pracownik { Imie = "Anna" };
var jan = new Pracownik { Imie = "Jan", Szef = szef };
var ewa = new Pracownik { Imie = "Ewa", Szef = szef };
szef.Podwladni.Add(jan);
szef.Podwladni.Add(ewa);

Console.WriteLine("--- 1. Co kontekst faktycznie ustawil w Options.ReferenceHandler ---");
Console.WriteLine($"Bez atrybutu:        {Opis(BezRef.Default.Options.ReferenceHandler)}");
Console.WriteLine($"Preserve:            {Opis(PreserveCtx.Default.Options.ReferenceHandler)}");
Console.WriteLine($"IgnoreCycles:        {Opis(IgnoreCtx.Default.Options.ReferenceHandler)}");
Console.WriteLine($"Unspecified (jawne): {Opis(UnspecCtx.Default.Options.ReferenceHandler)}");

Console.WriteLine("--- 2. Bez obslugi referencji: cykl ---");
Sprobuj(() => JsonSerializer.Serialize(jan, BezRef.Default.Pracownik));

Console.WriteLine("--- 3. Preserve (z atrybutu source-gen): $id / $ref ---");
var json = JsonSerializer.Serialize(jan, PreserveCtx.Default.Pracownik);
Console.WriteLine(json);
var wroc = JsonSerializer.Deserialize(json, PreserveCtx.Default.Pracownik)!;
Console.WriteLine($"po deserializacji: wroc.Szef.Podwladni[0] == wroc ? {ReferenceEquals(wroc.Szef!.Podwladni[0], wroc)}");

Console.WriteLine("--- 4. IgnoreCycles: cykl zamieniony na null ---");
Console.WriteLine(JsonSerializer.Serialize(jan, IgnoreCtx.Default.Pracownik));

Console.WriteLine("--- 5. Unspecified jawnie = brak obslugi ---");
Sprobuj(() => JsonSerializer.Serialize(jan, UnspecCtx.Default.Pracownik));

Console.WriteLine("--- 6. Deserializacja Preserve z kontekstu bez Preserve ---");
Sprobuj(() => JsonSerializer.Deserialize(json, BezRef.Default.Pracownik));

Console.WriteLine("--- 7. Stary sposob (dziala tez na net9.0): opcje przekazane do konstruktora kontekstu ---");
var staryCtx = new BezRef(new JsonSerializerOptions { ReferenceHandler = ReferenceHandler.Preserve });
Console.WriteLine(JsonSerializer.Serialize(jan, staryCtx.Pracownik).Substring(0, 60) + "...");

static string Opis(ReferenceHandler? h) => h is null ? "null" : h.GetType().Name;

static void Sprobuj(Func<object?> f)
{
    try { Console.WriteLine("OK: " + f()); }
    catch (Exception e)
    {
        var msg = e.Message;
        Console.WriteLine($"RZUCILO {e.GetType().Name}: {(msg.Length > 110 ? msg[..110] + "..." : msg)}");
    }
}

public class Pracownik
{
    public string Imie { get; set; } = "";
    public Pracownik? Szef { get; set; }
    public List<Pracownik> Podwladni { get; set; } = new();
}

[JsonSerializable(typeof(Pracownik))]
public partial class BezRef : JsonSerializerContext { }

[JsonSourceGenerationOptions(ReferenceHandler = JsonKnownReferenceHandler.Preserve)]
[JsonSerializable(typeof(Pracownik))]
public partial class PreserveCtx : JsonSerializerContext { }

[JsonSourceGenerationOptions(ReferenceHandler = JsonKnownReferenceHandler.IgnoreCycles)]
[JsonSerializable(typeof(Pracownik))]
public partial class IgnoreCtx : JsonSerializerContext { }

[JsonSourceGenerationOptions(ReferenceHandler = JsonKnownReferenceHandler.Unspecified)]
[JsonSerializable(typeof(Pracownik))]
public partial class UnspecCtx : JsonSerializerContext { }
