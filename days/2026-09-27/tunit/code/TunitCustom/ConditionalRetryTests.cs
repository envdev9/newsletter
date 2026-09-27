namespace TunitCustom;

/// <summary>
/// Wyjatek "przejsciowy" (np. timeout sieci) -- warto ponowic.
/// </summary>
public sealed class TransientException(string message) : Exception(message);

/// <summary>
/// Wlasny atrybut retry: ponawia TYLKO gdy test padl z wyjatkiem przejsciowym.
/// Bledy logiczne (np. AssertionException) nie sa maskowane.
/// </summary>
public sealed class RetryOnTransientAttribute(int times) : RetryAttribute(times)
{
    public override Task<bool> ShouldRetry(TestContext context, Exception exception, int currentRetryAttempt)
    {
        Console.WriteLine($"[ShouldRetry] proba={currentRetryAttempt}, wyjatek={exception.GetType().Name}");
        return Task.FromResult(exception is TransientException);
    }
}

public class ConditionalRetryTests
{
    private static int _transientAttempts;

    [Test]
    [RetryOnTransient(3)]
    public async Task Przejsciowy_Blad_JestPonawiany()
    {
        var attempt = Interlocked.Increment(ref _transientAttempts);
        Console.WriteLine($"[Transient] proba {attempt}");
        if (attempt < 3) throw new TransientException($"siec padla (proba {attempt})");
        await Assert.That(attempt).IsEqualTo(3);
    }
}
