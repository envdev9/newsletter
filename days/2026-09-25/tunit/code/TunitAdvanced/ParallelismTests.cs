using TUnit.Core.Interfaces;

namespace TunitAdvanced;

/// <summary>Licznik pomocniczy: ile testow z danej grupy dziala JEDNOCZESNIE (i jaki byl szczyt).</summary>
public sealed class Gauge
{
    private int _current;
    private int _peak;

    public int Peak => _peak;

    public async Task RunAsync(int millis)
    {
        var now = Interlocked.Increment(ref _current);
        int seen;
        while (now > (seen = Volatile.Read(ref _peak)))
            Interlocked.CompareExchange(ref _peak, now, seen);

        await Task.Delay(millis);
        Interlocked.Decrement(ref _current);
    }
}

// ---------------------------------------------------------------------------
// A) Domyslnie: testy dzialaja rownolegle. 6 testow x 300 ms => szczyt wspolbieznosci > 1.
// ---------------------------------------------------------------------------
public class DefaultParallelTests
{
    public static readonly Gauge Gauge = new();

    [Test]
    [Arguments(1)] [Arguments(2)] [Arguments(3)]
    [Arguments(4)] [Arguments(5)] [Arguments(6)]
    public async Task Work(int n) => await Gauge.RunAsync(300);

    [After(Class)]
    public static void Report() => Journal.Add($"[A] domyslnie: szczyt wspolbieznosci = {Gauge.Peak}");
}

// ---------------------------------------------------------------------------
// B) [NotInParallel("klucz")] - testy o tym samym kluczu nigdy nie nakladaja sie w czasie
//    (nawet miedzy roznymi klasami). Idealne dla wspolnego zasobu: plik, tabela, port.
// ---------------------------------------------------------------------------
public static class SharedResource
{
    public static readonly Gauge Gauge = new();
}

public class NotInParallelTestsOne
{
    [Test, NotInParallel("shared-resource")]
    public async Task UseA() => await SharedResource.Gauge.RunAsync(200);

    [Test, NotInParallel("shared-resource")]
    public async Task UseB() => await SharedResource.Gauge.RunAsync(200);
}

public class NotInParallelTestsTwo
{
    [Test, NotInParallel("shared-resource")]
    public async Task UseC() => await SharedResource.Gauge.RunAsync(200);

    [Test, NotInParallel("shared-resource")]
    public async Task UseD() => await SharedResource.Gauge.RunAsync(200);
}

// ---------------------------------------------------------------------------
// C) [DependsOn] - kolejnosc "najpierw X, potem Y". Y startuje po zakonczeniu X.
// ---------------------------------------------------------------------------
public class DependsOnTests
{
    private static readonly List<string> Order = new();
    private static readonly object Gate = new();

    private static void Mark(string s) { lock (Gate) Order.Add(s); }

    [Test]
    public async Task Krok1_Utworz()
    {
        await Task.Delay(300); // celowo wolny, zeby zaleznosc miala znaczenie
        Mark("Krok1_Utworz");
    }

    [Test, DependsOn(nameof(Krok1_Utworz))]
    public async Task Krok2_Odczytaj()
    {
        Mark("Krok2_Odczytaj");
        await Assert.That(Order).Contains("Krok1_Utworz");
    }

    [Test, DependsOn(nameof(Krok2_Odczytaj))]
    public async Task Krok3_Usun()
    {
        Mark("Krok3_Usun");
        await Assert.That(Order).IsEquivalentTo(new[] { "Krok1_Utworz", "Krok2_Odczytaj", "Krok3_Usun" });
    }

    [After(Class)]
    public static void Report() => Journal.Add($"[C] DependsOn - kolejnosc: {string.Join(" -> ", Order)}");
}

// ---------------------------------------------------------------------------
// D) [ParallelLimiter<T>] - "co najwyzej N naraz" dla klasy/testow (np. limit polaczen do bazy).
// ---------------------------------------------------------------------------
public class MaxTwoLimit : IParallelLimit
{
    public int Limit => 2;
}

[ParallelLimiter<MaxTwoLimit>]
public class LimitedParallelTests
{
    public static readonly Gauge Gauge = new();

    [Test]
    [Arguments(1)] [Arguments(2)] [Arguments(3)]
    [Arguments(4)] [Arguments(5)] [Arguments(6)]
    public async Task Limited(int n) => await Gauge.RunAsync(300);

    [After(Class)]
    public static void Report() => Journal.Add($"[D] ParallelLimiter(2): szczyt wspolbieznosci = {Gauge.Peak}");
}
