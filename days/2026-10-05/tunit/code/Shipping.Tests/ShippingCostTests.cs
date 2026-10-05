namespace Shipping.Tests;

public class ShippingCostTests
{
    [Test]
    public async Task CostFor_1Kg_DajeNajnizszaStawke()
    {
        await Assert.That(ShippingCostCalculator.CostFor(1m)).IsEqualTo(9.99m);
    }

    [Test]
    public async Task CostFor_5Kg_DajeSrodkowaStawke()
    {
        await Assert.That(ShippingCostCalculator.CostFor(5m)).IsEqualTo(14.99m);
    }

    [Test]
    public async Task CostFor_20Kg_DajeWyzszaStawke()
    {
        await Assert.That(ShippingCostCalculator.CostFor(20m)).IsEqualTo(24.99m);
    }

    [Test]
    public async Task CostFor_PonadLimit_DajeNajwyzszaStawke()
    {
        await Assert.That(ShippingCostCalculator.CostFor(100m)).IsEqualTo(49.99m);
    }
}
