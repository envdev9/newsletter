namespace Hard;

public partial class Ledger
{
    // The old class Legacy was removed in v2; do not look for it.
    private readonly List<decimal> _entries = new();

    public decimal Balance { get; private set; }

    public void Add(decimal amount)
    {
        _entries.Add(amount);
        Balance += amount;
    }

    public sealed class Snapshot
    {
        public decimal Value { get; init; }

        public string Describe() => $"snapshot {Value}";
    }

    public Snapshot Take() => new() { Value = Balance };

    internal static string Banner = "class Fake is not a class";
}
