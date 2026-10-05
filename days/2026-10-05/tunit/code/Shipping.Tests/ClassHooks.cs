namespace Shipping.Tests;

/// <summary>
/// [AfterEvery(Class)] w Shipping.Tests -- tu jest TYLKO JEDNA klasa testowa
/// (ShippingCostTests), więc ten hook odpali się RAZ, w przeciwieństwie do
/// Catalog.Tests, gdzie odpali się DWA razy (dwie klasy).
/// </summary>
public static class ClassHooks
{
    [AfterEvery(Class)]
    public static void Report(ClassHookContext context)
    {
        var n = SharedState.RecordClassFire();

        var passed = context.Tests.Count(t => t.Execution.Result?.State == TestState.Passed);

        Console.WriteLine($"=== [Shipping.Tests] [AfterEvery(Class)] wywolanie #{n}: klasa {context.ClassType.Name} ===");
        Console.WriteLine($"  Testow w klasie: {context.TestCount} (passed={passed})");
    }
}
