namespace TunitAdvanced;

/// <summary>Wspolny dziennik zdarzen, zeby pokazac KOLEJNOSC hookow w prawdziwym outpucie.</summary>
public static class Journal
{
    private static readonly System.Collections.Concurrent.ConcurrentQueue<string> Lines = new();

    public static void Add(string line) => Lines.Enqueue(line);

    public static void Dump(string title)
    {
        Console.WriteLine($"--- {title} ---");
        foreach (var l in Lines) Console.WriteLine(l);
    }
}

// Zakres ASSEMBLY: raz na caly przebieg, metoda statyczna. Trzymamy je w OSOBNEJ klasie
// (analizator TUnit0042 ostrzega przed mieszaniem hookow globalnych z klasa testowa).
public static class GlobalHooks
{
    [Before(Assembly)]
    public static void BeforeAssembly() => Journal.Add("[Before Assembly] start przebiegu");

    [After(Assembly)]
    public static void AfterAssembly()
    {
        // Raport grupy B (klucz wspolny dla dwoch klas) mozna zlozyc dopiero po WSZYSTKICH testach.
        Journal.Add($"[B] NotInParallel(\"shared-resource\"): szczyt wspolbieznosci = {SharedResource.Gauge.Peak}");
        Journal.Add("[After  Assembly] koniec przebiegu");
        Journal.Dump("Dziennik zdarzen calego przebiegu");
    }
}

public class HookTests
{

    // Zakres CLASS: raz na klase, metoda statyczna.
    [Before(Class)]
    public static void BeforeClass() => Journal.Add("[Before Class]    HookTests");

    [After(Class)]
    public static void AfterClass() => Journal.Add("[After  Class]    HookTests");

    // Zakres TEST: przed/po KAZDYM testem, metoda instancyjna
    // (TUnit tworzy nowa instancje klasy per test, jak xUnit).
    private readonly Guid _instanceId = Guid.NewGuid();

    [Before(Test)]
    public void BeforeEachTest(TestContext context)
        => Journal.Add($"[Before Test]     {context.Metadata.TestName}");

    [After(Test)]
    public void AfterEachTest(TestContext context)
        => Journal.Add($"[After  Test]     {context.Metadata.TestName}");

    [Test]
    public async Task Pierwszy()
    {
        Journal.Add("    ...cialo testu Pierwszy");
        await Assert.That(_instanceId).IsNotEqualTo(Guid.Empty);
    }

    [Test]
    public async Task Drugi()
    {
        Journal.Add("    ...cialo testu Drugi");
        var suma = int.Parse("1") + int.Parse("1");
        await Assert.That(suma).IsEqualTo(2);
    }
}
