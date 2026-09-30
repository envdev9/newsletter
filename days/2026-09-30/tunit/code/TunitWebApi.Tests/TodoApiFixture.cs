using Microsoft.AspNetCore.Mvc.Testing;
using TUnit.Core.Interfaces;

namespace TunitWebApi.Tests;

/// <summary>
/// TUnit-owy odpowiednik xUnitowego "ICollectionFixture&lt;WebApplicationFactory&lt;Program&gt;&gt;".
/// W wydaniu #5 (2026-09-28) uzylismy Shared = SharedType.PerClass -- jeden host na klase
/// testowa. Dzis obie klasy testowe (TodoApiTests, NotesApiTests) wskazuja na TEN SAM typ
/// fixture'a z Shared = SharedType.PerTestSession, wiec TUnit powinien utworzyc go RAZ na
/// caly przebieg testow, niezaleznie od tego, ile roznych klas po niego siega.
///
/// InitializeCount/DisposeCount sa statyczne (Interlocked) wlasnie po to, zeby to zmierzyc:
/// jesli PerTestSession dziala tak jak deklaruje dokumentacja, InitializeCount powinien
/// wyladowac na 1 po CALYM przebiegu (obu klasach), a nie na 2 (co byloby zachowaniem
/// PerClass zastosowanym przez pomylke).
/// </summary>
public class TodoApiFixture : WebApplicationFactory<Program>, IAsyncInitializer
{
    private static int _initializeCount;
    private static int _disposeCount;

    public static int InitializeCount => _initializeCount;
    public static int DisposeCount => _disposeCount;

    public HttpClient Client { get; private set; } = null!;

    public Task InitializeAsync()
    {
        var n = Interlocked.Increment(ref _initializeCount);
        Console.WriteLine($"[Fixture] InitializeAsync wywolanie #{n}");
        Client = CreateClient();
        return Task.CompletedTask;
    }

    public override async ValueTask DisposeAsync()
    {
        var n = Interlocked.Increment(ref _disposeCount);
        Console.WriteLine($"[Fixture] DisposeAsync wywolanie #{n}");
        await base.DisposeAsync();
    }
}
