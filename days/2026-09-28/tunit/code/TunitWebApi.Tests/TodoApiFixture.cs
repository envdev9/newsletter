using Microsoft.AspNetCore.Mvc.Testing;
using TUnit.Core.Interfaces;

namespace TunitWebApi.Tests;

/// <summary>
/// TUnit-owy odpowiednik xUnitowego "IClassFixture&lt;WebApplicationFactory&lt;Program&gt;&gt;".
/// Hostuje prawdziwe API w pamięci (TestServer) raz na klasę testową (patrz
/// [ClassDataSource&lt;TodoApiFixture&gt;(Shared = SharedType.PerClass)] w TodoApiTests).
/// </summary>
public class TodoApiFixture : WebApplicationFactory<Program>, IAsyncInitializer
{
    public HttpClient Client { get; private set; } = null!;

    public Task InitializeAsync()
    {
        Console.WriteLine("[Fixture] InitializeAsync: startuje WebApplicationFactory<Program>");
        Client = CreateClient();
        return Task.CompletedTask;
    }

    public override async ValueTask DisposeAsync()
    {
        Console.WriteLine("[Fixture] DisposeAsync: zamykam TestServer");
        await base.DisposeAsync();
    }
}
