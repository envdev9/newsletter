using System.Collections.Concurrent;
using System.Diagnostics;
using System.Diagnostics.Metrics;
using Microsoft.Extensions.Diagnostics.HealthChecks;

var builder = WebApplication.CreateBuilder(args);
builder.AddServiceDefaults();

// "Rozgrzewka": przez pierwsze ~3 s serwis żyje, ale NIE jest gotowy.
// /health zwraca 503 - i właśnie na tym opiera się WaitFor w AppHost.
builder.Services.AddSingleton<WarmupState>();
builder.Services.AddHostedService<WarmupService>();
builder.Services.AddHealthChecks().AddCheck<WarmupHealthCheck>("warmup");

var app = builder.Build();
app.MapDefaultEndpoints();

var tally = new LookupTally(); // MeterListener w procesie - tylko do podglądu w /debug/lookups

Product[] products =
[
    new("KB-001", "Klawiatura mechaniczna", 349.00m),
    new("MS-002", "Mysz bezprzewodowa", 129.90m),
    new("HD-003", "Słuchawki", 219.50m),
];

app.MapGet("/products/{sku}", (string sku) =>
{
    // Własny span: pojawi się w trace jako dziecko requestu HTTP.
    using var activity = CatalogTelemetry.Source.StartActivity("catalog.lookup");
    activity?.SetTag("catalog.sku", sku);

    var product = products.FirstOrDefault(p => p.Sku.Equals(sku, StringComparison.OrdinalIgnoreCase));
    CatalogTelemetry.Lookups.Add(1, new KeyValuePair<string, object?>("found", product is not null));

    if (product is null)
    {
        activity?.SetStatus(ActivityStatusCode.Error, "unknown sku");
        return Results.NotFound(new { error = $"Nieznany SKU: {sku}" });
    }

    // traceId zwracamy, żeby dało się sprawdzić propagację trace'a między serwisami.
    return Results.Ok(new { product.Sku, product.Name, product.Price, traceId = Activity.Current?.TraceId.ToString() });
});

app.MapGet("/debug/lookups", () => tally.Snapshot());

app.Run();

record Product(string Sku, string Name, decimal Price);

static class CatalogTelemetry
{
    // Nazwy zaczynają się od "Store." - łapie je wildcard z ServiceDefaults.
    public static readonly ActivitySource Source = new("Store.Catalog");
    public static readonly Meter Meter = new("Store.Catalog");
    public static readonly Counter<long> Lookups =
        Meter.CreateCounter<long>("catalog.lookups", unit: "{lookup}", description: "Liczba wyszukań produktu");
}

// Ten sam mechanizm, którego używa OpenTelemetry SDK, tylko w miniaturze:
// nasłuchujemy własnego Metera i sumujemy pomiary per tag "found".
sealed class LookupTally
{
    private readonly ConcurrentDictionary<string, long> _counts = new();

    public LookupTally()
    {
        var listener = new MeterListener();
        listener.InstrumentPublished = (instrument, l) =>
        {
            if (instrument.Meter.Name == "Store.Catalog") l.EnableMeasurementEvents(instrument);
        };
        listener.SetMeasurementEventCallback<long>((instrument, value, tags, _) =>
        {
            foreach (var tag in tags)
                if (tag.Key == "found")
                    _counts.AddOrUpdate($"{instrument.Name}{{found={tag.Value?.ToString()?.ToLowerInvariant()}}}", value, (_, old) => old + value);
        });
        listener.Start();
    }

    public IReadOnlyDictionary<string, long> Snapshot() => new SortedDictionary<string, long>(_counts);
}

sealed class WarmupState { public volatile bool Ready; }

sealed class WarmupService(WarmupState state) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken ct)
    {
        await Task.Delay(TimeSpan.FromSeconds(3), ct);
        state.Ready = true;
    }
}

sealed class WarmupHealthCheck(WarmupState state) : IHealthCheck
{
    public Task<HealthCheckResult> CheckHealthAsync(HealthCheckContext context, CancellationToken ct = default) =>
        Task.FromResult(state.Ready ? HealthCheckResult.Healthy("warm") : HealthCheckResult.Unhealthy("warming up"));
}
