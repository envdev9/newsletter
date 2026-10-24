using System.Diagnostics;
using System.Net;
using System.Text.Json;
using Aspire.Hosting;
using Aspire.Hosting.ApplicationModel;
using Aspire.Hosting.Testing;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

// Weryfikacja end-to-end BEZ curl-a i bez dashboardu: podnosimy cały AppHost w procesie
// (DistributedApplicationTestingBuilder), czekamy na zdrowie zasobów i wołamy API HttpClientem.
var timeout = TimeSpan.FromSeconds(90);
using var cts = new CancellationTokenSource(timeout);
var ct = cts.Token;
var failures = 0;

void Check(string name, bool ok, string detail = "")
{
    Console.WriteLine($"[{(ok ? "PASS" : "FAIL")}] {name} {detail}".TrimEnd());
    if (!ok) failures++;
}

var appHost = await DistributedApplicationTestingBuilder.CreateAsync<Projects.AppHost>(ct);

// Wyciszamy szum (logi requestów każdego serwisu), zostawiamy tylko nasze PASS/FAIL.
appHost.Services.AddLogging(logging => logging
    .SetMinimumLevel(LogLevel.Warning)
    .AddFilter("Microsoft", LogLevel.Warning)
    .AddFilter("System.Net.Http", LogLevel.Warning)
    .AddFilter("Aspire", LogLevel.Warning)
    .AddFilter("AppHost.Resources", LogLevel.Warning));
await using var app = await appHost.BuildAsync(ct);

var clock = Stopwatch.StartNew();
await app.StartAsync(ct);

// Kolejność jest kluczowa: store ma WaitFor(catalog), a catalog jest "healthy" po ~3 s rozgrzewki.
await app.ResourceNotifications.WaitForResourceHealthyAsync("catalog", ct);
var catalogReadyAt = clock.Elapsed;
await app.ResourceNotifications.WaitForResourceHealthyAsync("store", ct);
var storeReadyAt = clock.Elapsed;
Console.WriteLine($"catalog healthy po {catalogReadyAt.TotalSeconds:F1}s, store healthy po {storeReadyAt.TotalSeconds:F1}s");
Check("catalog zdrowy dopiero po rozgrzewce (>= 3 s)", catalogReadyAt >= TimeSpan.FromSeconds(3));

using var store = app.CreateHttpClient("store");
using var catalog = app.CreateHttpClient("catalog");

// 1. Health checks
var health = await catalog.GetAsync("/health", ct);
Check("catalog /health = 200", health.StatusCode == HttpStatusCode.OK, $"(body: {await health.Content.ReadAsStringAsync(ct)})");

// 2. Service discovery: store -> http://catalog
var quoteJson = await store.GetStringAsync("/quote/KB-001?qty=3", ct);
Console.WriteLine($"GET store /quote/KB-001?qty=3 -> {quoteJson}");
var quote = JsonDocument.Parse(quoteJson).RootElement;
Check("wycena: 3 x 349.00 netto = 1047.00", quote.GetProperty("net").GetDecimal() == 1047.00m);
Check("wycena: brutto (VAT 23%) = 1287.81", quote.GetProperty("gross").GetDecimal() == 1287.81m);

// 3. Propagacja trace'a store -> catalog (ten sam TraceId po obu stronach)
var storeTrace = quote.GetProperty("storeTraceId").GetString();
var catalogTrace = quote.GetProperty("catalogTraceId").GetString();
Check("ten sam TraceId w store i catalog", !string.IsNullOrEmpty(storeTrace) && storeTrace == catalogTrace, $"({storeTrace})");

// 4. Nieznany SKU -> 404 z catalog przekłada się na 404 ze store
var missing = await store.GetAsync("/quote/NOPE-999", ct);
Check("nieznany SKU -> 404", missing.StatusCode == HttpStatusCode.NotFound);

// 5. Co Aspire wstrzyknęło do store
var discoveryJson = await store.GetStringAsync("/discovery", ct);
Console.WriteLine($"GET store /discovery -> {discoveryJson}");
var discovery = JsonDocument.Parse(discoveryJson).RootElement;
Check("services:catalog:http:0 ustawione przez WithReference",
    discovery.GetProperty("catalogHttp").GetString()?.StartsWith("http://localhost:") == true);
Check("OTLP endpoint wstrzyknięty", discovery.GetProperty("otlpEndpoint").GetBoolean());

// 6. Własny Meter (catalog.lookups): 1 trafienie (KB-001) i 1 pudło (NOPE-999)
var tallyJson = await catalog.GetStringAsync("/debug/lookups", ct);
Console.WriteLine($"GET catalog /debug/lookups -> {tallyJson}");
var tally = JsonDocument.Parse(tallyJson).RootElement;
Check("Meter: catalog.lookups{found=true} == 1", tally.GetProperty("catalog.lookups{found=true}").GetInt64() == 1);
Check("Meter: catalog.lookups{found=false} == 1", tally.GetProperty("catalog.lookups{found=false}").GetInt64() == 1);

Console.WriteLine(failures == 0 ? "WSZYSTKO OK" : $"BLEDY: {failures}");
return failures == 0 ? 0 : 1;
