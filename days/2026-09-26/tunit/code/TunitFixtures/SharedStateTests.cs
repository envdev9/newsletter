using System.Collections.Concurrent;

namespace TunitFixtures;

// Scenariusz 1: PerTestSession -- jedna instancja na CALY przebieg, wstrzykiwana konstruktorem.
// [ClassDataSource] stoi na klasie, a fixture trafia do parametru konstruktora.
[ClassDataSource<FakeDatabase>(Shared = SharedType.PerTestSession)]
public class SessionA(FakeDatabase db)
{
    public static ConcurrentBag<int> SeenIds { get; } = new();

    [Test]
    public async Task Pierwszy()
    {
        SeenIds.Add(db.InstanceId);
        await Assert.That(db.IsReady).IsTrue();
    }

    [Test]
    public async Task Drugi()
    {
        SeenIds.Add(db.InstanceId);
        await Assert.That(db.IsReady).IsTrue();
    }
}

[ClassDataSource<FakeDatabase>(Shared = SharedType.PerTestSession)]
public class SessionB(FakeDatabase db)
{
    [Test]
    public async Task InnaKlasaWidziTeSamaInstancje()
    {
        SessionA.SeenIds.Add(db.InstanceId);
        await Assert.That(db.IsReady).IsTrue();
    }
}

// Scenariusz 2: PerClass -- jedna instancja na klase testowa.
[ClassDataSource<FakeDatabase>(Shared = SharedType.PerClass)]
public class PerClassA(FakeDatabase db)
{
    public static ConcurrentBag<int> Ids { get; } = new();

    [Test] public async Task T1() { Ids.Add(db.InstanceId); await Assert.That(db.IsReady).IsTrue(); }
    [Test] public async Task T2() { Ids.Add(db.InstanceId); await Assert.That(db.IsReady).IsTrue(); }
}

[ClassDataSource<FakeDatabase>(Shared = SharedType.PerClass)]
public class PerClassB(FakeDatabase db)
{
    public static ConcurrentBag<int> Ids { get; } = new();

    [Test] public async Task T1() { Ids.Add(db.InstanceId); await Assert.That(db.IsReady).IsTrue(); }
    [Test] public async Task T2() { Ids.Add(db.InstanceId); await Assert.That(db.IsReady).IsTrue(); }
}

// Scenariusz 3: Keyed -- ten sam klucz = ta sama instancja, nawet w roznych klasach.
[ClassDataSource<FakeDatabase>(Shared = SharedType.Keyed, Key = "tenant-1")]
public class KeyedA(FakeDatabase db)
{
    public static ConcurrentBag<int> Ids { get; } = new();

    [Test] public async Task Test() { Ids.Add(db.InstanceId); await Assert.That(db.IsReady).IsTrue(); }
}

[ClassDataSource<FakeDatabase>(Shared = SharedType.Keyed, Key = "tenant-1")]
public class KeyedB(FakeDatabase db)
{
    [Test] public async Task Test() { KeyedA.Ids.Add(db.InstanceId); await Assert.That(db.IsReady).IsTrue(); }
}

[ClassDataSource<FakeDatabase>(Shared = SharedType.Keyed, Key = "tenant-2")]
public class KeyedC(FakeDatabase db)
{
    public static ConcurrentBag<int> Ids { get; } = new();

    [Test] public async Task Test() { Ids.Add(db.InstanceId); await Assert.That(db.IsReady).IsTrue(); }
}

// Scenariusz 4: None -- swieza instancja dla kazdego testu. Tu [ClassDataSource] stoi na
// METODZIE, a fixture jest jej parametrem.
public class NotSharedTests
{
    public static ConcurrentBag<int> Ids { get; } = new();

    [Test]
    [ClassDataSource<FakeDatabase>(Shared = SharedType.None)]
    public async Task A(FakeDatabase db) { Ids.Add(db.InstanceId); await Assert.That(db.IsReady).IsTrue(); }

    [Test]
    [ClassDataSource<FakeDatabase>(Shared = SharedType.None)]
    public async Task B(FakeDatabase db) { Ids.Add(db.InstanceId); await Assert.That(db.IsReady).IsTrue(); }
}
