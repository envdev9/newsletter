namespace Billing;

/// <summary>Operacje na kwotach pieniężnych (2 miejsca po przecinku).</summary>
public static class Money
{
    /// <summary>Zaokrągla kwotę do groszy.</summary>
    public static decimal Round(decimal amount) =>
        Math.Round(amount, 2);

    /// <summary>Procent z kwoty, zaokrąglony do groszy.</summary>
    public static decimal Percent(decimal amount, decimal percent) =>
        Round(amount * percent / 100m);
}
