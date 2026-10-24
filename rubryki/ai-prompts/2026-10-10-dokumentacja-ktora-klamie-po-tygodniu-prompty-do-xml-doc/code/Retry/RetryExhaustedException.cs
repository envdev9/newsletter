namespace Retry;

/// <summary>Zgłaszany, gdy wyczerpano wszystkie próby ponowienia.</summary>
public sealed class RetryExhaustedException : Exception
{
    /// <summary>Tworzy wyjątek z liczbą wykonanych prób i ostatnim błędem.</summary>
    /// <param name="attempts">Liczba wykonanych prób.</param>
    /// <param name="inner">Wyjątek z ostatniej próby.</param>
    public RetryExhaustedException(int attempts, Exception inner)
        : base($"Wyczerpano {attempts} prób.", inner)
    {
        Attempts = attempts;
    }

    /// <summary>Liczba wykonanych prób.</summary>
    public int Attempts { get; }
}
