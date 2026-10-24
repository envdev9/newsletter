using Npgsql;

var builder = WebApplication.CreateBuilder(args);

// Zanim NpgsqlDataSource go skonsumuje, zapamiętujemy surowy connection string
// wstrzyknięty przez Aspire - żeby w /notes-info pokazać jego KSZTAŁT (host, ssl mode),
// nigdy hasło.
var rawConnectionString = builder.Configuration.GetConnectionString("notesdb");

// Aspire.Npgsql: rejestruje NpgsqlDataSource skonfigurowany connection stringiem,
// który Aspire wstrzyknęło przez WithReference(db) - klucz "ConnectionStrings:notesdb"
// musi zgadzać się z nazwą zasobu z pg.AddDatabase("notesdb") w AppHost.
builder.AddNpgsqlDataSource(connectionName: "notesdb");

var app = builder.Build();

app.MapGet("/health", () => "Healthy");

// Tworzymy tabelę przy starcie, jeśli jeszcze nie istnieje - to jedyny "schema
// management" w tym przykładzie (celowo bez EF Core/migracji, żeby nie rozmywać
// tematu: kontener Postgresa + trwałość danych między restartami).
using (var scope = app.Services.CreateScope())
{
    await using var initConn = await scope.ServiceProvider
        .GetRequiredService<NpgsqlDataSource>()
        .OpenConnectionAsync();
    await using var createTable = new NpgsqlCommand(
        "CREATE TABLE IF NOT EXISTS notes (id SERIAL PRIMARY KEY, text TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());",
        initConn);
    await createTable.ExecuteNonQueryAsync();
}

// Zapis notatki - INSERT ... RETURNING id, żeby dowieźć wygenerowane ID z powrotem.
app.MapPost("/notes", async (NoteInput input, NpgsqlDataSource db) =>
{
    await using var conn = await db.OpenConnectionAsync();
    await using var cmd = new NpgsqlCommand(
        "INSERT INTO notes (text) VALUES (@text) RETURNING id, created_at;", conn);
    cmd.Parameters.AddWithValue("text", input.Text);
    await using var reader = await cmd.ExecuteReaderAsync();
    await reader.ReadAsync();
    var id = reader.GetInt32(0);
    var createdAt = reader.GetDateTime(1);
    return Results.Ok(new { id, text = input.Text, createdAt });
});

// Lista wszystkich notatek - dowód, że dane naprawdę leżą w Postgresie, nie w pamięci
// procesu (po restarcie notes-api, ta lista powinna być identyczna - jeśli wolumin
// przeżył, a kontener nie).
app.MapGet("/notes", async (NpgsqlDataSource db) =>
{
    await using var conn = await db.OpenConnectionAsync();
    await using var cmd = new NpgsqlCommand(
        "SELECT id, text, created_at FROM notes ORDER BY id;", conn);
    await using var reader = await cmd.ExecuteReaderAsync();
    var notes = new List<object>();
    while (await reader.ReadAsync())
    {
        notes.Add(new
        {
            id = reader.GetInt32(0),
            text = reader.GetString(1),
            createdAt = reader.GetDateTime(2),
        });
    }
    return Results.Ok(notes);
});

// Kształt connection stringa wstrzykniętego przez Aspire - BEZ wartości hasła.
app.MapGet("/notes-info", () => Results.Ok(new
{
    hasPassword = rawConnectionString?.Contains("Password=", StringComparison.OrdinalIgnoreCase) ?? false,
    hasHost = rawConnectionString?.Contains("Host=", StringComparison.OrdinalIgnoreCase) ?? false,
    hasDatabase = rawConnectionString?.Contains("Database=notesdb", StringComparison.OrdinalIgnoreCase) ?? false,
}));

app.Run();

record NoteInput(string Text);
