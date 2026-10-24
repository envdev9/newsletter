namespace TunitFixtures;

// Testy asercji na licznikach wspoldzielenia. [DependsOn] gwarantuje, ze sprawdzamy
// dopiero PO tym, jak testy z SharedStateTests zebraly identyfikatory.
public class SharingAssertionTests
{
    [Test]
    [DependsOn(typeof(SessionA), nameof(SessionA.Pierwszy))]
    [DependsOn(typeof(SessionA), nameof(SessionA.Drugi))]
    [DependsOn(typeof(SessionB), nameof(SessionB.InnaKlasaWidziTeSamaInstancje))]
    public async Task PerTestSession_JednaInstancjaDlaWszystkich()
    {
        await Assert.That(SessionA.SeenIds.Distinct().Count()).IsEqualTo(1);
    }

    [Test]
    [DependsOn(typeof(PerClassA), nameof(PerClassA.T1))]
    [DependsOn(typeof(PerClassA), nameof(PerClassA.T2))]
    [DependsOn(typeof(PerClassB), nameof(PerClassB.T1))]
    [DependsOn(typeof(PerClassB), nameof(PerClassB.T2))]
    public async Task PerClass_InstancjaNaKlase()
    {
        await Assert.That(PerClassA.Ids.Distinct().Count()).IsEqualTo(1);
        await Assert.That(PerClassB.Ids.Distinct().Count()).IsEqualTo(1);
        await Assert.That(PerClassA.Ids.Intersect(PerClassB.Ids).Any()).IsFalse();
    }

    [Test]
    [DependsOn(typeof(KeyedA), nameof(KeyedA.Test))]
    [DependsOn(typeof(KeyedB), nameof(KeyedB.Test))]
    [DependsOn(typeof(KeyedC), nameof(KeyedC.Test))]
    public async Task Keyed_TenSamKluczTaSamaInstancja()
    {
        await Assert.That(KeyedA.Ids.Distinct().Count()).IsEqualTo(1);   // A i B (tenant-1)
        await Assert.That(KeyedC.Ids.Distinct().Count()).IsEqualTo(1);   // tenant-2
        await Assert.That(KeyedA.Ids.Intersect(KeyedC.Ids).Any()).IsFalse();
    }

    [Test]
    [DependsOn(typeof(NotSharedTests), nameof(NotSharedTests.A))]
    [DependsOn(typeof(NotSharedTests), nameof(NotSharedTests.B))]
    public async Task None_SwiezaInstancjaNaTest()
    {
        await Assert.That(NotSharedTests.Ids.Distinct().Count()).IsEqualTo(2);
    }
}
