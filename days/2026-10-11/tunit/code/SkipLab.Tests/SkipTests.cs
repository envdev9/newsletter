using SkipLab;

namespace SkipLab.Tests;

public class SkipTests
{
    [Test]
    public async Task Zwykly_test_zawsze_biegnie()
        => await Assert.That(Slugifier.Slugify(" Hello, World! ")).IsEqualTo("hello-world");

    // 1. Statyczne pominiecie: powod trafia do raportu.
    [Test]
    [Skip("zablokowane do naprawy slugow dla znakow spoza ASCII (ticket DEMO-1)")]
    public async Task Statycznie_pominiety()
        => await Assert.That(Slugifier.Slugify("Zażółć")).IsEqualTo("zazolc");

    // 2. Warunkowe pominiecie wlasnym atrybutem (SkipAttribute.ShouldSkip).
    [Test]
    [RequiresEnvVar(DbSettings.VariableName)]
    public async Task Wymaga_zmiennej_srodowiskowej()
        => await Assert.That(DbSettings.ConnectionString()).IsNotNull();

    [Test]
    [LinuxOnly]
    public async Task Tylko_linux_system_plikow_rozroznia_wielkosc_liter()
        => await Assert.That(FsProbe.IsCaseSensitive(Path.GetTempPath())).IsTrue();

    // 3. Pominiecie z wnetrza testu: decyzja zalezy od czegos, co wiadomo dopiero w trakcie.
    [Test]
    public async Task Pominiety_w_trakcie()
    {
        var caseSensitive = FsProbe.IsCaseSensitive(Path.GetTempPath());
        if (caseSensitive)
        {
            Skip.Test("katalog tymczasowy rozroznia wielkosc liter - scenariusz case-insensitive nie do sprawdzenia");
        }

        await Assert.That(caseSensitive).IsFalse();
    }

    // 4. [Explicit]: nie biegnie w zwyklym przebiegu, tylko gdy filtr wskaze go wprost.
    [Test]
    [Explicit]
    public async Task Droga_operacja_tylko_na_zadanie()
    {
        await Task.Delay(50);
        await Assert.That(Slugifier.Slugify("A B")).IsEqualTo("a-b");
    }
}
