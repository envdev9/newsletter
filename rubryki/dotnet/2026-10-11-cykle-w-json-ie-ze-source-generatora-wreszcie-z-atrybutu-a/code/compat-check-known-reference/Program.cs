using System.Text.Json.Serialization;

// Na net9.0 atrybut [JsonSourceGenerationOptions] nie ma wlasciwosci ReferenceHandler
// ani typu JsonKnownReferenceHandler - kompilacja ma sie nie udac.
[JsonSourceGenerationOptions(ReferenceHandler = JsonKnownReferenceHandler.Preserve)]
[JsonSerializable(typeof(Wezel))]
public partial class Ctx : JsonSerializerContext { }

public class Wezel
{
    public Wezel? Nastepny { get; set; }
}

public static class Program
{
    public static void Main() => Console.WriteLine(Ctx.Default.Options.ReferenceHandler);
}
