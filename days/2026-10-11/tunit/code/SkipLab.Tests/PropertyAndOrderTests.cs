namespace SkipLab.Tests;

/// <summary>[Property] to znacznik klucz/wartosc, po ktorym mozna filtrowac (--treenode-filter).</summary>
public class PropertyTests
{
    [Test]
    [Property("Kind", "Unit")]
    public async Task Unit_A()
    {
        Trace.Add("body Unit_A");
        await Assert.That(Slugifier.Slugify("A B")).IsEqualTo("a-b");
    }

    [Test]
    [Property("Kind", "Unit")]
    public async Task Unit_B()
    {
        Trace.Add("body Unit_B");
        await Assert.That("ab".Length).IsEqualTo(2);
    }

    [Test]
    [Property("Kind", "Integration")]
    public async Task Integration_C()
    {
        Trace.Add("body Integration_C");
        await Assert.That(Slugifier.Slugify("x")).IsEqualTo("x");
    }
}

/// <summary>Wypisuje dziennik: czy ShouldSkip poszlo przed cialami testow?</summary>
public class TraceDumpTests
{
    [Test]
    public async Task Zrzut_kolejnosci_zdarzen()
    {
        var mine = Trace.Add("body Zrzut_kolejnosci_zdarzen");
        foreach (var (seq, what) in Trace.Events.OrderBy(e => e.Seq))
        {
            Console.WriteLine($"TRACE {seq,3}: {what}");
        }

        var shouldSkipEvents = Trace.Events.Where(e => e.What.StartsWith("ShouldSkip")).ToList();
        Console.WriteLine($"TRACE ShouldSkip wywolan: {shouldSkipEvents.Count}, najwyzszy numer: {shouldSkipEvents.Max(e => e.Seq)}, moj numer: {mine}");
        await Assert.That(shouldSkipEvents.Count).IsGreaterThan(0);
    }
}
