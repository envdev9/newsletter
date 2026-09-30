using System.Net;
using System.Net.Http.Json;

namespace TunitWebApi.Tests;

/// <summary>
/// Druga, niezalezna klasa testowa wskazujaca na TEN SAM typ fixture'a co TodoApiTests,
/// z tym samym Shared = SharedType.PerTestSession. Jesli PerTestSession dziala tak jak
/// deklaruje TUnit, obie klasy dostana DOKLADNIE TEN SAM WebApplicationFactory&lt;Program&gt;
/// (jeden TestServer, jeden proces hosta) -- zmierzone w AssemblyHooks.cs.
///
/// Testuje inny zasob (/notes) niz TodoApiTests (/todos) -- to swiadomy wybor: dwie klasy
/// dzielace jeden host musza dzielic tez odpowiedzialnosc za to, zeby nie deptac sobie po
/// stanie. Gdyby obie klasy testowaly /todos, "swoj" rekord po Id nadal byloby bezpieczne,
/// ale osobne zasoby czynia separacje jawna i czytelna dla kogos, kto pierwszy raz widzi
/// PerTestSession.
/// </summary>
[ClassDataSource<TodoApiFixture>(Shared = SharedType.PerTestSession)]
public class NotesApiTests(TodoApiFixture fixture)
{
    [Test]
    public async Task Post_TworzyNotatke_ZwracaCreatedZLokalizacja()
    {
        var response = await fixture.Client.PostAsJsonAsync("/notes", new CreateNoteRequest("Zadzwonic do klienta"));

        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.Created);
        await Assert.That(response.Headers.Location).IsNotNull();

        var note = await response.Content.ReadFromJsonAsync<Note>();
        await Assert.That(note!.Content).IsEqualTo("Zadzwonic do klienta");
    }

    [Test]
    public async Task Get_PoUtworzeniu_ZwracaToSamaNotatke()
    {
        var created = await fixture.Client.PostAsJsonAsync("/notes", new CreateNoteRequest("Wyslac fakture"));
        var createdNote = await created.Content.ReadFromJsonAsync<Note>();

        var response = await fixture.Client.GetAsync($"/notes/{createdNote!.Id}");

        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.OK);
        var fetched = await response.Content.ReadFromJsonAsync<Note>();
        await Assert.That(fetched).IsEqualTo(createdNote);
    }

    [Test]
    public async Task Get_NieistniejacyId_Zwraca404()
    {
        var response = await fixture.Client.GetAsync("/notes/999999");

        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.NotFound);
    }

    [Test]
    public async Task Post_PustaTresc_Zwraca400()
    {
        var response = await fixture.Client.PostAsJsonAsync("/notes", new CreateNoteRequest(""));

        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.BadRequest);
    }

    [Test]
    public async Task ZglaszaInstanceIdHosta_DoWspolnegoRaportu()
    {
        var response = await fixture.Client.GetAsync("/instance-id");
        var instanceId = await response.Content.ReadFromJsonAsync<Guid>();

        InstanceIdObservations.Record(nameof(NotesApiTests), instanceId);

        await Assert.That(instanceId).IsNotEqualTo(Guid.Empty);
    }
}
