namespace Shipping.Tests;

/// <summary>
/// [AfterEvery(Assembly)] w PROJEKCIE TESTOWYM nr 2 (Shipping.Tests). Ten projekt ma
/// JEDNĄ klasę testową (4 testy) -- w przeciwieństwie do Catalog.Tests (dwie klasy,
/// 5 testów). Jeśli [AfterEvery(Assembly)] naprawdę jest ograniczone do GRANICY
/// ASSEMBLY (a nie do całego solution-wide `dotnet test`), to w logu zobaczymy TUTAJ
/// wywołanie #1 z TestCount=4 -- niezależnie od tego, co i kiedy odpaliło się w
/// Catalog.Tests.
/// </summary>
public static class AssemblyHooks
{
    [AfterEvery(Assembly)]
    public static void Report(AssemblyHookContext context)
    {
        var n = SharedState.RecordAssemblyFire();

        var passed = context.TestClasses
            .SelectMany(c => c.Tests)
            .Count(t => t.Execution.Result?.State == TestState.Passed);

        Console.WriteLine($"=== [Shipping.Tests] [AfterEvery(Assembly)] wywolanie #{n} ===");
        Console.WriteLine($"  PID procesu = {Environment.ProcessId}");
        Console.WriteLine($"  Testow w TEJ assembly: {context.TestCount} (passed={passed})");
        Console.WriteLine($"  SharedState.ShippingTestsSeen (static pole TYLKO tego projektu) = {SharedState.ShippingTestsSeen}");
    }
}
