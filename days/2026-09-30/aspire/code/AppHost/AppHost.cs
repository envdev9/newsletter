var builder = DistributedApplication.CreateBuilder(args);

// Hasło administratora Postgresa NIE jest wpisane w kodzie ani w appsettings.json
// (bo appsettings.json trafia do repo, publicznego). AddParameter(secret: true) czyta
// je z konfiguracji pod kluczem "Parameters:pg-password" - a tę wartość dostarcza
// dotnet user-secrets (patrz code/README.md: `dotnet user-secrets set`).
// Jeśli sekret nie jest ustawiony, AppHost i tak wystartuje (Aspire samo wygeneruje
// losowe hasło zastępcze) - ale wtedy NIE jest to hasło, które wpisaliśmy ręcznie.
var pgPassword = builder.AddParameter("pg-password", secret: true);

// AddPostgres: prawdziwy kontener (obraz wg PostgresContainerImageTags w Aspire
// 13.5.2), nie atrapa. WithDataVolume() podpina NAZWANY wolumin Docker pod
// /var/lib/postgresql/data - w odróżnieniu od anonimowego woluminu efemerycznego,
// ten PRZEŻYWA "docker rm" kontenera. Nazwa woluminu jest deterministyczna
// (zależy od nazwy projektu AppHost + nazwy zasobu "pg"), więc kolejne uruchomienia
// tego samego AppHosta podłączają się pod te same dane.
var pg = builder.AddPostgres("pg", password: pgPassword)
    .WithDataVolume();

// AddDatabase: logiczna baza "notesdb" w tym samym serwerze Postgres. WithReference
// wstrzykuje "ConnectionStrings:notesdb" do notes-api (host, port, hasło, nazwa bazy -
// wszystko naraz, tak jak connection string dla Redis w wydaniu #5).
var db = pg.AddDatabase("notesdb");

var api = builder.AddProject<Projects.NotesApi>("notes-api")
    .WithReference(db)
    .WaitFor(db)
    .WithHttpHealthCheck("/health");

builder.Build().Run();
