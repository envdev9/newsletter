var builder = DistributedApplication.CreateBuilder(args);

// 1a) Parametr czytany z konfiguracji ("Parameters:greeting"), bez wartości w kodzie.
//     Nie ustawisz - zasób dostanie stan ValueMissing (scenariusz B w Config.Verify).
var greeting = builder.AddParameter("greeting");

// 1b) UWAGA, pułapka: przeciążenie AddParameter(nazwa, WARTOŚĆ) to wartość STAŁA.
//     Konfiguracja "Parameters:fixed-text" NIE jest wtedy czytana (sprawdzone w Config.Verify).
var fixedText = builder.AddParameter("fixed-text", "stała z kodu");

// 2) Parametr-SEKRET: brak wartości w kodzie. Aspire szuka "Parameters:api-key"
//    w konfiguracji (user-secrets / zmienna środowiskowa Parameters__api-key / argument).
var apiKey = builder.AddParameter("api-key", secret: true);

// 3) Parametr "na życzenie": hasło do (nieistniejącej tu) bazy - do złożenia connection stringa.
var dbPassword = builder.AddParameter("db-password", secret: true);

var api = builder.AddProject<Projects.ConfigApi>("config-api")
    // WithEnvironment - trzy przeciążenia:
    .WithEnvironment("APP_MODE", "demo")                       // literał
    .WithEnvironment("GREETING", greeting)                     // parametr (IResourceBuilder<ParameterResource>)
    .WithEnvironment("FIXED_TEXT", fixedText)
    .WithEnvironment("API_KEY", apiKey)                        // sekret - ta sama składnia
    .WithEnvironment("DB_CONNECTION",                          // wyrażenie składane z parametrów
        ReferenceExpression.Create($"Host=db.local;Database=shop;Password={dbPassword}"))
    .WithEnvironment(ctx =>                                    // callback: dostęp do trybu uruchomienia
    {
        ctx.EnvironmentVariables["RUN_MODE"] = ctx.ExecutionContext.IsRunMode ? "run" : "publish";
    })
    .WithHttpHealthCheck("/health");

// AddExecutable: dowolny proces, nie tylko projekt .NET. Tu: sh wypisujący zmienne, które dostał.
builder.AddExecutable("env-printer", "sh", ".",
        "-c", "echo \"env-printer: GREETING=$GREETING KEY_LEN=${#API_KEY}\"; sleep 2")
    .WithEnvironment("GREETING", greeting)
    .WithEnvironment("API_KEY", apiKey);

builder.Build().Run();
