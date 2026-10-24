using Aspire.Hosting;
using Aspire.Hosting.ApplicationModel;
using Aspire.Hosting.Testing;
using Microsoft.Extensions.DependencyInjection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

// Weryfikacja bez curl i bez Dockera: AppHost jako biblioteka, parametry podawane
// jako ARGUMENTY (Parameters:nazwa=wartość) - tak samo zadziałałyby user-secrets/zmienne środowiskowe.
// Wartości poniżej to atrapy testowe, nie prawdziwe sekrety.

const string FakeKey = "test-key-12345";
const string FakePass = "p@ss-987";
int failures = 0;

void Check(string name, bool ok, string? detail = null)
{
    Console.WriteLine($"[{(ok ? "PASS" : "FAIL")}] {name}{(detail is null ? "" : $" ({detail})")}");
    if (!ok) failures++;
}

static string Sha8(string s) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(s)))[..8];

using var cts = new CancellationTokenSource(TimeSpan.FromMinutes(3));
var ct = cts.Token;

// ---------- Scenariusz A: wszystkie parametry podane ----------
Console.WriteLine("=== A: parametry podane ===");
{
    var appHost = await DistributedApplicationTestingBuilder.CreateAsync<Projects.AppHost>(
        ["Parameters:api-key=" + FakeKey, "Parameters:db-password=" + FakePass,
         "Parameters:greeting=Witaj", "Parameters:fixed-text=z konfiguracji",
         "Logging:LogLevel:Default=Warning", "Logging:LogLevel:AppHost.Resources.env-printer=Information"], ct);
    await using var app = await appHost.BuildAsync(ct);
    await app.StartAsync(ct);

    await app.ResourceNotifications.WaitForResourceHealthyAsync("config-api", ct);
    using var http = app.CreateHttpClient("config-api");
    var json = await http.GetStringAsync("/env", ct);
    Console.WriteLine("GET config-api /env -> " + json);
    var env = JsonDocument.Parse(json).RootElement;

    Check("literał: APP_MODE == demo", env.GetProperty("appMode").GetString() == "demo");
    Check("AddParameter(nazwa): GREETING == Witaj (z Parameters:greeting)",
        env.GetProperty("greeting").GetString() == "Witaj");
    Check("AddParameter(nazwa, wartość) jest STAŁE: FIXED_TEXT ignoruje konfigurację",
        env.GetProperty("fixedText").GetString() == "stała z kodu");
    Check("callback WithEnvironment(ctx): RUN_MODE == run", env.GetProperty("runMode").GetString() == "run");
    Check("sekret dotarł do procesu (długość i skrót się zgadzają)",
        env.GetProperty("apiKey").GetString() == $"len={FakeKey.Length};sha256={Sha8(FakeKey)}");
    Check("ReferenceExpression złożył connection string",
        env.GetProperty("dbConnectionPrefix").GetString() == "Host=db.local;Database=shop;"
        && env.GetProperty("dbConnectionHasPassword").GetBoolean());

    // Log procesu AddExecutable - czytamy go przez ResourceLoggerService.
    await app.ResourceNotifications.WaitForResourceAsync("env-printer", KnownResourceStates.Finished, ct);
    var logger = app.Services.GetRequiredService<ResourceLoggerService>();
    var model = app.Services.GetRequiredService<DistributedApplicationModel>();
    var printer = model.Resources.First(r => r.Name == "env-printer");
    var lines = new List<string>();
    using var logCts = CancellationTokenSource.CreateLinkedTokenSource(ct);
    logCts.CancelAfter(TimeSpan.FromSeconds(3));
    try
    {
        await foreach (var batch in logger.WatchAsync(printer).WithCancellation(logCts.Token))
            foreach (var l in batch) lines.Add(l.Content);
    }
    catch (OperationCanceledException) { }
    Console.WriteLine($"  (linii logu env-printer: {lines.Count})");
    var printed = lines.FirstOrDefault(l => l.Contains("env-printer: GREETING=") && !l.Contains("[sys]"));
    Console.WriteLine("log env-printer -> " + printed);
    Check("AddExecutable dostał GREETING i sekret (KEY_LEN)",
        printed is not null && printed.Contains("GREETING=Witaj") && printed.Contains($"KEY_LEN={FakeKey.Length}"));
}

// ---------- Scenariusz B: brak sekretu ----------
Console.WriteLine("=== B: brak Parameters:api-key ===");
{
    var appHost = await DistributedApplicationTestingBuilder.CreateAsync<Projects.AppHost>(
        ["Parameters:db-password=" + FakePass, "Logging:LogLevel:Default=Critical"], ct);
    await using var app = await appHost.BuildAsync(ct);
    var states = new List<string>();
    string? failure = null;
    try
    {
        await app.StartAsync(ct);
        using var watchCts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        watchCts.CancelAfter(TimeSpan.FromSeconds(20));
        await foreach (var ev in app.ResourceNotifications.WatchAsync(watchCts.Token))
        {
            if (ev.Resource.Name is not ("config-api" or "env-printer" or "api-key")) continue;
            var s = $"{ev.Resource.Name}={ev.Snapshot.State?.Text}";
            if (states.Count == 0 || states[^1] != s) { states.Add(s); Console.WriteLine("  stan: " + s); }
        }
    }
    catch (OperationCanceledException) { }
    catch (Exception ex) { failure = ex.GetType().Name + ": " + ex.Message; Console.WriteLine("  wyjątek: " + failure); }

    Check("brak sekretu -> config-api NIE jest Running/Healthy",
        !states.Contains("config-api=Running") && !states.Contains("config-api=Healthy"),
        string.Join(", ", states));
}

Console.WriteLine(failures == 0 ? "WSZYSTKO OK" : $"BŁĘDY: {failures}");
return failures == 0 ? 0 : 1;
