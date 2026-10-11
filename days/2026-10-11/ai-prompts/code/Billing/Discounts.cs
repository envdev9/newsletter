namespace Billing;

/// <summary>Reguły rabatowe.</summary>
public static class Discounts
{
    /// <summary>Czy suma kwalifikuje się do rabatu.</summary>
    public static bool IsEligible(decimal subtotal) =>
        subtotal >= 100m;
}
