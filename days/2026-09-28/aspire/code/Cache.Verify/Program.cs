using Aspire.Hosting;
using Aspire.Hosting.Testing;
using System.Text.Json;

// Weryfikacja PRAWDZIWEGO kontenera Redis (nie atrapa): AppHost jako biblioteka
// (DistributedApplicationTestingBuilder) faktycznie startuje kontener przez Docker,
// czeka aż "cache-api" będzie Healthy (czyli Redis pod spodem musiał wstać wcześniej,
// bo WaitFor(cache) blokuje start), i sprawdza HTTP-em, że dane realnie
// przechodzą przez sieć do Redisa i z powrotem.

int failures = 0;
void Check(string name, bool ok, string? detail = null)
{
    Console.WriteLine($"[{(ok ? "PASS" : "FAIL")}] {name}{(detail is null ? "" : $" ({detail})")}");
    if (!ok) failures++;
}

using var cts = new CancellationTokenSource(TimeSpan.FromMinutes(5));
var ct = cts.Token;

Console.WriteLine("=== Start AppHost (kontener Redis przez Docker) ===");
var appHost = await DistributedApplicationTestingBuilder.CreateAsync<Projects.AppHost>(
    ["Logging:LogLevel:Default=Warning"], ct);
await using var app = await appHost.BuildAsync(ct);
await app.StartAsync(ct);

try
{
    // WaitFor(cache) w AppHost oznacza, że jeśli "cache-api" w ogóle dojdzie do
    // Healthy, to Redis pod spodem już żyje - to jest nasz dowód, że kontener wstał.
    await app.ResourceNotifications.WaitForResourceHealthyAsync("cache-api", ct);
    Console.WriteLine("cache-api = Healthy (czyli kontener redis 'cache' też musiał wystartować)");

    using var http = app.CreateHttpClient("cache-api");

    var info = await http.GetStringAsync("/cache-info", ct);
    Console.WriteLine("GET /cache-info -> " + info);
    var infoJson = JsonDocument.Parse(info).RootElement;
    Check("klient StackExchange.Redis jest połączony (IsConnected)", infoJson.GetProperty("isConnected").GetBoolean());
    Check("endpoint wygląda jak host:port kontenera (nie localhost:6379 na sztywno)",
        infoJson.GetProperty("endpoint").GetString() is { Length: > 0 } ep && ep.Contains(':'),
        infoJson.GetProperty("endpoint").GetString());
    Check("Aspire wstrzyknął connection string z hasłem (bez podawania go w kodzie)",
        infoJson.GetProperty("connectionHasPassword").GetBoolean());
    Check("Aspire wstrzyknął connection string z TLS (ssl=true)",
        infoJson.GetProperty("connectionHasSsl").GetBoolean());

    // Zapis i odczyt z prawdziwego Redisa, przez sieć, dwoma osobnymi wywołaniami HTTP.
    var key = "prasowka:test:" + Guid.NewGuid().ToString("N")[..8];
    var value = "wpis z Cache.Verify " + DateTimeOffset.UtcNow.ToString("O");

    var put = await http.PutAsync(
        $"/cache/{key}",
        new StringContent(value, System.Text.Encoding.UTF8, "text/plain"), ct);
    Check("PUT /cache/{key} -> 200", put.IsSuccessStatusCode, put.StatusCode.ToString());

    var getBody = await http.GetStringAsync($"/cache/{key}", ct);
    Console.WriteLine($"GET /cache/{key} -> " + getBody);
    var getJson = JsonDocument.Parse(getBody).RootElement;
    Check("odczytana wartość == zapisana wartość (round-trip przez realny Redis)",
        getJson.GetProperty("value").GetString() == value);

    var missing = await http.GetAsync("/cache/nieistniejacy-klucz-xyz", ct);
    Check("brakujący klucz -> 404", missing.StatusCode == System.Net.HttpStatusCode.NotFound, missing.StatusCode.ToString());
}
finally
{
    Console.WriteLine("=== Zatrzymywanie AppHost (Aspire zdejmuje kontener Redis) ===");
    await app.StopAsync(CancellationToken.None);
}

Console.WriteLine(failures == 0 ? "WSZYSTKO OK" : $"BŁĘDY: {failures}");
return failures == 0 ? 0 : 1;
