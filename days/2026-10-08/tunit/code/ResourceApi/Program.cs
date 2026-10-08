using ResourceApi;

// Uruchomienie reczne: dotnet run --project ResourceApi -- --urls http://127.0.0.1:5100
// Zaklada wystawce pod http://127.0.0.1:5000 (dotnet run --project IssuerApi -- --urls http://127.0.0.1:5000).
ResourceApp.Build(args, new ResourceOptions("http://127.0.0.1:5000", TimeSpan.FromSeconds(30))).Run();
