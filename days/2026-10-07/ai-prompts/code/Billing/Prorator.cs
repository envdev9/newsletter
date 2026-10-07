namespace Billing;

/// <summary>
/// Rozliczenia abonamentu. To jest "kod pod testami" z artykulu - maly, ale z prawdziwymi
/// przypadkami brzegowymi (granice miesiaca, rok przestepny, zaokraglanie, reszta groszy).
/// </summary>
public static class Prorator
{
    /// <summary>
    /// Oplata za dany miesiac rozliczeniowy dla abonamentu aktywowanego w dniu <paramref name="activation"/>.
    /// Aktywacja w pierwszym dniu miesiaca (lub wczesniej) = pelna cena; po ostatnim dniu = 0.
    /// W pozostalych przypadkach: cena * (dni od aktywacji WLACZNIE do konca miesiaca) / (dni w miesiacu),
    /// zaokraglone do groszy (MidpointRounding.AwayFromZero).
    /// </summary>
    /// <exception cref="ArgumentOutOfRangeException">Cena ujemna.</exception>
    public static decimal Charge(decimal monthlyPrice, int year, int month, DateOnly activation)
    {
        if (monthlyPrice < 0) throw new ArgumentOutOfRangeException(nameof(monthlyPrice));
        var daysInMonth = DateTime.DaysInMonth(year, month);
        var first = new DateOnly(year, month, 1);
        var last = new DateOnly(year, month, daysInMonth);
        if (activation <= first) return Round(monthlyPrice);
        if (activation > last) return 0m;
        var remaining = last.DayNumber - activation.DayNumber + 1;
        return Round(monthlyPrice * remaining / daysInMonth);
    }

    /// <summary>
    /// Dzieli kwote (max 2 miejsca po przecinku, nieujemna) na <paramref name="parts"/> pozycji co do grosza.
    /// Suma pozycji == kwota. Reszta groszy trafia po 1 gr do PIERWSZYCH pozycji.
    /// </summary>
    /// <exception cref="ArgumentOutOfRangeException">parts &lt;= 0 albo kwota ujemna.</exception>
    /// <exception cref="ArgumentException">Kwota ma wiecej niz 2 miejsca po przecinku.</exception>
    public static IReadOnlyList<decimal> Split(decimal total, int parts)
    {
        if (parts <= 0) throw new ArgumentOutOfRangeException(nameof(parts));
        if (total < 0) throw new ArgumentOutOfRangeException(nameof(total));
        if (total != Round(total)) throw new ArgumentException("Kwota ma wiecej niz 2 miejsca po przecinku.", nameof(total));
        var cents = (long)(total * 100m);
        var baseCents = cents / parts;
        var rem = (int)(cents % parts);
        var result = new decimal[parts];
        for (var i = 0; i < parts; i++)
            result[i] = (baseCents + (i < rem ? 1 : 0)) / 100m;
        return result;
    }

    private static decimal Round(decimal v) => Math.Round(v, 2, MidpointRounding.AwayFromZero);
}
