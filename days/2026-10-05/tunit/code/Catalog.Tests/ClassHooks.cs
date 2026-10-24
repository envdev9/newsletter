namespace Catalog.Tests;

/// <summary>
/// [AfterEvery(Class)] w Catalog.Tests -- w TYM projekcie są DWIE klasy testowe
/// (PricingTests, DiscountTests), więc ten hook powinien odpalić się DWA razy,
/// podczas gdy [AfterEvery(Assembly)] w AssemblyHooks.cs odpali się RAZ (po obu
/// klasach, na koniec całej assembly Catalog.Tests).
/// </summary>
public static class ClassHooks
{
    [AfterEvery(Class)]
    public static void Report(ClassHookContext context)
    {
        var n = SharedState.RecordClassFire();

        var passed = context.Tests.Count(t => t.Execution.Result?.State == TestState.Passed);

        Console.WriteLine($"=== [Catalog.Tests] [AfterEvery(Class)] wywolanie #{n}: klasa {context.ClassType.Name} ===");
        Console.WriteLine($"  Testow w klasie: {context.TestCount} (passed={passed})");
    }
}
