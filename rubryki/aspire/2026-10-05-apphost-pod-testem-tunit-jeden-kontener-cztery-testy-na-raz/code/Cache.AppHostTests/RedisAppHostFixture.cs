using Aspire.Hosting;
using Aspire.Hosting.Testing;
using TUnit.Core.Interfaces;

namespace Cache.AppHostTests;

/// <summary>
/// Opakowuje cykl życia PRAWDZIWEGO AppHosta (kontener Redis przez Docker) w
/// dwa interfejsy, które TUnit już znamy z wydania #3 (2026-09-26):
/// IAsyncInitializer / IAsyncDisposable. To jest dokładnie ten sam wzorzec, który
/// do teraz służył do współdzielenia fixture'a WebApplicationFactory między testami
/// (ClassDataSource + SharedType) - dziś pod spodem nie stoi WebApplicationFactory,
/// a cały rozproszony system Aspire (AppHost + kontener Redis + CacheApi).
///
/// IAsyncInitializer.InitializeAsync() woła się RAZ, zanim TUnit odpali pierwszy
/// test współdzielący ten egzemplarz (patrz SharedType w klasie testowej) -
/// to jedyne miejsce, gdzie realnie startuje Docker. DisposeAsync() woła się
/// RAZ, po ostatnim teście - tam Aspire sprząta kontener (app.StopAsync()).
/// </summary>
public sealed class RedisAppHostFixture : IAsyncInitializer, IAsyncDisposable
{
    private DistributedApplication? _app;

    /// <summary>Ile razy InitializeAsync realnie wystartowało AppHost - dowód, że to RAZ, nie raz na test.</summary>
    public int InitializeCount { get; private set; }

    public async Task InitializeAsync()
    {
        InitializeCount++;

        var appHost = await DistributedApplicationTestingBuilder.CreateAsync<Projects.AppHost>(
            ["Logging:LogLevel:Default=Warning"]);
        _app = await appHost.BuildAsync();
        await _app.StartAsync();

        // WaitFor(cache) w AppHost.cs oznacza: jeśli "cache-api" dojdzie do Healthy,
        // kontener Redis pod spodem już żyje. To samo rozumowanie co w Cache.Verify
        // z wydania #5 - tylko tym razem wywołane z wnętrza hooka TUnit, nie z Main.
        await _app.ResourceNotifications.WaitForResourceHealthyAsync("cache-api");
    }

    public HttpClient CreateHttpClient() => _app!.CreateHttpClient("cache-api");

    public async ValueTask DisposeAsync()
    {
        if (_app is null)
        {
            return;
        }

        await _app.StopAsync();
        await _app.DisposeAsync();
    }
}
