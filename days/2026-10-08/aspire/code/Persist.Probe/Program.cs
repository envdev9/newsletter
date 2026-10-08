using System.Diagnostics;
using System.Text;
using Aspire.Hosting;
using Aspire.Hosting.Testing;

// Persist.Probe - czy kontener z ContainerLifetime.Persistent naprawdę przeżywa AppHosta
// i czy następny AppHost go ponownie używa (ten sam kontener, te same dane)?
//
//   dotnet run --project Persist.Probe            (pełny scenariusz: persistent + kontrola session)
//
// "parent" odpala kolejne PROCESY POTOMNE (ten sam exe: "child <write|read> <die> <wartość> <persistent>").
// Potomek stawia prawdziwego AppHosta (Redis w Dockerze + CacheApi), przez HTTP zapisuje albo czyta
// klucz, melduje READY i umiera: "clean" (StopAsync+DisposeAsync) albo "sigkill" (kill -9 od rodzica).
// Rodzic po każdym kroku czeka i robi migawkę: kontenery, procesy, ID i czas startu kontenera.
// Na końcu sprząta WYŁĄCZNIE kontenery/sieci/woluminy/procesy, które pojawiły się po jego starcie.

if (args.Length >= 5 && args[0] == "child")
{
    return await Child.RunAsync(args[1], args[2], args[3], bool.Parse(args[4]));
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

    /// <summary>"id12 status startedAt" kontenera albo "(brak)".</summary>
    public static string Describe(string container)
    {
        var o = Run("docker", $"inspect --format \"{{{{.Id}}}} {{{{.State.Status}}}} {{{{.State.StartedAt}}}}\" {container}").Trim();
        var t = o.Split(' ', 3);
        return t.Length == 3 ? $"id={t[0][..12]} status={t[1]} startedAt={t[2]}" : "(brak)";
    }
}

static class Child
{
    public static async Task<int> RunAsync(string action, string die, string value, bool persistent)
    {
        var appHost = await DistributedApplicationTestingBuilder.CreateAsync<Projects.AppHost>(
            ["Logging:LogLevel:Default=Warning", $"Persistent={persistent}"]);
        var app = await appHost.BuildAsync();
        await app.StartAsync();
        await app.ResourceNotifications.WaitForResourceHealthyAsync("cache-api").WaitAsync(TimeSpan.FromSeconds(120));

        using var http = app.CreateHttpClient("cache-api");
        if (action == "write")
        {
            var r = await http.PutAsync("/cache/persist-key", new StringContent(value, Encoding.UTF8));
            Console.WriteLine($"RESULT write {(int)r.StatusCode}");
        }
        else
        {
            var r = await http.GetAsync("/cache/persist-key");
            Console.WriteLine(r.IsSuccessStatusCode
                ? $"RESULT read {(await r.Content.ReadAsStringAsync())}"
                : $"RESULT read MISSING ({(int)r.StatusCode})");
        }
        Console.WriteLine($"READY {Environment.ProcessId}");
        Console.Out.Flush();

        if (die == "clean")
        {
            await app.StopAsync();
            await app.DisposeAsync();
            return 0;
        }
        await Task.Delay(Timeout.Infinite);   // "sigkill": rodzic wyśle kill -KILL
        return 0;
    }
}

static class Parent
{
    static readonly TimeSpan Settle = TimeSpan.FromSeconds(25);
    static HashSet<string> own = [];

    public static async Task<int> RunAsync()
    {
        var containers0 = Sh.Containers();
        var networks0 = Sh.Networks();
        var volumes0 = Sh.Volumes();
        var procs0 = Sh.Processes();
        var guid = Guid.NewGuid().ToString("N")[..8];

        try
        {
            Console.WriteLine("### Scenariusz A: WithLifetime(ContainerLifetime.Persistent)");
            await Step("A1 write v1-" + guid, "write", "clean", $"v1-{guid}", true, containers0, procs0);
            await Step("A2 read (nowy AppHost)", "read", "clean", "-", true, containers0, procs0);
            await Step("A3 write v2-" + guid + ", host zabity kill -9", "write", "sigkill", $"v2-{guid}", true, containers0, procs0);
            await Step("A4 read (nowy AppHost)", "read", "clean", "-", true, containers0, procs0);

            // Sprzątamy scenariusz A (kontener trwały nie zniknie sam), zanim zaczniemy kontrolę.
            Cleanup(containers0, networks0, volumes0, procs0);
            own = [];

            Console.WriteLine();
            Console.WriteLine("### Scenariusz B (kontrola): domyślny ContainerLifetime.Session");
            await Step("B1 write v1-" + guid, "write", "clean", $"v1-{guid}", false, containers0, procs0);
            await Step("B2 read (nowy AppHost)", "read", "clean", "-", false, containers0, procs0);
        }
        finally
        {
            Cleanup(containers0, networks0, volumes0, procs0);
        }
        return 0;
    }

    static async Task Step(string title, string action, string die, string value, bool persistent,
        HashSet<string> containers0, Dictionary<int, string> procs0)
    {
        var self = Environment.ProcessPath!;
        var childArgs = $"child {action} {die} {value} {persistent}";
        var selfArgs = Path.GetFileNameWithoutExtension(self) == "dotnet"
            ? $"\"{Environment.GetCommandLineArgs()[0]}\" {childArgs}"
            : childArgs;
        var sw = Stopwatch.StartNew();
        using var child = Process.Start(new ProcessStartInfo(self, selfArgs)
        { RedirectStandardOutput = true, RedirectStandardError = true })!;
        _ = child.StandardError.ReadToEndAsync();

        string? result = null, line;
        while ((line = await child.StandardOutput.ReadLineAsync()) is not null && !line.StartsWith("READY"))
        {
            if (line.StartsWith("RESULT")) result = line;
        }
        if (line is null) { Console.WriteLine($"- {title}: potomek nie doszedł do READY"); return; }

        own.UnionWith(Sh.Containers().Except(containers0));
        var procsReady = Sh.Processes();
        var ownProcs = procsReady.Where(kv => !procs0.ContainsKey(kv.Key) && kv.Key != child.Id).ToDictionary();
        var duringReady = string.Join("; ", own.Select(c => $"{c}: {Sh.Describe(c)}"));

        if (die == "sigkill") Sh.Run("kill", $"-KILL {child.Id}");
        else child.WaitForExit();
        var childExit = sw.Elapsed;
        await Task.Delay(Settle);

        var procsAfter = Sh.Processes();
        var survivors = ownProcs.Where(kv => procsAfter.TryGetValue(kv.Key, out var n) && n == kv.Value)
                                .Select(kv => $"{kv.Value}({kv.Key})").ToList();
        Console.WriteLine($"- {title}");
        Console.WriteLine($"    {result}");
        Console.WriteLine($"    kontener w chwili READY: {(duringReady.Length == 0 ? "(brak)" : duringReady)}");
        Console.WriteLine($"    {Settle.TotalSeconds:F0} s po śmierci hosta (kod {(die == "sigkill" ? "kill -9" : child.ExitCode)}):");
        foreach (var c in own) Console.WriteLine($"      kontener {c}: {Sh.Describe(c)}");
        Console.WriteLine($"      procesy hosta/DCP/CacheApi, które żyją: {(survivors.Count == 0 ? "0" : string.Join(", ", survivors))}");
    }

    static void Cleanup(HashSet<string> containers0, HashSet<string> networks0, HashSet<string> volumes0,
        Dictionary<int, string> procs0)
    {
        var now = Sh.Processes();
        foreach (var kv in now.Where(kv => !procs0.ContainsKey(kv.Key) && (kv.Value.StartsWith("dcp") || kv.Value == "CacheApi")))
            Sh.Run("kill", $"-KILL {kv.Key}");
        foreach (var c in Sh.Containers().Except(containers0)) Sh.Run("docker", $"rm -f {c}");
        foreach (var n in Sh.Networks().Except(networks0)) Sh.Run("docker", $"network rm {n}");
        foreach (var v in Sh.Volumes().Except(volumes0)) Sh.Run("docker", $"volume rm {v}");
    }
}
