namespace TunitAdvanced;

/// <summary>Klasa testowana: rabat procentowy z zaokrągleniem do groszy.</summary>
public static class PriceCalculator
{
    public static decimal ApplyDiscount(decimal price, int percent)
    {
        if (percent is < 0 or > 100)
            throw new ArgumentOutOfRangeException(nameof(percent));

        return Math.Round(price * (100 - percent) / 100m, 2, MidpointRounding.AwayFromZero);
    }
}
