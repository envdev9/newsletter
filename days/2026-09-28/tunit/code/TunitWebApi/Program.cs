var builder = WebApplication.CreateBuilder(args);
builder.Services.AddSingleton<ITodoStore, InMemoryTodoStore>();

var app = builder.Build();

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

app.Run();

// Klasyczna rada dla minimal API + WebApplicationFactory: top-level statements generują
// niejawną klasę `Program`, która bywała `internal` (WebApplicationFactory<Program> z innego
// assembly rzucał wtedy CS0122). Ten `partial class Program` to bezpieczne zabezpieczenie —
// scala się z niejawną deklaracją i wymusza `public`. Zostawiamy go defensywnie, choć na tym
// SDK (10.0.400) zmierzyliśmy, że nie jest to już konieczne (patrz artykuł).
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
