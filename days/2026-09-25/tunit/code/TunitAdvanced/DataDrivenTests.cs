namespace TunitAdvanced;

public class DataDrivenTests
{
    // 1) [Arguments] - dane inline; kazdy atrybut = osobny przypadek testowy.
    [Test]
    [Arguments(100.00, 10, 90.00)]
    [Arguments(19.99, 0, 19.99)]
    [Arguments(19.99, 100, 0.00)]
    [Arguments(10.05, 50, 5.03, DisplayName = "polowa z zaokragleniem 5.025 -> 5.03")]
    public async Task ApplyDiscount_Arguments(double price, int percent, double expected)
    {
        var result = PriceCalculator.ApplyDiscount((decimal)price, percent);

        await Assert.That(result).IsEqualTo((decimal)expected);
    }

    // 2) [MethodDataSource] - dane z metody statycznej; nadaje sie do danych zlozonych/obliczanych.
    //    Zwracamy Func<tuple>, zeby kazdy test dostal SWIEZY obiekt (rekomendacja TUnit).
    public static IEnumerable<Func<(decimal Price, int Percent, decimal Expected)>> DiscountCases()
    {
        yield return () => (200m, 25, 150m);
        yield return () => (0.99m, 50, 0.50m);
        yield return () => (1234.56m, 15, 1049.38m);
    }

    [Test]
    [MethodDataSource(nameof(DiscountCases))]
    public async Task ApplyDiscount_MethodDataSource(decimal price, int percent, decimal expected)
    {
        await Assert.That(PriceCalculator.ApplyDiscount(price, percent)).IsEqualTo(expected);
    }

    // 3) Zle dane tez sa "danymi" - wyjatek per przypadek.
    [Test]
    [Arguments(-1)]
    [Arguments(101)]
    public async Task ApplyDiscount_PoprawnyZakres(int percent)
    {
        await Assert.That(() => PriceCalculator.ApplyDiscount(10m, percent))
            .Throws<ArgumentOutOfRangeException>();
    }

    // 4) Kombinatoryka: [Matrix] generuje iloczyn kartezjanski (2 x 3 = 6 testow).
    [Test]
    [MatrixDataSource]
    public async Task ApplyDiscount_NigdyNieWiekszaNizCena(
        [Matrix(10.0, 99.99)] double price,
        [Matrix(0, 50, 100)] int percent)
    {
        var result = PriceCalculator.ApplyDiscount((decimal)price, percent);

        await Assert.That(result).IsLessThanOrEqualTo((decimal)price);
    }
}
