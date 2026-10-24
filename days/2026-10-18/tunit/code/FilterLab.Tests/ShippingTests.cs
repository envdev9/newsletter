using FilterLab.Core;

namespace FilterLab.Tests;

public class ShippingTests
{
    [Test]
    [Property("Area", "shipping")]
    public async Task Standard_do_kilograma_kosztuje_10()
    {
        await Assert.That(Shipping.Cost("standard", 1m)).IsEqualTo(10m);
    }

    [Test]
    [Property("Area", "shipping")]
    public async Task Standard_ponad_kilogram_doplata_2_za_kg()
    {
        await Assert.That(Shipping.Cost("standard", 3m)).IsEqualTo(14m);
    }

    [Test]
    public async Task Waga_niedodatnia_rzuca()
    {
        await Assert.That(() => Shipping.Cost("standard", 0m)).Throws<ArgumentOutOfRangeException>();
    }

    // Wlasciwie testowany "express" -- ale wylaczony, zeby pokazac w pokryciu niepokryta galaz.
    // (uruchamiany tylko przez filtr)
    [Test, Explicit]
    [Property("Area", "shipping")]
    public async Task Express_kosztuje_25_plus_5_za_kg()
    {
        await Assert.That(Shipping.Cost("express", 2m)).IsEqualTo(35m);
    }

    // Celowo czerwony -- do sprawdzenia, jak wyglada TRX przy porazce.
    [Test, Explicit]
    [Property("Kind", "Failing")]
    public async Task Celowa_porazka_z_outputem()
    {
        TestContext.Current!.Output.WriteLine("output-przed-porazka");
        await Assert.That(Shipping.Cost("standard", 1m)).IsEqualTo(999m);
    }
}

public class ValidationTests
{
    [Test]
    public async Task Nieznana_metoda_rzuca()
    {
        await Assert.That(() => Shipping.Cost("gołąb", 1m)).Throws<ArgumentException>();
    }
}
