using Billing;

namespace Billing.NaiveTests;

// UWAGA: te testy napisal czlowiek (autor artykulu), NIE model. To symulacja typowego wyniku
// promptu "Napisz testy jednostkowe dla klasy Prorator": scenariusz szczesliwy, wartosci "okragle",
// slabe asercje (liczba elementow, "nie null"). Nie jest to zmierzony output zadnego modelu.
public class ProratorNaiveTests
{
    [Test]
    public async Task Charge_FullMonth_ReturnsFullPrice()
    {
        var result = Prorator.Charge(30m, 2026, 6, new DateOnly(2026, 6, 1));
        await Assert.That(result).IsEqualTo(30m);
    }

    [Test]
    public async Task Charge_MidMonth_ReturnsProratedPrice()
    {
        // czerwiec ma 30 dni, od 16. do 30. = 15 dni => polowa
        var result = Prorator.Charge(30m, 2026, 6, new DateOnly(2026, 6, 16));
        await Assert.That(result).IsEqualTo(15m);
    }

    [Test]
    public async Task Charge_ReturnsNonNegative()
    {
        var result = Prorator.Charge(49.99m, 2026, 3, new DateOnly(2026, 3, 10));
        await Assert.That(result >= 0m).IsTrue();
    }

    [Test]
    public async Task Split_Evenly_ReturnsEqualParts()
    {
        var result = Prorator.Split(100m, 4);
        await Assert.That(result.Count).IsEqualTo(4);
        await Assert.That(result[0]).IsEqualTo(25m);
    }

    [Test]
    public async Task Split_WithRemainder_ReturnsRequestedNumberOfParts()
    {
        var result = Prorator.Split(100m, 3);
        await Assert.That(result).IsNotNull();
        await Assert.That(result.Count).IsEqualTo(3);
    }
}
