using Aspire.Hosting;
using Aspire.Hosting.Testing;
using System.Text.Json;

// Dwie rzeczy do zweryfikowania NAPRAWDĘ (nie na wiarę z dokumentacji):
//
// 1. AddParameter("pg-password", secret: true) faktycznie da się nakarmić z zewnątrz
//    (tu: przez argumenty "Parameters:pg-password=...", ten sam mechanizm co w teście
//    Config.Verify z wydania #4 - w code/README.md pokazujemy równolegle, że DOKŁADNIE
//    ta sama zmienna konfiguracyjna działa też z prawdziwego pliku user-secrets przy
//    zwykłym "dotnet run").
// 2. WithDataVolume() na kontenerze Postgresa: dane przeżywają PEŁNE zatrzymanie
//    i ponowne uruchomienie AppHosta (nowy kontener, ten sam nazwany wolumin Docker).
//    Dowód: wstawiamy notatkę w PIERWSZYM uruchomieniu AppHosta, zatrzymujemy AppHost
//    (co usuwa kontener - "docker ps -a" go nie pokaże), startujemy AppHost DRUGI RAZ
//    od zera i sprawdzamy, czy notatka nadal tam jest.

int failures = 0;
void Check(string name, bool ok, string? detail = null)
{
    Console.WriteLine($"[{(ok ? "PASS" : "FAIL")}] {name}{(detail is null ? "" : $" ({detail})")}");
    if (!ok) failures++;
}

// Wartość czysto demonstracyjna - nigdy prawdziwy sekret. Podana przez argumenty testu,
// dokładnie jak "Parameters:cache-password=..." w Config.Verify (wydanie #4).
const string DemoPassword = "prasowka-demo-pw-2026-09-30";
var marker = "prasowka-nota-" + Guid.NewGuid().ToString("N")[..8];

using var cts = new CancellationTokenSource(TimeSpan.FromMinutes(6));
var ct = cts.Token;

Console.WriteLine("=== Przebieg #1: start AppHost, INSERT notatki, zatrzymanie AppHosta ===");
{
    var appHost = await DistributedApplicationTestingBuilder.CreateAsync<Projects.AppHost>(
        ["Logging:LogLevel:Default=Warning", $"Parameters:pg-password={DemoPassword}"], ct);
    await using var app = await appHost.BuildAsync(ct);
    await app.StartAsync(ct);

    try
    {
        await app.ResourceNotifications.WaitForResourceHealthyAsync("notes-api", ct);
        Console.WriteLine("notes-api = Healthy (kontener Postgres 'pg' też musiał wystartować)");

        using var http = app.CreateHttpClient("notes-api");

        var info = await http.GetStringAsync("/notes-info", ct);
        Console.WriteLine("GET /notes-info -> " + info);
        var infoJson = JsonDocument.Parse(info).RootElement;
        Check("Aspire wstrzyknęło connection string z hasłem z parametru (nie z kodu)",
            infoJson.GetProperty("hasPassword").GetBoolean());
        Check("connection string wskazuje na kontener (Host=...)",
            infoJson.GetProperty("hasHost").GetBoolean());
        Check("connection string wskazuje na bazę notesdb",
            infoJson.GetProperty("hasDatabase").GetBoolean());

        var post = await http.PostAsync("/notes",
            new StringContent($"{{\"text\":\"{marker}\"}}", System.Text.Encoding.UTF8, "application/json"), ct);
        Check("POST /notes -> 200", post.IsSuccessStatusCode, post.StatusCode.ToString());
        Console.WriteLine("POST /notes body -> " + await post.Content.ReadAsStringAsync(ct));
    }
    finally
    {
        Console.WriteLine("--- Zatrzymywanie AppHost #1 (Aspire zdejmuje kontener Postgres, wolumin ZOSTAJE) ---");
        await app.StopAsync(CancellationToken.None);
    }
}

Console.WriteLine();
Console.WriteLine("=== Przebieg #2: NOWY AppHost od zera, sprawdzamy czy notatka przeżyła ===");
{
    var appHost = await DistributedApplicationTestingBuilder.CreateAsync<Projects.AppHost>(
        ["Logging:LogLevel:Default=Warning", $"Parameters:pg-password={DemoPassword}"], ct);
    await using var app = await appHost.BuildAsync(ct);
    await app.StartAsync(ct);

    try
    {
        await app.ResourceNotifications.WaitForResourceHealthyAsync("notes-api", ct);
        Console.WriteLine("notes-api = Healthy (NOWY kontener Postgres, ten sam nazwany wolumin)");

        using var http = app.CreateHttpClient("notes-api");

        var listBody = await http.GetStringAsync("/notes", ct);
        Console.WriteLine("GET /notes -> " + listBody);
        var notes = JsonDocument.Parse(listBody).RootElement;
        var found = notes.EnumerateArray().Any(n => n.GetProperty("text").GetString() == marker);
        Check("notatka z Przebiegu #1 PRZEŻYŁA restart AppHosta (WithDataVolume działa)", found, marker);

        var post2 = await http.PostAsync("/notes",
            new StringContent("{\"text\":\"druga-notatka-po-restarcie\"}", System.Text.Encoding.UTF8, "application/json"), ct);
        Check("zapis nadal działa po restarcie (POST /notes -> 200)", post2.IsSuccessStatusCode, post2.StatusCode.ToString());
    }
    finally
    {
        Console.WriteLine("--- Zatrzymywanie AppHost #2 ---");
        await app.StopAsync(CancellationToken.None);
    }
}

Console.WriteLine();
Console.WriteLine(failures == 0 ? "WSZYSTKO OK" : $"BŁĘDY: {failures}");
Console.WriteLine("UWAGA: wolumin danych Postgresa NIE jest usuwany automatycznie (to sens WithDataVolume) -");
Console.WriteLine("posprzątaj go ręcznie: patrz code/README.md, sekcja 'Porządek'.");
return failures == 0 ? 0 : 1;
