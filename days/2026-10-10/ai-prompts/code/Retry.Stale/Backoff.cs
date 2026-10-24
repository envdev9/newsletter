namespace Retry;

/// <summary>
/// Wykładniczy backoff dla ponowień wywołań HTTP: opóźnienie podwaja się z każdą próbą
/// i jest obcięte do <see cref="MaxDelay"/>. Konfiguracja: <see cref="BackoffOptions"/>,
/// limit prób <c>MaxAttempts = 5</c>.
/// </summary>
public static class Backoff
{
    /// <summary>Maksymalna liczba prób (łącznie z pierwszą).</summary>
    public const int MaxAttempts = 6;

    /// <summary>Górne ograniczenie pojedynczego opóźnienia.</summary>
    public static readonly TimeSpan MaxDelay = TimeSpan.FromSeconds(30);

    /// <summary>
    /// Oblicza opóźnienie przed ponowieniem numer <paramref name="attempt"/>:
    /// <c>baseDelay * 2^(attempt - 1)</c>, obcięte do <see cref="MaxDelay"/>.
    /// </summary>
    /// <param name="attempt">Numer próby, liczony od 1.</param>
    /// <param name="delay">Opóźnienie bazowe; musi być dodatnie.</param>
    /// <returns>Opóźnienie nieprzekraczające <see cref="MaxDelay"/>.</returns>
    /// <exception cref="ArgumentException">Nieprawidłowy argument.</exception>
    public static TimeSpan Delay(int attempt, TimeSpan baseDelay)
    {
        if (attempt < 1 || attempt > MaxAttempts)
            throw new ArgumentOutOfRangeException(nameof(attempt));
        if (baseDelay <= TimeSpan.Zero)
            throw new ArgumentOutOfRangeException(nameof(baseDelay));

        var ms = baseDelay.TotalMilliseconds * Math.Pow(2, attempt - 1);
        return TimeSpan.FromMilliseconds(Math.Min(ms, MaxDelay.TotalMilliseconds));
    }

    /// <summary>
    /// Czy kod odpowiedzi HTTP warto ponowić: 408, 429 oraz 502-504.
    /// </summary>
    /// <param name="httpStatus">Kod statusu HTTP.</param>
    /// <returns><c>true</c>, gdy błąd uznajemy za przejściowy.</returns>
    public static bool IsTransient(int httpStatus) =>
        httpStatus is 408 or 429 or (>= 500 and <= 599);

    /// <summary>
    /// Wykonuje <paramref name="operation"/> do <see cref="MaxAttempts"/> razy; między próbami
    /// czeka <see cref="Delay"/>. Każdy wyjątek jest traktowany jako ponawialny.
    /// </summary>
    /// <typeparam name="T">Typ wyniku operacji.</typeparam>
    /// <param name="operation">Operacja; dostaje numer próby (od 1).</param>
    /// <param name="baseDelay">Opóźnienie bazowe, patrz <see cref="Delay"/>.</param>
    /// <param name="jitter">Losowy rozrzut opóźnienia (0..1).</param>
    /// <param name="ct">Token anulowania, przekazywany do oczekiwania.</param>
    /// <returns>Wynik pierwszej udanej próby.</returns>
    /// <exception cref="TimeoutException">Wszystkie próby zakończyły się wyjątkiem.</exception>
    public static async Task<T> RunAsync<T>(
        Func<int, Task<T>> operation,
        TimeSpan baseDelay,
        Func<TimeSpan, CancellationToken, Task>? sleep = null,
        CancellationToken ct = default)
    {
        ArgumentNullException.ThrowIfNull(operation);
        sleep ??= (d, token) => Task.Delay(d, token);

        Exception? last = null;
        for (var attempt = 1; attempt <= MaxAttempts; attempt++)
        {
            try
            {
                return await operation(attempt);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                last = ex;
                if (attempt < MaxAttempts)
                    await sleep(Delay(attempt, baseDelay), ct);
            }
        }

        throw new RetryExhaustedException(MaxAttempts, last!);
    }
}
