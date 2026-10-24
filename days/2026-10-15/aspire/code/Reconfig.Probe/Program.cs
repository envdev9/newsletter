using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Aspire.Hosting;
using Aspire.Hosting.Testing;

// Reconfig.Probe - co robi Aspire z TRWAŁYM kontenerem (ContainerLifetime.Persistent), gdy:
//   C) zmieni się konfiguracja zasobu między uruchomieniami AppHosta (zmienna środowiskowa, tag obrazu),
//   D) kontener zostanie usunięty z zewnątrz (docker rm), z WithDataVolume i bez.
//
//   dotnet run --project Reconfig.Probe
//
// Każdy krok to NOWY proces potomek ("child <write|read> <wartość> [Klucz=Wartość ...]") z prawdziwym
// AppHostem; potomek zapisuje/czyta klucz przez CacheApi i kończy się czysto. Rodzic po każdym kroku robi
// migawkę kontenerów "cache-*" (docker inspect: id, status, obraz, czas startu, LAB_MARK, woluminy).
// Sprząta wyłącznie kontenery "cache-*", wolumin "reconfig-lab-*" i sieci, które pojawiły się po jego starcie.

if (args.Length >= 3 && args[0] == "child")
{
    return await Child.RunAsync(args[1], args[2], args[3..]);
}
return await Parent.RunAsync();

static class Sh
{
    public static string Run(string file, string arguments)
    {
        var psi = new ProcessStartInfo(file, arguments) { RedirectStandardOutput = true, RedirectStandardError = true };
        using var p = Process.Start(psi)!;
        var o = p.StandardOutput.ReadToEnd();
        p.StandardError.ReadToEnd();
        p.WaitForExit();
        return o;
    }

    public static HashSet<string> Lines(string file, string arguments) =>
        Run(file, arguments).Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).ToHashSet();

    public static HashSet<string> Containers() => Lines("docker", "ps -a --format {{.Names}}");
    public static HashSet<string> Networks() => Lines("docker", "network ls --format {{.Name}}");
    public static HashSet<string> Volumes() => Lines("docker", "volume ls --format {{.Name}}");

    public static Dictionary<int, string> Processes()
    {
        var map = new Dictionary<int, string>();
        foreach (var line in Run("ps", "-eo pid=,comm=").Split('\n', StringSplitOptions.RemoveEmptyEntries))
        {
            var t = line.Trim().Split(' ', 2, StringSplitOptions.RemoveEmptyEntries);
            if (t.Length == 2 && int.TryParse(t[0], out var pid) && t[1] is not ("ps" or "docker"))
                map[pid] = t[1].Trim();
        }
        return map;
    }

    /// <summary>Opis kontenera z `docker inspect` (BEZ wypisywania zmiennych środowiskowych poza LAB_MARK).</summary>
    public static string Describe(string container)
    {
        var json = Run("docker", $"inspect {container}");
        if (string.IsNullOrWhiteSpace(json)) return "(brak)";
        using var doc = JsonDocument.Parse(json);
        var c = doc.RootElement[0];
        var id = c.GetProperty("Id").GetString()![..12];
        var state = c.GetProperty("State");
        var image = c.GetProperty("Config").GetProperty("Image").GetString();
        var mark = c.GetProperty("Config").GetProperty("Env").EnumerateArray()
            .Select(e => e.GetString()!).FirstOrDefault(e => e.StartsWith("LAB_MARK=")) ?? "LAB_MARK=(brak)";
        var vols = string.Join(",", c.GetProperty("Mounts").EnumerateArray()
            .Select(m => m.TryGetProperty("Name", out var n) ? n.GetString() : "?"));
        // Linia poleceń kontenera (tylko dla opcji --save/--appendonly; hasło redagowane, jeśli by się pojawiło).
        var cmd = new List<string>();
        var cfgEl = c.GetProperty("Config");
        foreach (var prop in new[] { "Entrypoint", "Cmd" })
            if (cfgEl.TryGetProperty(prop, out var arr) && arr.ValueKind == JsonValueKind.Array)
                cmd.AddRange(arr.EnumerateArray().Select(e => e.GetString() ?? ""));
        var password = cfgEl.GetProperty("Env").EnumerateArray().Select(e => e.GetString()!)
            .Where(e => e.StartsWith("REDIS_PASSWORD=")).Select(e => e["REDIS_PASSWORD=".Length..]).FirstOrDefault();
        var cmdLine = string.Join(' ', cmd);
        if (!string.IsNullOrEmpty(password)) cmdLine = cmdLine.Replace(password, "<hasło>");
        var opts = System.Text.RegularExpressions.Regex.Matches(cmdLine, @"--(save|appendonly)\s+(""[^""]*""|'[^']*'|\S+)(\s+\d+)?")
            .Select(m => m.Value);
        var optText = string.Join(" ", opts);
        return $"id={id} status={state.GetProperty("Status").GetString()} image={image} {mark} " +
               $"startedAt={state.GetProperty("StartedAt").GetString()} volumes=[{vols}] opcje: {(optText.Length == 0 ? "(brak --save/--appendonly)" : optText)}";
    }
}

static class Child
{
    public static async Task<int> RunAsync(string action, string value, string[] extra)
    {
        var appArgs = new List<string> { "Logging:LogLevel:Default=Warning" };
        appArgs.AddRange(extra);
        var appHost = await DistributedApplicationTestingBuilder.CreateAsync<Projects.AppHost>(appArgs.ToArray());
        var app = await appHost.BuildAsync();
        await app.StartAsync();
        await app.ResourceNotifications.WaitForResourceHealthyAsync("cache-api").WaitAsync(TimeSpan.FromSeconds(180));

        using var http = app.CreateHttpClient("cache-api");
        if (action == "write")
        {
            var r = await http.PutAsync("/cache/reconfig-key", new StringContent(value, Encoding.UTF8));
            Console.WriteLine($"RESULT write {(int)r.StatusCode}");
        }
        else
        {
            var r = await http.GetAsync("/cache/reconfig-key");
            Console.WriteLine(r.IsSuccessStatusCode
                ? $"RESULT read {await r.Content.ReadAsStringAsync()}"
                : $"RESULT read MISSING ({(int)r.StatusCode})");
        }
        Console.Out.Flush();
        await app.StopAsync();
        await app.DisposeAsync();
        return 0;
    }
}

static class Parent
{
    static readonly TimeSpan Settle = TimeSpan.FromSeconds(8);
    static HashSet<string> containers0 = [], networks0 = [], volumes0 = [];
    static Dictionary<int, string> procs0 = [];
    static readonly string Guid8 = Guid.NewGuid().ToString("N")[..8];

    public static async Task<int> RunAsync()
    {
        containers0 = Sh.Containers();
        networks0 = Sh.Networks();
        volumes0 = Sh.Volumes();
        procs0 = Sh.Processes();
        var vol = $"reconfig-lab-{Guid8}";
        try
        {
            Console.WriteLine("### C: zmiana konfiguracji zasobu przy trwałym kontenerze");
            await Step("C1 write v1, Mark=m1", "write", $"v1-{Guid8}", ["Mark=m1"]);
            await Step("C2 read,     Mark=m1 (kontrola: ta sama konfiguracja)", "read", "-", ["Mark=m1"]);
            await Step("C3 read,     Mark=m2 (zmieniona zmienna środowiskowa)", "read", "-", ["Mark=m2"]);
            await Step("C4 read,     Mark=m2 + RedisTag=7-alpine (zmieniony obraz)", "read", "-", ["Mark=m2", "RedisTag=7-alpine"]);
            Cleanup();

            Console.WriteLine();
            Console.WriteLine("### D1: Persistent + WithDataVolume, kontener zatrzymany łagodnie (docker stop) i usunięty");
            await Step("D1a write v1, VolumeName", "write", $"v1-{Guid8}", [$"VolumeName={vol}"]);
            Console.WriteLine("    [z zewnątrz] docker stop + docker rm kontenera cache-*");
            StopAndRemoveOwn(force: false);
            await Step("D1b read (nowy AppHost, ten sam wolumin)", "read", "-", [$"VolumeName={vol}"]);
            Cleanup();

            Console.WriteLine();
            Console.WriteLine("### D2: Persistent + WithDataVolume, kontener ubity (docker rm -f = SIGKILL)");
            await Step("D2a write v2, VolumeName", "write", $"v2-{Guid8}", [$"VolumeName={vol}b"]);
            Console.WriteLine("    [z zewnątrz] docker rm -f kontenera cache-*");
            StopAndRemoveOwn(force: true);
            await Step("D2b read (nowy AppHost, ten sam wolumin)", "read", "-", [$"VolumeName={vol}b"]);
            Cleanup();

            Console.WriteLine();
            Console.WriteLine("### D4: Persistent + WithDataVolume + WithPersistence(), docker stop + docker rm");
            await Step("D4a write v4", "write", $"v4-{Guid8}", [$"VolumeName={vol}c", "Persistence=true"]);
            Console.WriteLine("    [z zewnątrz] docker stop + docker rm kontenera cache-*");
            StopAndRemoveOwn(force: false);
            await Step("D4b read (nowy AppHost, ten sam wolumin)", "read", "-", [$"VolumeName={vol}c", "Persistence=true"]);
            Cleanup();

            Console.WriteLine();
            Console.WriteLine("### D5: Persistent + WithDataVolume + WithPersistence(), docker rm -f (SIGKILL) zaraz po zapisie");
            await Step("D5a write v5", "write", $"v5-{Guid8}", [$"VolumeName={vol}d", "Persistence=true"]);
            Console.WriteLine("    [z zewnątrz] docker rm -f kontenera cache-*");
            StopAndRemoveOwn(force: true);
            await Step("D5b read (nowy AppHost, ten sam wolumin)", "read", "-", [$"VolumeName={vol}d", "Persistence=true"]);
            Cleanup();

            Console.WriteLine();
            Console.WriteLine("### D6: Persistent + WithDataVolume, zapis, 75 s czekania (> okno --save 60 1), dopiero docker rm -f");
            await Step("D6a write v6", "write", $"v6-{Guid8}", [$"VolumeName={vol}e"]);
            Console.WriteLine("    [czekam 75 s, żeby minęło okno snapshotu --save 60 1]");
            await Task.Delay(TimeSpan.FromSeconds(75));
            Console.WriteLine("    [z zewnątrz] docker rm -f kontenera cache-*");
            StopAndRemoveOwn(force: true);
            await Step("D6b read (nowy AppHost, ten sam wolumin)", "read", "-", [$"VolumeName={vol}e"]);
            Cleanup();

            Console.WriteLine();
            Console.WriteLine("### D3 (kontrola): Persistent BEZ WithDataVolume, kontener zatrzymany łagodnie i usunięty");
            await Step("D3a write v3", "write", $"v3-{Guid8}", []);
            Console.WriteLine("    [z zewnątrz] docker stop + docker rm kontenera cache-*");
            StopAndRemoveOwn(force: false);
            await Step("D3b read (nowy AppHost)", "read", "-", []);
        }
        finally
        {
            Cleanup();
        }
        return 0;
    }

    static IEnumerable<string> OwnCaches() => Sh.Containers().Except(containers0).Where(c => c.StartsWith("cache-"));

    static void StopAndRemoveOwn(bool force)
    {
        foreach (var c in OwnCaches())
        {
            if (force) Sh.Run("docker", $"rm -f {c}");
            else
            {
                var sw = Stopwatch.StartNew();
                Sh.Run("docker", $"stop {c}");
                var exit = Sh.Run("docker", "inspect --format {{.State.ExitCode}} " + c).Trim();
                Console.WriteLine($"    docker stop {c}: {sw.Elapsed.TotalSeconds:F1} s, kod wyjścia kontenera {exit} (137 = SIGKILL)");
                Sh.Run("docker", $"rm {c}");
            }
        }
    }

    static async Task Step(string title, string action, string value, string[] extra)
    {
        var self = Environment.ProcessPath!;
        var childArgs = $"child {action} {value} {string.Join(' ', extra)}".Trim();
        var selfArgs = Path.GetFileNameWithoutExtension(self) == "dotnet"
            ? $"\"{Environment.GetCommandLineArgs()[0]}\" {childArgs}"
            : childArgs;
        using var child = Process.Start(new ProcessStartInfo(self, selfArgs)
        { RedirectStandardOutput = true, RedirectStandardError = true })!;
        _ = child.StandardError.ReadToEndAsync();
        string? result = null, line;
        while ((line = await child.StandardOutput.ReadLineAsync()) is not null)
        {
            if (line.StartsWith("RESULT")) result = line;
        }
        child.WaitForExit();
        await Task.Delay(Settle);

        Console.WriteLine($"- {title}");
        Console.WriteLine($"    {result ?? "(potomek nie zwrócił wyniku)"} (kod wyjścia {child.ExitCode})");
        var caches = OwnCaches().ToList();
        if (caches.Count == 0) Console.WriteLine($"    kontenery cache-* po {Settle.TotalSeconds:F0} s: (brak)");
        foreach (var c in caches) Console.WriteLine($"    {c}: {Sh.Describe(c)}");
    }

    static void Cleanup()
    {
        var now = Sh.Processes();
        foreach (var kv in now.Where(kv => !procs0.ContainsKey(kv.Key) && (kv.Value.StartsWith("dcp") || kv.Value == "CacheApi")))
            Sh.Run("kill", $"-KILL {kv.Key}");
        foreach (var c in OwnCaches().ToList())
        {
            // Obraz redis:7-alpine deklaruje VOLUME /data -> anonimowy wolumin, którego Aspire nie sprząta.
            var mounts = Sh.Run("docker", "inspect --format \"{{range .Mounts}}{{println .Name}}{{end}}\" " + c)
                .Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
            Sh.Run("docker", $"rm -f {c}");
            foreach (var m in mounts) Sh.Run("docker", $"volume rm {m}");
        }
        foreach (var n in Sh.Networks().Except(networks0).Where(n => n.StartsWith("aspire")))
            Sh.Run("docker", $"network rm {n}");
        foreach (var v in Sh.Volumes().Except(volumes0).Where(v => v.Contains("reconfig-lab-")))
            Sh.Run("docker", $"volume rm {v}");
    }
}
