namespace Catalog.Tests;

public class DiscountTests
{
    [Test]
    public async Task ApplyDiscount_Z10Proc_Obniza()
    {
        var discounted = PricingCalculator.ApplyDiscount(200m, 10m);

        await Assert.That(discounted).IsEqualTo(180.00m);
    }

    [Test]
    public async Task ApplyDiscount_Z100Proc_DajeZero()
    {
        var discounted = PricingCalculator.ApplyDiscount(200m, 100m);

        await Assert.That(discounted).IsEqualTo(0.00m);
    }
}
