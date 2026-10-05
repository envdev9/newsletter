namespace Catalog.Tests;

public class PricingTests
{
    [Test]
    public async Task NetToGross_Z23ProcVat_LiczyPoprawnie()
    {
        var gross = PricingCalculator.NetToGross(100m, 0.23m);

        await Assert.That(gross).IsEqualTo(123.00m);
    }

    [Test]
    public async Task NetToGross_ZZerowymVat_ZwracaNetto()
    {
        var gross = PricingCalculator.NetToGross(100m, 0m);

        await Assert.That(gross).IsEqualTo(100.00m);
    }

    [Test]
    public async Task NetToGross_ZUjemnymVat_RzucaWyjatek()
    {
        await Assert.That(() => PricingCalculator.NetToGross(100m, -0.01m))
            .Throws<ArgumentOutOfRangeException>();
    }
}
