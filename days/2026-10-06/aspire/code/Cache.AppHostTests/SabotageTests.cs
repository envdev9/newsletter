namespace Cache.AppHostTests;

/// <summary>
/// Test, który CELOWO się wywala (po tym, jak AppHost już działa). [Explicit] =>
/// TUnit nie odpala go w zwykłym "dotnet test"; trzeba go wskazać filtrem
/// (--treenode-filter po kategorii). Służy tylko do jednego pomiaru: czy po porażce
/// testu fixture jest zdisposowany, a kontener Redis posprzątany.
/// </summary>
[Explicit]
[Category("Sabotage")]
[ClassDataSource<RedisAppHostFixture>(Shared = SharedType.PerTestSession)]
public class SabotageTests(RedisAppHostFixture fixture)
{
    [Test]
    public async Task Fails_On_Purpose_With_Running_Container()
    {
        using var http = fixture.CreateHttpClient();
        var body = await http.GetStringAsync("/health");
        await Assert.That(body).IsEqualTo("Healthy");

        Console.WriteLine("Kontenery w trakcie testu: " + string.Join(", ", RedisAppHostFixture.RunningRedisContainers()));
        throw new InvalidOperationException("Celowa porażka testu przy żywym kontenerze Redis.");
    }
}
