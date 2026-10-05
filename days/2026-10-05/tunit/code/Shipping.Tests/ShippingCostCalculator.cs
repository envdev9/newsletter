namespace Shipping.Tests;

/// <summary>
/// Minimalna logika kosztu wysyłki -- przedmiot testów DRUGIEGO projektu testowego
/// w tym repo (pierwszy: Catalog.Tests). Celowo trywialna z tych samych powodów co
/// PricingCalculator w Catalog.Tests.
/// </summary>
public static class ShippingCostCalculator
{
    public static decimal CostFor(decimal weightKg)
    {
        if (weightKg < 0) throw new ArgumentOutOfRangeException(nameof(weightKg));

        return weightKg switch
        {
            <= 1m => 9.99m,
            <= 5m => 14.99m,
            <= 20m => 24.99m,
            _ => 49.99m
        };
    }
}
