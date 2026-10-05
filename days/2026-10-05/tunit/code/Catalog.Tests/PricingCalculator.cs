namespace Catalog.Tests;

/// <summary>
/// Minimalna logika cenowa katalogu -- przedmiot testów w tym projekcie.
/// Celowo trywialna: fokus wydania jest na zachowaniu hooków [AfterEvery],
/// nie na samej logice biznesowej.
/// </summary>
public static class PricingCalculator
{
    public static decimal NetToGross(decimal net, decimal vatRate)
    {
        if (vatRate < 0) throw new ArgumentOutOfRangeException(nameof(vatRate));
        return Math.Round(net * (1 + vatRate), 2);
    }

    public static decimal ApplyDiscount(decimal price, decimal discountPercent)
    {
        if (discountPercent is < 0 or > 100)
            throw new ArgumentOutOfRangeException(nameof(discountPercent));
        return Math.Round(price * (1 - discountPercent / 100m), 2);
    }
}
