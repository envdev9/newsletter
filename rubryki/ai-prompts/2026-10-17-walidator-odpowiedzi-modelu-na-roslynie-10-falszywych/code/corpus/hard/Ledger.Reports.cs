namespace Hard;

public partial class Ledger
{
    public decimal Average() => _entries.Count == 0 ? 0m : _entries.Average();

    public decimal Max(
        decimal floor,
        decimal ceiling)
    {
        return Math.Clamp(Balance, floor, ceiling);
    }

    internal int Count => _entries.Count;
}
