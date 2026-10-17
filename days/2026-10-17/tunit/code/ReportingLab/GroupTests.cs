namespace ReportingLab;

// Eksperyment z [ParallelGroup]: dwie grupy po dwa testy.
public class GroupOne
{
    [Test, ParallelGroup("g1")] public async Task G1a() { await Probe.Run("g1"); }
    [Test, ParallelGroup("g1")] public async Task G1b() { await Probe.Run("g1"); }
}

public class GroupTwo
{
    [Test, ParallelGroup("g2")] public async Task G2a() { await Probe.Run("g2"); }
    [Test, ParallelGroup("g2")] public async Task G2b() { await Probe.Run("g2"); }
}
