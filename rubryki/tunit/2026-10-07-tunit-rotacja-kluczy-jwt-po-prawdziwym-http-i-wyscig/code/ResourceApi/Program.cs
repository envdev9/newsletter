using ResourceApi;

// Uruchomienie samodzielne: dotnet run --project ResourceApi -- --Authority http://127.0.0.1:5000
var authority = args.SkipWhile(a => a != "--Authority").Skip(1).FirstOrDefault() ?? "http://127.0.0.1:5000";
ResourceApp.Build(args, new ResourceOptions(authority, TimeSpan.FromHours(12), TimeSpan.FromMinutes(5))).Run();
