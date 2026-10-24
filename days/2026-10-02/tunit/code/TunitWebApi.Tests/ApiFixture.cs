using Microsoft.AspNetCore.Mvc.Testing;
using TUnit.Core.Interfaces;

namespace TunitWebApi.Tests;

/// <summary>
/// WebApplicationFactory&lt;Program&gt; wspoldzielony w obrebie JEDNEJ klasy testowej
/// (Shared = SharedType.PerClass -- wzorzec znany z wydania #5, 2026-09-28). Kazda z
/// dwoch klas testowych w tym wydaniu (AuthenticatedUserTests, AdminAuthorizationTests)
/// deklaruje wlasny [ClassDataSource&lt;ApiFixture&gt;(Shared = SharedType.PerClass)], wiec
/// oczekujemy DWOCH niezaleznych instancji -- InitializeCount powinien wyladowac na 2 po
/// calym przebiegu. To jest material dowodowy dla [AfterEvery(Class)] w ClassHooks.cs:
/// hook powinien odpalic sie DWA razy (raz na klase), nie raz na caly przebieg jak
/// [AfterEvery(Assembly)] z wydania #7.
/// </summary>
public class ApiFixture : WebApplicationFactory<Program>, IAsyncInitializer
{
    private static int _initializeCount;
    public static int InitializeCount => _initializeCount;

    public HttpClient Client { get; private set; } = null!;

    public Task InitializeAsync()
    {
        var n = Interlocked.Increment(ref _initializeCount);
        Console.WriteLine($"[ApiFixture] InitializeAsync wywolanie #{n}");
        Client = CreateClient();
        return Task.CompletedTask;
    }
}
