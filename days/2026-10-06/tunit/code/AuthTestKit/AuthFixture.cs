using System.Security.Cryptography;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Microsoft.Extensions.Time.Testing;
using AuthApi;
using TUnit.Core.Interfaces;

namespace AuthTestKit;

/// <summary>
/// Wspolna fixture dla WSZYSTKICH projektow testowych (zywa w osobnym projekcie
/// AuthTestKit, nie skopiowana). Podmienia w aplikacji dwie rzeczy:
///  - KeyMaterial -> klucz RSA trzymany przez test (test moze podpisywac "legalne" tokeny),
///  - TimeProvider -> FakeTimeProvider (test steruje czasem: wygasanie bez Thread.Sleep).
/// </summary>
public sealed class AuthFixture : WebApplicationFactory<Program>, IAsyncInitializer
{
    private static int _initializeCount;
    public static int InitializeCount => _initializeCount;

    public RSA TestRsa { get; } = RSA.Create(2048);

    public FakeTimeProvider Time { get; } = new(new DateTimeOffset(2026, 10, 6, 12, 0, 0, TimeSpan.Zero));

    public Guid InstanceId { get; } = Guid.NewGuid();

    public HttpClient Client { get; private set; } = null!;

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureTestServices(services =>
        {
            services.RemoveAll<KeyMaterial>();
            services.AddSingleton(new KeyMaterial(TestRsa));
            services.RemoveAll<TimeProvider>();
            services.AddSingleton<TimeProvider>(Time);
        });
    }

    public Task InitializeAsync()
    {
        Interlocked.Increment(ref _initializeCount);
        Client = CreateClient();
        return Task.CompletedTask;
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing) TestRsa.Dispose();
        base.Dispose(disposing);
    }
}
