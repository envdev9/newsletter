namespace ReportingLab;

// Klucz "db" dzielony przez DWIE klasy: testy z kluczem "db" nie nakladaja sie ani w klasie, ani miedzy klasami.
[NotInParallel("db")]
public class DbWritersA
{
    [Test] public async Task A1() { await Probe.Run("db"); }
    [Test] public async Task A2() { await Probe.Run("db"); }
    [Test] public async Task A3() { await Probe.Run("db"); }
}

[NotInParallel("db")]
public class DbWritersB
{
    [Test] public async Task B1() { await Probe.Run("db"); }
    [Test] public async Task B2() { await Probe.Run("db"); }
}

// Inny klucz: serializuje sie sam ze soba, ale moze nakladac sie z "db".
[NotInParallel("cache")]
public class CacheWriters
{
    [Test] public async Task C1() { await Probe.Run("cache"); }
    [Test] public async Task C2() { await Probe.Run("cache"); }
}

// Bez ograniczen: biegna rownolegle.
public class Free
{
    [Test] public async Task F1() { await Probe.Run("free"); }
    [Test] public async Task F2() { await Probe.Run("free"); }
    [Test] public async Task F3() { await Probe.Run("free"); }
    [Test] public async Task F4() { await Probe.Run("free"); }
}
