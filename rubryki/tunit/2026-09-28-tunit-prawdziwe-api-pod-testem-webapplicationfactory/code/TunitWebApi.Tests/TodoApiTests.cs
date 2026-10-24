using System.Net;
using System.Net.Http.Json;

namespace TunitWebApi.Tests;

/// <summary>
/// Odpowiednik xUnitowej klasy z "IClassFixture&lt;WebApplicationFactory&lt;Program&gt;&gt;".
/// [ClassDataSource&lt;T&gt;(Shared = SharedType.PerClass)] tworzy TodoApiFixture RAZ na tę
/// klasę (jeden realny TestServer, jeden HttpClient) i współdzieli go między wszystkimi
/// testami poniżej — dokładnie tak jak IClassFixture w xUnit.
/// </summary>
[ClassDataSource<TodoApiFixture>(Shared = SharedType.PerClass)]
public class TodoApiTests(TodoApiFixture fixture)
{
    [Test]
    public async Task Post_TworzyTodo_ZwracaCreatedZLokalizacja()
    {
        var response = await fixture.Client.PostAsJsonAsync("/todos", new CreateTodoRequest("Kupic mleko"));

        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.Created);
        await Assert.That(response.Headers.Location).IsNotNull();

        var todo = await response.Content.ReadFromJsonAsync<Todo>();
        await Assert.That(todo!.Title).IsEqualTo("Kupic mleko");
        await Assert.That(todo.Done).IsFalse();
    }

    [Test]
    public async Task Get_PoUtworzeniu_ZwracaToSamoZadanie()
    {
        var created = await fixture.Client.PostAsJsonAsync("/todos", new CreateTodoRequest("Ugotowac obiad"));
        var createdTodo = await created.Content.ReadFromJsonAsync<Todo>();

        var response = await fixture.Client.GetAsync($"/todos/{createdTodo!.Id}");

        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.OK);
        var fetched = await response.Content.ReadFromJsonAsync<Todo>();
        await Assert.That(fetched).IsEqualTo(createdTodo);
    }

    [Test]
    public async Task Get_NieistniejacyId_Zwraca404()
    {
        var response = await fixture.Client.GetAsync("/todos/999999");

        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.NotFound);
    }

    [Test]
    public async Task Post_PustyTytul_Zwraca400()
    {
        var response = await fixture.Client.PostAsJsonAsync("/todos", new CreateTodoRequest(""));

        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.BadRequest);
    }

    [Test]
    public async Task Delete_UsuwaWlasnyRekord_PotemGet404()
    {
        var created = await fixture.Client.PostAsJsonAsync("/todos", new CreateTodoRequest("Do usuniecia"));
        var todo = await created.Content.ReadFromJsonAsync<Todo>();

        var deleteResponse = await fixture.Client.DeleteAsync($"/todos/{todo!.Id}");
        await Assert.That(deleteResponse.StatusCode).IsEqualTo(HttpStatusCode.NoContent);

        var getResponse = await fixture.Client.GetAsync($"/todos/{todo.Id}");
        await Assert.That(getResponse.StatusCode).IsEqualTo(HttpStatusCode.NotFound);
    }
}
