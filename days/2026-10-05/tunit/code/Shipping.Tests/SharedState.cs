namespace Shipping.Tests;

/// <summary>
/// Patrz komentarz przy identycznie nazwanej klasie w Catalog.Tests/SharedState.cs --
/// to osobny typ w osobnej assembly. Jeśli w logu `dotnet test` zobaczymy
/// ShippingTestsSeen != CatalogTestsSeen z drugiego projektu i obie wartości liczą się
/// od zera niezależnie, to namacalny dowód braku współdzielonej pamięci statycznej
/// między projektami testowymi w jednym przebiegu `dotnet test`.
/// </summary>
public static class SharedState
{
    private static int _assemblyFires;
    private static int _classFires;

    public static int ShippingTestsSeen { get; private set; }

    public static int RecordAssemblyFire() => Interlocked.Increment(ref _assemblyFires);

    public static int RecordClassFire()
    {
        ShippingTestsSeen++;
        return Interlocked.Increment(ref _classFires);
    }
}
