using System.Diagnostics;
using System.Diagnostics.Metrics;

var builder = WebApplication.CreateBuilder(args);
builder.AddServiceDefaults();

// "http://catalog" - to NIE jest DNS. Nazwa "catalog" to nazwa zasobu z AppHost;
// handler service discovery (z AddServiceDefaults) podmieni ją na realny adres:port.
builder.Services.AddHttpClient<CatalogClient>(c => c.BaseAddress = new Uri("http://catalog"));

var app = builder.Build();
app.MapDefaultEndpoints();

app.MapGet("/quote/{sku}", async (string sku, int? qty, CatalogClient catalog, CancellationToken ct) =>
{
    var quantity = qty ?? 1;
    using var activity = StoreTelemetry.Source.StartActivity("store.quote");
    activity?.SetTag("store.sku", sku);
    activity?.SetTag("store.qty", quantity);

    var product = await catalog.GetAsync(sku, ct);
    if (product is null)
    {
        StoreTelemetry.Quotes.Add(1, new KeyValuePair<string, object?>("outcome", "unknown_sku"));
        return Results.NotFound(new { error = $"Katalog nie zna SKU {sku}" });
    }

    var net = product.Price * quantity;
    var gross = Math.Round(net * 1.23m, 2); // VAT 23%
    StoreTelemetry.Quotes.Add(1, new KeyValuePair<string, object?>("outcome", "ok"));
    StoreTelemetry.QuoteValue.Record((double)gross);

    return Results.Ok(new
    {
        product.Sku, product.Name, quantity, net, gross,
        storeTraceId = Activity.Current?.TraceId.ToString(),
        catalogTraceId = product.TraceId, // ten sam trace id = propagacja W3C przez HttpClient
    });
});

// Pokazuje, co Aspire wstrzyknęło do konfiguracji przez WithReference(catalog).
app.MapGet("/discovery", (IConfiguration cfg) => new
{
    catalogHttp = cfg["services:catalog:http:0"],
    catalogHttps = cfg["services:catalog:https:0"],
    otlpEndpoint = cfg["OTEL_EXPORTER_OTLP_ENDPOINT"] is not null,
    serviceName = cfg["OTEL_SERVICE_NAME"],
});

app.Run();

static class StoreTelemetry
{
    public static readonly ActivitySource Source = new("Store.Quotes");
    public static readonly Meter Meter = new("Store.Quotes");
    public static readonly Counter<long> Quotes = Meter.CreateCounter<long>("store.quotes", "{quote}", "Wyceny wg wyniku");
    public static readonly Histogram<double> QuoteValue = Meter.CreateHistogram<double>("store.quote.value", "PLN", "Wartość brutto wyceny");
}

record CatalogProduct(string Sku, string Name, decimal Price, string? TraceId);

sealed class CatalogClient(HttpClient http)
{
    public async Task<CatalogProduct?> GetAsync(string sku, CancellationToken ct)
    {
        var response = await http.GetAsync($"/products/{Uri.EscapeDataString(sku)}", ct);
        if (response.StatusCode == System.Net.HttpStatusCode.NotFound) return null;
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<CatalogProduct>(ct);
    }
}
