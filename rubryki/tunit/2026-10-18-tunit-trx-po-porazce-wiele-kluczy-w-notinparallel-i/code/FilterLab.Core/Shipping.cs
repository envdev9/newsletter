namespace FilterLab.Core;

/// <summary>Kod produkcyjny pod pomiar pokrycia. Gałąź "Express" jest celowo NIE pokryta testami.</summary>
public static class Shipping
{
    public static decimal Cost(string method, decimal weightKg)
    {
        if (weightKg <= 0) throw new ArgumentOutOfRangeException(nameof(weightKg));

        if (method == "standard")
        {
            return weightKg <= 1 ? 10m : 10m + (weightKg - 1) * 2m;
        }

        if (method == "express")
        {
            return 25m + weightKg * 5m;
        }

        throw new ArgumentException($"nieznana metoda: {method}", nameof(method));
    }
}
