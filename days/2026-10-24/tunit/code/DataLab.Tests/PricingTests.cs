using DataLab.Core;
using TUnit.Assertions;
using TUnit.Core;

namespace DataLab.Tests;

[ClassConstructor<DiClassConstructor>]
public class PricingTests(PricingService pricing, RequestScopeMarker marker)
{
    [Test]
    [CsvCases("cases.csv")]
    [DisplayName("Total(net=$net, tier=$tier) = $expected")]
    public async Task Total_zgodny_z_tabela(decimal net, string tier, decimal expected)
    {
        await Assert.That(pricing.Total(net, tier)).IsEqualTo(expected);
    }

    [Test]
    public async Task Nieznany_poziom_rzuca()
    {
        await Assert.That(() => pricing.Total(10m, "diamond")).Throws<ArgumentException>();
    }

    [Test]
    public async Task Kazdy_test_ma_swoj_scope()
    {
        Console.WriteLine($"scope-marker-id={marker.Id} created-w-chwili-testu={RequestScopeMarker.Created} disposed-w-chwili-testu={RequestScopeMarker.Disposed}");
        await Assert.That(marker.Id).IsGreaterThan(0);
    }

    [After(Class)]
    public static void Raport()
    {
        Console.WriteLine($"RAPORT created={RequestScopeMarker.Created} disposed={RequestScopeMarker.Disposed} generateCalls={CsvCasesAttribute.GenerateCalls}");
    }
}
