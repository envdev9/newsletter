namespace ReportingLab;

public class OutputTests
{
    [Test]
    public async Task Output_przez_TestContext()
    {
        TestContext.Current!.Output.WriteLine("linia przez TestContext.Output");
        Console.WriteLine("linia przez Console.WriteLine");
        var sum = Enumerable.Range(1, 3).Sum();
        await Assert.That(sum).IsEqualTo(6);
    }

    [Test]
    public async Task Artefakt_pliku()
    {
        var path = Path.Combine(Path.GetTempPath(), $"reportinglab-{Guid.NewGuid():N}.txt");
        await File.WriteAllTextAsync(path, "zawartosc artefaktu");
        TestContext.Current!.Output.AttachArtifact(new Artifact
        {
            File = new FileInfo(path),
            DisplayName = "raport testowy",
            Description = "plik z ciala testu"
        });
        await Assert.That(File.Exists(path)).IsTrue();
    }

    [Test]
    [Explicit]
    [Property("Kind", "Failing")]
    public async Task Test_ktory_pada_z_outputem()
    {
        TestContext.Current!.Output.WriteLine("ten output ma byc widoczny przy porazce");
        var sum = Enumerable.Range(1, 2).Sum();
        await Assert.That(sum).IsEqualTo(5);
    }
}
