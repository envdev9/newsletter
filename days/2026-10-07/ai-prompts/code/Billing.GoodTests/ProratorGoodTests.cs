using Billing;

namespace Billing.GoodTests;

// UWAGA: te testy tez napisal czlowiek (autor artykulu), wg listy kontrolnej z "dobrego" promptu
// (prompts/tests_good.txt): tabela przypadkow brzegowych, wyjatki z typem, wlasciwosci (property)
// na ziarnie losowym, kontrakt "reszta groszy do pierwszych pozycji". NIE jest to output modelu.
public class ProratorGoodTests
{
    // (cena, rok, miesiac, dzien aktywacji, oczekiwana oplata) - kazdy wiersz ma powod w komentarzu
    public static IEnumerable<(decimal, int, int, int, decimal)> ChargeCases()
    {
        yield return (30m, 2026, 6, 1, 30m);        // pierwszy dzien = pelna cena
        yield return (30m, 2026, 6, 30, 1m);        // OSTATNI dzien = 1 dzien (granica wlacznie)
        yield return (30m, 2026, 6, 16, 15m);       // polowa miesiaca
        yield return (31m, 2026, 5, 31, 1m);        // maj ma 31 dni
        yield return (29m, 2024, 2, 15, 15m);       // luty przestepny: 29 dni, 15..29 = 15 dni
        yield return (28m, 2026, 2, 15, 14m);       // luty zwykly: 28 dni, 15..28 = 14 dni
        yield return (0m, 2026, 6, 10, 0m);         // cena zero jest dozwolona
        yield return (0.15m, 2026, 6, 30, 0.01m);   // 0.15/30 = 0.005 -> AwayFromZero daje 0.01 (ToEven dalby 0.00)
        yield return (10m, 2026, 6, 20, 3.67m);     // 10*11/30 = 3.6666.. -> 3.67
        yield return (10m, 2026, 6, 10, 7.00m);     // 10*21/30 = 7 dokladnie
    }

    [Test]
    [MethodDataSource(nameof(ChargeCases))]
    public async Task Charge_Table(decimal price, int year, int month, int day, decimal expected)
    {
        var result = Prorator.Charge(price, year, month, new DateOnly(year, month, day));
        await Assert.That(result).IsEqualTo(expected);
    }

    [Test]
    public async Task Charge_ActivationBeforeMonth_IsFullPrice()
    {
        var result = Prorator.Charge(30m, 2026, 6, new DateOnly(2026, 5, 20));
        await Assert.That(result).IsEqualTo(30m);
    }

    [Test]
    public async Task Charge_ActivationAfterMonth_IsZero()
    {
        var result = Prorator.Charge(30m, 2026, 6, new DateOnly(2026, 7, 1));
        await Assert.That(result).IsEqualTo(0m);
    }

    [Test]
    public async Task Charge_NegativePrice_ThrowsArgumentOutOfRange()
    {
        await Assert.That(() => Prorator.Charge(-0.01m, 2026, 6, new DateOnly(2026, 6, 1)))
            .Throws<ArgumentOutOfRangeException>();
    }

    [Test]
    public async Task Charge_Property_NeverExceedsPrice_NeverNegative_MonotonicInActivationDay()
    {
        var rnd = new Random(12345); // stale ziarno => powtarzalnosc
        var checkedCases = 0;
        for (var i = 0; i < 2000; i++)
        {
            var price = rnd.Next(0, 100_000) / 100m;
            var year = rnd.Next(2020, 2031);
            var month = rnd.Next(1, 13);
            var dim = DateTime.DaysInMonth(year, month);
            decimal? previous = null;
            for (var day = 1; day <= dim; day++)
            {
                var c = Prorator.Charge(price, year, month, new DateOnly(year, month, day));
                if (c < 0m || c > price) throw new Exception($"poza zakresem: {price} {year}-{month}-{day} => {c}");
                if (previous is not null && c > previous) throw new Exception($"nie maleje: {price} {year}-{month}-{day}");
                previous = c;
            }
            // pelna cena w dniu 1, a na koncu miesiaca nie wiecej niz cena/dni zaokraglona w gore o 1 gr
            var lastDay = Prorator.Charge(price, year, month, new DateOnly(year, month, dim));
            if (lastDay > Math.Round(price / dim, 2, MidpointRounding.AwayFromZero) + 0.01m)
                throw new Exception($"ostatni dzien za drogi: {price} {year}-{month} => {lastDay}");
            checkedCases++;
        }
        await Assert.That(checkedCases).IsEqualTo(2000);
    }

    [Test]
    public async Task Split_Contract_RemainderGoesToFirstParts()
    {
        var result = Prorator.Split(100m, 3);
        await Assert.That(result.ToArray()).IsEquivalentTo(new[] { 33.34m, 33.33m, 33.33m });
    }

    [Test]
    public async Task Split_Exact_NoRemainder()
    {
        await Assert.That(Prorator.Split(100m, 4).ToArray()).IsEquivalentTo(new[] { 25m, 25m, 25m, 25m });
    }

    [Test]
    public async Task Split_MorePartsThanCents_ZeroesAtTheEnd()
    {
        // 0.02 na 5 pozycji: dwie po 0.01, reszta 0
        await Assert.That(Prorator.Split(0.02m, 5).ToArray())
            .IsEquivalentTo(new[] { 0.01m, 0.01m, 0m, 0m, 0m });
    }

    [Test]
    public async Task Split_ZeroTotal_AllZeroes()
    {
        await Assert.That(Prorator.Split(0m, 3).ToArray()).IsEquivalentTo(new[] { 0m, 0m, 0m });
    }

    [Test]
    public async Task Split_SinglePart_ReturnsWholeAmount()
    {
        await Assert.That(Prorator.Split(12.34m, 1).ToArray()).IsEquivalentTo(new[] { 12.34m });
    }

    [Test]
    [Arguments(0)]
    [Arguments(-1)]
    public async Task Split_NonPositiveParts_ThrowsArgumentOutOfRange(int parts)
    {
        await Assert.That(() => Prorator.Split(10m, parts)).Throws<ArgumentOutOfRangeException>();
    }

    [Test]
    public async Task Split_NegativeTotal_ThrowsArgumentOutOfRange()
    {
        await Assert.That(() => Prorator.Split(-1m, 2)).Throws<ArgumentOutOfRangeException>();
    }

    [Test]
    public async Task Split_MoreThanTwoDecimals_ThrowsArgumentException()
    {
        await Assert.That(() => Prorator.Split(10.001m, 2)).Throws<ArgumentException>();
    }

    [Test]
    public async Task Split_Property_SumEqualsTotal_SpreadAtMostOneCent_NonIncreasing()
    {
        var rnd = new Random(2026);
        var checkedCases = 0;
        for (var i = 0; i < 5000; i++)
        {
            var total = rnd.Next(0, 10_000_000) / 100m;
            var parts = rnd.Next(1, 40);
            var r = Prorator.Split(total, parts);
            if (r.Count != parts) throw new Exception($"liczba pozycji: {total}/{parts}");
            if (r.Sum() != total) throw new Exception($"suma: {total}/{parts} => {r.Sum()}");
            if (r.Max() - r.Min() > 0.01m) throw new Exception($"rozrzut > 1 gr: {total}/{parts}");
            if (r.Any(x => x < 0m)) throw new Exception($"ujemna pozycja: {total}/{parts}");
            for (var k = 1; k < r.Count; k++)
                if (r[k] > r[k - 1]) throw new Exception($"reszta nie na poczatku: {total}/{parts}");
            checkedCases++;
        }
        await Assert.That(checkedCases).IsEqualTo(5000);
    }
}
