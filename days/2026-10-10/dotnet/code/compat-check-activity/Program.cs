using System.Diagnostics;

// Ten kod NIE kompiluje sie na net9.0: brak ActivitySourceOptions.
var opcje = new ActivitySourceOptions("demo")
{
    Version = "1.0.0",
    TelemetrySchemaUrl = "https://opentelemetry.io/schemas/1.27.0",
};
using var zrodlo = new ActivitySource(opcje);
Console.WriteLine(zrodlo.TelemetrySchemaUrl);
