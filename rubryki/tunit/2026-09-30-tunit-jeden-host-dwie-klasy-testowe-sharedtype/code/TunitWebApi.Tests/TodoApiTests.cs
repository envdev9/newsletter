using System.Net;
using System.Net.Http.Json;

namespace TunitWebApi.Tests;

/// <summary>
/// [ClassDataSource&lt;T&gt;(Shared = SharedType.PerTestSession)] -- w wydaniu #5 uzylismy
/// tu SharedType.PerClass (jeden host na TE klase). PerTestSession idzie o krok dalej:
/// jeden host na CALY przebieg testow, wspoldzielony takze z NotesApiTests ponizej, mimo
/// ze to dwie zupelnie oddzielne klasy testowe w tym samym zestawie.
///
/// Testy operuja wylacznie na wlasnym zasobie (/todos), nigdy na globalnym stanie serwera --
/// ta sama zasada co w wydaniu #5, tu jeszcze wazniejsza: skoro host jest teraz wspoldzielony
/// takze z NotesApiTests, kazda klasa musi trzymac sie swojej "piaskownicy" zasobow.
/// </summary>
[ClassDataSource<TodoApiFixture>(Shared = SharedType.PerTestSession)]
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

    [Test]
    public async Task ZglaszaInstanceIdHosta_DoWspolnegoRaportu()
    {
        var response = await fixture.Client.GetAsync("/instance-id");
        var instanceId = await response.Content.ReadFromJsonAsync<Guid>();

        InstanceIdObservations.Record(nameof(TodoApiTests), instanceId);

        await Assert.That(instanceId).IsNotEqualTo(Guid.Empty);
    }
}
