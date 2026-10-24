var builder = DistributedApplication.CreateBuilder(args);

// Jeden zasób: nasze API. Aspire samo wie, jak je zbudować i odpalić,
// bo AppHost ma ProjectReference do DemoApi.csproj - stąd source-generated
// typ Projects.DemoApi (patrz obj/AppHost.csproj.nuget.g.props -> generator).
builder.AddProject<Projects.DemoApi>("api");

builder.Build().Run();
