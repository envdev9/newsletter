using System.Diagnostics;
using Aspire.Hosting;
using Aspire.Hosting.Testing;
using TUnit.Core.Interfaces;

namespace Cache.AppHostTests;

/// <summary>
/// Fixture z wydania #12, rozszerzony o INSTRUMENTACJĘ cyklu życia: każda instancja
/// ma własne Id, a globalne liczniki (statyczne - przeżywają wszystkie instancje)
/// mówią, ile AppHostów faktycznie wystartowało i ile zostało posprzątanych.
/// </summary>
public sealed class RedisAppHostFixture : IAsyncInitializer, IAsyncDisposable
{
    public static int Starts;
    public static int Disposes;
    public static string DisposeLogPath => Path.Combine(AppContext.BaseDirectory, "fixture-lifecycle.log");

    private DistributedApplication? _app;

    public string Id { get; } = Guid.NewGuid().ToString("N")[..6];

    public async Task InitializeAsync()
    {
        Interlocked.Increment(ref Starts);
        Log($"InitializeAsync fixture={Id}");

        var appHost = await DistributedApplicationTestingBuilder.CreateAsync<Projects.AppHost>(
            ["Logging:LogLevel:Default=Warning"]);
        _app = await appHost.BuildAsync();
        await _app.StartAsync();
        await _app.ResourceNotifications.WaitForResourceHealthyAsync("cache-api");
    }

    public HttpClient CreateHttpClient() => _app!.CreateHttpClient("cache-api");

    public async ValueTask DisposeAsync()
    {
        Log($"DisposeAsync START fixture={Id}");
        if (_app is not null)
        {
            await _app.StopAsync();
            await _app.DisposeAsync();
        }
        Interlocked.Increment(ref Disposes);
        Log($"DisposeAsync END fixture={Id}");
    }

    /// <summary>Nazwy kontenerów Aspire z Redisem (nazwa zaczyna się od "cache-") widoczne teraz w Dockerze.</summary>
    public static string[] RunningRedisContainers()
    {
        var psi = new ProcessStartInfo("docker", "ps --filter name=cache- --format {{.Names}}")
        {
            RedirectStandardOutput = true,
        };
        using var p = Process.Start(psi)!;
        var output = p.StandardOutput.ReadToEnd();
        p.WaitForExit();
        return output.Split('\n', StringSplitOptions.RemoveEmptyEntries);
    }

    private static void Log(string line) =>
        File.AppendAllText(DisposeLogPath, $"{DateTime.UtcNow:HH:mm:ss.fff} {line}{Environment.NewLine}");
}
