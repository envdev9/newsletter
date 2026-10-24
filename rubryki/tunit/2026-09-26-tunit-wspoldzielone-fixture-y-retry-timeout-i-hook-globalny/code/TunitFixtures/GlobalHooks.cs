using System.Collections.Concurrent;

namespace TunitFixtures;

// [BeforeEvery]/[AfterEvery] -- hook globalny: dziala dla KAZDEGO testu w calym zestawie,
// bez wpisywania go w kazda klase. Metoda musi byc static.
public static class GlobalHooks
{
    public static ConcurrentBag<string> Seen { get; } = new();

    [BeforeEvery(Test)]
    public static void KazdyTestPrzed(TestContext context)
    {
        Seen.Add(context.Metadata.TestName);
    }
}

// Raport zbiorczy: [After(TestSession)] uruchamia sie raz, po wszystkich testach.
public static class SessionReport
{
    [After(TestSession)]
    public static void Report()
    {
        var lines = new List<string>
        {
            "=== RAPORT FIXTURE ===",
            $"FakeDatabase: utworzono={FakeDatabase.Created}, zwolniono={FakeDatabase.Disposed}",
            $"PerTestSession: id={string.Join(",", SessionA.SeenIds.Distinct().OrderBy(x => x))}",
            $"PerClass A:     id={string.Join(",", PerClassA.Ids.Distinct().OrderBy(x => x))}",
            $"PerClass B:     id={string.Join(",", PerClassB.Ids.Distinct().OrderBy(x => x))}",
            $"Keyed tenant-1: id={string.Join(",", KeyedA.Ids.Distinct().OrderBy(x => x))}",
            $"Keyed tenant-2: id={string.Join(",", KeyedC.Ids.Distinct().OrderBy(x => x))}",
            $"None:           id={string.Join(",", NotSharedTests.Ids.Distinct().OrderBy(x => x))}",
            $"[BeforeEvery] widzial {GlobalHooks.Seen.Count} testow",
        };
        lines.AddRange(FakeDatabase.Journal.Select(l => "  " + l));

        // Console z hooka sesji nie trafia do raportu dotnet test, wiec zapisujemy do pliku.
        var path = Path.Combine(Path.GetTempPath(), "tunit-fixtures-report.txt");
        File.WriteAllLines(path, lines);
        foreach (var l in lines) Console.WriteLine(l);
    }
}
