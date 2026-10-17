namespace Hard;

public interface IPricer
{
    decimal Price(string sku);
}

public enum Tier
{
    Basic,
    Premium,
}

public readonly record struct Rate(decimal Value, string Currency);

public class Pricer(IPricer inner) : IPricer
{
    private int _calls;

    public decimal Price(string sku) => Price(sku, 1);

    public decimal Price(string sku, int quantity)
    {
        _calls++;
        return inner.Price(sku) * quantity;
    }

    [Obsolete("use Price")]
    public static decimal Old(
        string sku) => 0m;

    public (decimal Low, decimal High) Range() => (0m, 1m);
}

public static class PricerExtensions
{
    public static decimal Doubled(this Pricer p, string sku) => p.Price(sku) * 2;
}
