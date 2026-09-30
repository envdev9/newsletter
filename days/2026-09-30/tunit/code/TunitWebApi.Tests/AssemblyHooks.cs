namespace TunitWebApi.Tests;

/// <summary>
/// [AfterEvery(Assembly)] -- hook globalny wolany RAZ, po tym jak WSZYSTKIE testy w calym
/// zestawie (assembly) sie zakoncza -- niezaleznie z ilu klas testowych sie skladaja.
/// Uzywamy go do raportu koncowego: ile razy TodoApiFixture zostal faktycznie utworzony
/// (InitializeCount) i czy obie klasy (TodoApiTests, NotesApiTests) widzialy ten sam
/// instance-id hosta.
/// </summary>
public static class AssemblyHooks
{
    [AfterEvery(Assembly)]
    public static void Report(AssemblyHookContext context)
    {
        var ids = InstanceIdObservations.SeenByClass;
        var distinctIds = ids.Values.Distinct().Count();

        Console.WriteLine("=== RAPORT [AfterEvery(Assembly)] ===");
        Console.WriteLine($"TodoApiFixture.InitializeCount = {TodoApiFixture.InitializeCount}");
        Console.WriteLine($"TodoApiFixture.DisposeCount    = {TodoApiFixture.DisposeCount}");
        foreach (var (className, id) in ids.OrderBy(kv => kv.Key))
        {
            Console.WriteLine($"  instance-id widziany przez {className}: {id}");
        }
        Console.WriteLine($"Liczba roznych instance-id: {distinctIds} (oczekiwane: 1 -- jeden wspolny host PerTestSession)");
    }
}
