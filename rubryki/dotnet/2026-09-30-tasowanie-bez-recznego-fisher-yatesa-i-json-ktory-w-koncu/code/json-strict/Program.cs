// JsonSerializerOptions.Strict / JsonDocumentOptions.AllowDuplicateProperties - nowosc
// System.Text.Json w .NET 10. Potwierdzone empirycznie w tej sesji: na SDK 9.0.316
// (net9.0) `JsonSerializerOptions.Strict` daje CS0117 - patrz ../compat-check.

using System.Text.Json;
using System.Text.Json.Serialization;

const string dupJson = """{"a":1,"a":2}""";
const string unknownJson = """{"a":1,"unknown":123}""";

Console.WriteLine("--- 1. Domyslne zachowanie: duplikat klucza JSON jest CICHO tolerowany ---");
using (var doc = JsonDocument.Parse(dupJson))
{
    Console.WriteLine($"JSON wejsciowy: {dupJson}");
    Console.WriteLine($"JsonDocument.Parse (domyslne opcje) - bez wyjatku, GetProperty(\"a\") = {doc.RootElement.GetProperty("a").GetInt32()} (ostatnia wartosc wygrywa)");
}
var lenient = JsonSerializer.Deserialize<Rekord>(dupJson);
Console.WriteLine($"JsonSerializer.Deserialize<Rekord> (domyslne opcje) - bez wyjatku, A = {lenient!.A}");

Console.WriteLine();
Console.WriteLine("--- 2. JsonDocumentOptions.AllowDuplicateProperties = false: jawne odrzucenie duplikatu ---");
try
{
    var strictDocOpts = new JsonDocumentOptions { AllowDuplicateProperties = false };
    using var doc = JsonDocument.Parse(dupJson, strictDocOpts);
    Console.WriteLine("brak wyjatku (nieoczekiwane)");
}
catch (JsonException ex)
{
    Console.WriteLine($"JsonDocument.Parse (AllowDuplicateProperties=false) rzucil: {ex.Message}");
}

Console.WriteLine();
Console.WriteLine("--- 3. JsonSerializerOptions.Strict: nowy gotowy preset (duplikaty + nieznane wlasciwosci) ---");
var strictOpts = new JsonSerializerOptions(JsonSerializerOptions.Strict);
try
{
    JsonSerializer.Deserialize<Rekord>(dupJson, strictOpts);
    Console.WriteLine("brak wyjatku (nieoczekiwane)");
}
catch (JsonException ex)
{
    Console.WriteLine($"Deserialize<Rekord>(dupJson, Strict) rzucil: {ex.Message}");
}

try
{
    JsonSerializer.Deserialize<Rekord>(unknownJson, strictOpts);
    Console.WriteLine("brak wyjatku (nieoczekiwane)");
}
catch (JsonException ex)
{
    Console.WriteLine($"Deserialize<Rekord>(unknownJson, Strict) rzucil: {ex.Message}");
}

var lenientOnUnknown = JsonSerializer.Deserialize<Rekord>(unknownJson);
Console.WriteLine($"Dla porownania - domyslne opcje na tym samym JSON z nieznana wlasciwoscia: bez wyjatku, A = {lenientOnUnknown!.A}");

Console.WriteLine();
Console.WriteLine("--- 4. Strict jako JsonSerializerDefaults (do wspolnej konfiguracji np. w ASP.NET Core) ---");
var strictViaDefaults = new JsonSerializerOptions(JsonSerializerDefaults.Strict);
Console.WriteLine($"JsonSerializerOptions z JsonSerializerDefaults.Strict utworzone: {strictViaDefaults is not null}");

class Rekord
{
    [JsonPropertyName("a")]
    public int A { get; set; }
}
