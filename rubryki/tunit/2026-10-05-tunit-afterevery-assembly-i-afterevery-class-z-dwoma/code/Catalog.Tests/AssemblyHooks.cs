namespace Catalog.Tests;

/// <summary>
/// [AfterEvery(Assembly)] w PROJEKCIE TESTOWYM nr 1 z dwóch w tym repo (drugi: Shipping.Tests).
/// Pytanie, na które to wydanie odpowiada: gdy `dotnet test` odpytuje WIĘCEJ niż jeden
/// projekt testowy na raz (solution-wide run), czy ten hook odpala się RAZ NA CAŁY
/// PRZEBIEG (obejmujący oba projekty), czy RAZ NA ASSEMBLY (czyli raz tutaj, raz w
/// Shipping.Tests, niezależnie)? SharedState.AssemblyFires/Environment.ProcessId
/// pozwalają to zmierzyć, nie zgadnąć.
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

        Console.WriteLine($"=== [Catalog.Tests] [AfterEvery(Assembly)] wywolanie #{n} ===");
        Console.WriteLine($"  PID procesu = {Environment.ProcessId}");
        Console.WriteLine($"  Testow w TEJ assembly: {context.TestCount} (passed={passed})");
        Console.WriteLine($"  SharedState.CatalogTestsSeen (static pole TYLKO tego projektu) = {SharedState.CatalogTestsSeen}");
    }
}
