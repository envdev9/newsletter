var builder = WebApplication.CreateBuilder(args);
builder.Services.AddSingleton<ITodoStore, InMemoryTodoStore>();
builder.Services.AddSingleton<INoteStore, InMemoryNoteStore>();

var app = builder.Build();

// Wygenerowany RAZ, gdy proces hosta startuje (top-level statements uruchamiaja sie raz na
// AppHost). Pozwala PO STRONIE SERWERA zmierzyc, czy dwie rozne klasy testowe faktycznie
// rozmawiaja z TYM SAMYM hostem (SharedType.PerTestSession), czy kazda dostala swoj wlasny
// (SharedType.PerClass) -- bez zgadywania po logach fixture'a, patrz artykul.
var instanceId = Guid.NewGuid();
app.MapGet("/instance-id", () => Results.Ok(instanceId));

app.MapGet("/todos", (ITodoStore store) => Results.Ok(store.GetAll()));

app.MapGet("/todos/{id:int}", (int id, ITodoStore store) =>
    store.Get(id) is { } todo ? Results.Ok(todo) : Results.NotFound());

app.MapPost("/todos", (CreateTodoRequest request, ITodoStore store) =>
{
    if (string.IsNullOrWhiteSpace(request.Title))
    {
        return Results.ValidationProblem(new Dictionary<string, string[]>
        {
            ["title"] = ["Title jest wymagany."]
        });
    }

    var todo = store.Add(request.Title);
    return Results.Created($"/todos/{todo.Id}", todo);
});

app.MapDelete("/todos/{id:int}", (int id, ITodoStore store) =>
    store.Remove(id) ? Results.NoContent() : Results.NotFound());

app.MapGet("/notes", (INoteStore store) => Results.Ok(store.GetAll()));

app.MapGet("/notes/{id:int}", (int id, INoteStore store) =>
    store.Get(id) is { } note ? Results.Ok(note) : Results.NotFound());

app.MapPost("/notes", (CreateNoteRequest request, INoteStore store) =>
{
    if (string.IsNullOrWhiteSpace(request.Content))
    {
        return Results.ValidationProblem(new Dictionary<string, string[]>
        {
            ["content"] = ["Content jest wymagany."]
        });
    }

    var note = store.Add(request.Content);
    return Results.Created($"/notes/{note.Id}", note);
});

app.Run();

// Zabezpieczenie widocznosci niejawnej klasy Program dla WebApplicationFactory<Program> z
// osobnego projektu testow -- patrz wydanie #5 (2026-09-28), gdzie zmierzylismy, ze na tym
// SDK (10.0.400) jest to juz zbedne, ale zostawiamy defensywnie.
public partial class Program { }

public record Todo(int Id, string Title, bool Done);

public record CreateTodoRequest(string Title);

public interface ITodoStore
{
    Todo Add(string title);
    Todo? Get(int id);
    IReadOnlyList<Todo> GetAll();
    bool Remove(int id);
}

public class InMemoryTodoStore : ITodoStore
{
    private readonly List<Todo> _todos = [];
    private readonly Lock _lock = new();
    private int _nextId = 1;

    public Todo Add(string title)
    {
        lock (_lock)
        {
            var todo = new Todo(_nextId++, title, Done: false);
            _todos.Add(todo);
            return todo;
        }
    }

    public Todo? Get(int id)
    {
        lock (_lock)
        {
            return _todos.FirstOrDefault(t => t.Id == id);
        }
    }

    public IReadOnlyList<Todo> GetAll()
    {
        lock (_lock)
        {
            return _todos.ToList();
        }
    }

    public bool Remove(int id)
    {
        lock (_lock)
        {
            return _todos.RemoveAll(t => t.Id == id) > 0;
        }
    }
}

public record Note(int Id, string Content);

public record CreateNoteRequest(string Content);

public interface INoteStore
{
    Note Add(string content);
    Note? Get(int id);
    IReadOnlyList<Note> GetAll();
}

public class InMemoryNoteStore : INoteStore
{
    private readonly List<Note> _notes = [];
    private readonly Lock _lock = new();
    private int _nextId = 1;

    public Note Add(string content)
    {
        lock (_lock)
        {
            var note = new Note(_nextId++, content);
            _notes.Add(note);
            return note;
        }
    }

    public Note? Get(int id)
    {
        lock (_lock)
        {
            return _notes.FirstOrDefault(n => n.Id == id);
        }
    }

    public IReadOnlyList<Note> GetAll()
    {
        lock (_lock)
        {
            return _notes.ToList();
        }
    }
}
