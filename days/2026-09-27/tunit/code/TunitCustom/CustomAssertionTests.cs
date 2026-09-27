using TUnit.Assertions.Exceptions;

namespace TunitCustom;

public class CustomAssertionTests
{
    [Test]
    public async Task PoprawnyIban_PrzechodziRecznaAsercje()
    {
        await Assert.That(new Iban("PL61109010140000071219812874")).HasValidChecksum();
    }

    [Test]
    public async Task PoprawnyIban_PrzechodziAsercjeWygenerowana()
    {
        await Assert.That(new Iban("DE89370400440532013000")).IsFromCountry("de");
    }

    [Test]
    public async Task AsercjeMoznaLaczyc_And()
    {
        await Assert.That(new Iban("GB82WEST12345698765432"))
            .HasValidChecksum()
            .And.IsFromCountry("GB");
    }

    [Test]
    public async Task BlednyIban_RzucaAssertionException_ZNaszymKomunikatem()
    {
        var ex = await Assert.ThrowsAsync<AssertionException>(async () =>
            await Assert.That(new Iban("PL00109010140000071219812874")).HasValidChecksum());

        Console.WriteLine("--- komunikat (reczna asercja) ---");
        Console.WriteLine(ex!.Message);

        await Assert.That(ex.Message).Contains("suma kontrolna");
        await Assert.That(ex.Message).Contains("to have a valid IBAN checksum");
    }

    [Test]
    public async Task ZlyKraj_KomunikatZGeneratora()
    {
        var ex = await Assert.ThrowsAsync<AssertionException>(async () =>
            await Assert.That(new Iban("PL61109010140000071219812874")).IsFromCountry("DE"));

        Console.WriteLine("--- komunikat (wygenerowana asercja) ---");
        Console.WriteLine(ex!.Message);

        await Assert.That(ex.Message).Contains("to be issued in");
    }
}
