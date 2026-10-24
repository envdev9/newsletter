namespace Billing;

/// <summary>Pozycja faktury.</summary>
public sealed record InvoiceLine(string Sku, int Quantity, decimal UnitPrice);

/// <summary>Liczenie wartości faktury.</summary>
public static class InvoiceCalculator
{
    /// <summary>Wartość jednej pozycji (ilość x cena), zaokrąglona do groszy.</summary>
    public static decimal LineTotal(InvoiceLine line)
    {
        ArgumentNullException.ThrowIfNull(line);
        return Money.Round(line.Quantity * line.UnitPrice);
    }

    /// <summary>Suma pozycji pomniejszona o rabat procentowy.</summary>
    public static decimal Total(IEnumerable<InvoiceLine> lines, decimal discountPercent = 0m)
    {
        ArgumentNullException.ThrowIfNull(lines);
        var sum = lines.Sum(LineTotal);
        return sum - Money.Percent(sum, discountPercent);
    }
}
