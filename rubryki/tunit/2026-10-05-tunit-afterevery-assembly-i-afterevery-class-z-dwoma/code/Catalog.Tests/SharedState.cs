namespace Catalog.Tests;

/// <summary>
/// Statyczny stan WYŁĄCZNIE tego projektu (Catalog.Tests). Celowo nazwany identycznie
/// jak klasa w Shipping.Tests (patrz tamten projekt) -- to NIE jest ten sam typ ani ta
/// sama pamięć, mimo identycznej nazwy i identycznego kodu: każdy projekt testowy to
/// osobna skompilowana assembly, a pod Microsoft.Testing.Platform (TUnit) -- jak
/// zweryfikowano w tym wydaniu -- także osobny proces systemowy. Dwa "SharedState" w
/// dwóch projektach nigdy się nie zobaczą.
/// </summary>
public static class SharedState
{
    private static int _assemblyFires;
    private static int _classFires;

    public static int CatalogTestsSeen { get; private set; }

    public static int RecordAssemblyFire() => Interlocked.Increment(ref _assemblyFires);

    public static int RecordClassFire()
    {
        CatalogTestsSeen++;
        return Interlocked.Increment(ref _classFires);
    }
}
