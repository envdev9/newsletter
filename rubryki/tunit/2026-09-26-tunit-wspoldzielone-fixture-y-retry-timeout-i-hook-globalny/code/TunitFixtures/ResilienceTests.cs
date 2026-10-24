namespace TunitFixtures;

public class ResilienceTests
{
    // Licznik prob -- static, bo kazda proba to NOWA instancja klasy testowej.
    private static int _flakyAttempts;

    [Test]
    [Retry(3)]
    public async Task Flaky_PrzechodziDopieroZaTrzecimPodejsciem()
    {
        var attempt = Interlocked.Increment(ref _flakyAttempts);
        Console.WriteLine($"[Retry] proba nr {attempt}, CurrentRetryAttempt={TestContext.Current!.Execution.CurrentRetryAttempt}");
        await Assert.That(attempt).IsGreaterThanOrEqualTo(3);
    }

    [Test]
    [Timeout(2_000)]
    public async Task Timeout_TestMiesciSieWLimicie(CancellationToken cancellationToken)
    {
        // Token jest anulowany przez TUnit po przekroczeniu limitu; przekazujemy go dalej.
        // Zeby zobaczyc porazke: zmien na [Timeout(300)] i Task.Delay(5000, ...).
        await Task.Delay(100, cancellationToken);
        await Assert.That(cancellationToken.IsCancellationRequested).IsFalse();
    }
}
