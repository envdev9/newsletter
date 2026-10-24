namespace ReportingLab;

// Test, ktory jest zawsze pominiety: sluzy do sprawdzenia kodu wyjscia, gdy NIC sie nie wykonalo.
public class AllSkipped
{
    [Test]
    [Skip("celowo pominiety - sprawdzamy kod wyjscia")]
    [Property("Kind", "AllSkipped")]
    public async Task S1() => await Task.CompletedTask;
}
