using System.Diagnostics;
using System.Diagnostics.Metrics;

const string SchemaUrl = "https://opentelemetry.io/schemas/1.27.0";

// ---------------------------------------------------------------- 1
Console.WriteLine("--- 1. ActivitySourceOptions: wersja, tagi i TelemetrySchemaUrl w jednym obiekcie ---");
var opcje = new ActivitySourceOptions("Sklep.Zamowienia")
{
    Version = "2.3.1",
    TelemetrySchemaUrl = SchemaUrl,
    Tags = new KeyValuePair<string, object?>[]
    {
        new("zespol", "platforma"),
        new("srodowisko", "demo"),
    },
};
using var zrodlo = new ActivitySource(opcje);
Console.WriteLine($"Name={zrodlo.Name} Version={zrodlo.Version}");
Console.WriteLine($"TelemetrySchemaUrl={zrodlo.TelemetrySchemaUrl}");
Console.WriteLine($"Tags={string.Join(", ", zrodlo.Tags!.Select(t => $"{t.Key}={t.Value}"))}");

// ---------------------------------------------------------------- 2
Console.WriteLine("--- 2. Listener widzi te metadane w ShouldListenTo ---");
using var listener = new ActivityListener
{
    ShouldListenTo = s =>
    {
        Console.WriteLine($"ShouldListenTo({s.Name}): schema={s.TelemetrySchemaUrl ?? "(null)"}, tagi={s.Tags?.Count() ?? 0}");
        return s.Name == "Sklep.Zamowienia";
    },
    Sample = (ref ActivityCreationOptions<ActivityContext> _) => ActivitySamplingResult.AllDataAndRecorded,
    ActivityStopped = a => Console.WriteLine($"  [stopped] {a.OperationName}, Source.TelemetrySchemaUrl={a.Source.TelemetrySchemaUrl}"),
};
ActivitySource.AddActivityListener(listener);
using (var a = zrodlo.StartActivity("PrzyjmijZamowienie")) { }

// ---------------------------------------------------------------- 3
Console.WriteLine("--- 3. Stary konstruktor (name, version) nie ma jak podac schematu ---");
using var stary = new ActivitySource("Sklep.Stary", "1.0.0");
Console.WriteLine($"stary: Version={stary.Version}, TelemetrySchemaUrl={stary.TelemetrySchemaUrl ?? "(null)"}, Tags={(stary.Tags is null ? "(null)" : stary.Tags.Count().ToString())}");

// ---------------------------------------------------------------- 4
Console.WriteLine("--- 4. Haczyki ---");
try { _ = new ActivitySourceOptions(null!); }
catch (Exception e) { Console.WriteLine($"Name=null: RZUCILO {e.GetType().Name}"); }

var pusta = new ActivitySourceOptions("x");
Console.WriteLine($"domyslnie: Version={pusta.Version ?? "(null)"}, TelemetrySchemaUrl={pusta.TelemetrySchemaUrl ?? "(null)"}, Tags={(pusta.Tags is null ? "(null)" : "niepuste")}");

// Czy opcje sa kopiowane przy tworzeniu zrodla? Mutacja po konstrukcji:
var op = new ActivitySourceOptions("Sklep.Mutacja") { TelemetrySchemaUrl = "https://example.invalid/v1" };
using var m = new ActivitySource(op);
op.TelemetrySchemaUrl = "https://example.invalid/v2";
Console.WriteLine($"po mutacji opcji: zrodlo.TelemetrySchemaUrl={m.TelemetrySchemaUrl}");

// Walidacja formatu URL? (bezsensowny string)
using var zly = new ActivitySource(new ActivitySourceOptions("Sklep.Zly") { TelemetrySchemaUrl = "to nie jest url" });
Console.WriteLine($"niepoprawny URL przyjety bez walidacji: '{zly.TelemetrySchemaUrl}'");

// Czy Tags sa liczone w tożsamości zrodla (dwa zrodla o tej samej nazwie/wersji)?
using var d1 = new ActivitySource(new ActivitySourceOptions("Sklep.Dup") { Version = "1" });
using var d2 = new ActivitySource(new ActivitySourceOptions("Sklep.Dup") { Version = "1", TelemetrySchemaUrl = SchemaUrl });
Console.WriteLine($"dwa zrodla o tej samej nazwie i wersji: d1.schema={d1.TelemetrySchemaUrl ?? "(null)"}, d2.schema={d2.TelemetrySchemaUrl}");

// ---------------------------------------------------------------- 5
Console.WriteLine("--- 5. Porownanie: Meter ma analogiczne MeterOptions.TelemetrySchemaUrl ---");
using var meter = new Meter(new MeterOptions("Sklep.Metryki") { Version = "1.0", TelemetrySchemaUrl = SchemaUrl });
Console.WriteLine($"Meter.TelemetrySchemaUrl={meter.TelemetrySchemaUrl}");
