var builder = DistributedApplication.CreateBuilder(args);

// catalog jest "gotowy" dopiero, gdy jego GET /health zwróci 200 (patrz WarmupHealthCheck).
var catalog = builder.AddProject<Projects.CatalogApi>("catalog")
    .WithHttpHealthCheck("/health");

// WithReference: wstrzyknij adres catalog do store (konfiguracja services__catalog__http__0)
//                i włącz rozwiązywanie "http://catalog" w HttpClient.
// WaitFor:       nie startuj store, dopóki catalog nie jest zdrowy (nie tylko uruchomiony).
builder.AddProject<Projects.StoreApi>("store")
    .WithReference(catalog)
    .WaitFor(catalog);

builder.Build().Run();
