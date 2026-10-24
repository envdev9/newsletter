using System.Diagnostics;
using Aspire.Hosting;
using Aspire.Hosting.Testing;

// Orphan.Probe - co zostaje w systemie, gdy proces hostujący AppHosta umiera "nieelegancko"?
//
//   dotnet run --project Orphan.Probe -- parent clean exit crash sigterm sigint sigkill
//
// "parent" odpala dla każdego trybu osobny PROCES POTOMNY (ten sam exe, argument "child <tryb>"),
// który stawia prawdziwego AppHosta (Redis w Dockerze + CacheApi), melduje READY, a potem umiera
// w wybrany sposób. Rodzic mierzy, co przeżyło: kontenery, sieci i woluminy Dockera oraz procesy
// systemowe (DCP, CacheApi), i po każdym trybie sprząta WYŁĄCZNIE to, co pojawiło się
// po starcie potomka.

var argv = args;
if (argv.Length >= 2 && argv[0] == "child")
{
    return await Child.RunAsync(argv[1]);
}

var modes = argv.Length >= 2 && argv[0] == "parent"
    ? argv[1..]
    : ["clean", "exit", "crash", "sigterm", "sigint", "sigkill"];
return await Parent.RunAsync(modes);

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

    /// <summary>pid -> nazwa polecenia (comm) wszystkich procesów, z pominięciem ps/docker.</summary>
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
}

static class Child
{
    public static async Task<int> RunAsync(string mode)
    {
        var appHost = await DistributedApplicationTestingBuilder.CreateAsync<Projects.AppHost>(
            ["Logging:LogLevel:Default=Warning"]);
        var app = await appHost.BuildAsync();
        await app.StartAsync();
        await app.ResourceNotifications.WaitForResourceHealthyAsync("cache-api").WaitAsync(TimeSpan.FromSeconds(120));
        Console.WriteLine($"READY {Environment.ProcessId}");
        Console.Out.Flush();

        switch (mode)
        {
            case "clean":
                await app.StopAsync();
                await app.DisposeAsync();
                return 0;
            case "exit":
                Environment.Exit(0);          // proces kończy się, bez StopAsync/DisposeAsync
                return 0;
            case "crash":
                Environment.FailFast("Orphan.Probe: celowy FailFast (SIGABRT)");
                return 1;
            default:                          // sigterm / sigint / sigkill: rodzic wyśle sygnał
                await Task.Delay(Timeout.Infinite);
                return 0;
        }
    }
}

static class Parent
{
    public static async Task<int> RunAsync(string[] modes)
    {
        Console.WriteLine("| tryb | kod wyjścia potomka | potomek kończy się po | kontener Redis znika po | procesy DCP/CacheApi znikają po | uwagi |");
        Console.WriteLine("|---|---|---|---|---|---|");
        foreach (var mode in modes)
        {
            await RunModeAsync(mode);
        }
        return 0;
    }

    static async Task RunModeAsync(string mode)
    {
        var containers0 = Sh.Containers();
        var networks0 = Sh.Networks();
        var volumes0 = Sh.Volumes();
        var procs0 = Sh.Processes();

        // Uruchomiony przez "dotnet X.dll" ProcessPath to "dotnet" - wtedy dll trzeba podać jawnie.
        var self = Environment.ProcessPath!;
        var selfArgs = Path.GetFileNameWithoutExtension(self) == "dotnet"
            ? $"\"{Environment.GetCommandLineArgs()[0]}\" child {mode}"
            : $"child {mode}";
        var psi = new ProcessStartInfo(self, selfArgs)
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        using var child = Process.Start(psi)!;
        _ = child.StandardError.ReadToEndAsync();   // szum stderr (k8s itd.) - nieistotny, ale trzeba opróżniać
        string? line;
        while ((line = await child.StandardOutput.ReadLineAsync()) is not null && !line.StartsWith("READY")) { }
        if (line is null) { Console.WriteLine($"| {mode} | child nie doszedł do READY | | | | |"); return; }

        var ownContainers = Sh.Containers().Except(containers0).ToHashSet();
        var ownNetworks = Sh.Networks().Except(networks0).ToHashSet();
        var procsReady = Sh.Processes();
        var own = procsReady.Where(kv => !procs0.ContainsKey(kv.Key) && kv.Key != child.Id)
                            .ToDictionary(kv => kv.Key, kv => kv.Value);
        Console.Error.WriteLine($"[{mode}] kontenery: {string.Join(",", ownContainers)}; sieci: {string.Join(",", ownNetworks)}; " +
                                $"procesy: {string.Join(",", own.Select(kv => $"{kv.Value}({kv.Key})"))}");

        switch (mode)
        {
            case "sigterm": Sh.Run("kill", $"-TERM {child.Id}"); break;
            case "sigint": Sh.Run("kill", $"-INT {child.Id}"); break;
            case "sigkill": Sh.Run("kill", $"-KILL {child.Id}"); break;
            case "sigkill-all":
                // Zabij hosta ORAZ jego "siatkę bezpieczeństwa" (procesy dcp*) w jednym poleceniu.
                var dcp = string.Join(" ", own.Where(kv => kv.Value.StartsWith("dcp")).Select(kv => kv.Key));
                Sh.Run("kill", $"-KILL {child.Id} {dcp}");
                break;
        }
        // Zegar startuje w chwili "wyzwalacza": wysłania sygnału albo (tryby clean/exit/crash)
        // chwili READY, bo potomek sam kończy się natychmiast po meldunku.
        var sw = Stopwatch.StartNew();
        TimeSpan? childExitAt = null, containerGoneAt = null, procsGoneAt = null;
        var deadline = TimeSpan.FromSeconds(90);
        while (sw.Elapsed < deadline)
        {
            if (childExitAt is null && child.HasExited) childExitAt = sw.Elapsed;
            if (containerGoneAt is null && !Sh.Containers().Overlaps(ownContainers)) containerGoneAt = sw.Elapsed;
            if (procsGoneAt is null)
            {
                var now = Sh.Processes();
                if (!own.Any(kv => now.TryGetValue(kv.Key, out var name) && name == kv.Value)) procsGoneAt = sw.Elapsed;
            }
            if (childExitAt is not null && containerGoneAt is not null && procsGoneAt is not null) break;
            await Task.Delay(500);
        }
        var childStillAlive = !child.HasExited;
        if (childStillAlive) { child.Kill(); child.WaitForExit(); }   // tylko po pomiarze

        var nowProcs = Sh.Processes();
        var orphanProcs = own.Where(kv => nowProcs.TryGetValue(kv.Key, out var name) && name == kv.Value).ToList();
        var orphanContainers = Sh.Containers().Intersect(ownContainers).ToList();
        var orphanNetworks = Sh.Networks().Intersect(ownNetworks).ToList();
        var newVolumes = Sh.Volumes().Except(volumes0).ToList();

        static string T(TimeSpan? t) => t is null ? "NIE (90 s)" : $"{t.Value.TotalSeconds:F1} s";
        var notes = new List<string>();
        if (orphanNetworks.Count > 0) notes.Add($"sieć zostaje: {orphanNetworks.Count}");
        if (newVolumes.Count > 0) notes.Add($"nowe woluminy: {newVolumes.Count}");
        if (orphanProcs.Count > 0) notes.Add("sieroty: " + string.Join(", ", orphanProcs.Select(kv => $"{kv.Value}({kv.Key})")));
        Console.WriteLine($"| {mode} | {(childStillAlive ? "żyje (zabity po pomiarze)" : child.ExitCode.ToString())} | {T(childExitAt)} | " +
                          $"{T(containerGoneAt)} | {T(procsGoneAt)} | {string.Join("; ", notes)} |");

        if (mode == "sigkill-all" && orphanContainers.Count > 0)
        {
            Console.Error.WriteLine($"[{mode}] sieroty: {string.Join(",", orphanContainers)}; " +
                $"etykiety: {Sh.Run("docker", $"inspect --format \"{{{{range $k,$v := .Config.Labels}}}}{{{{$k}}}} {{{{end}}}}\" {orphanContainers[0]}").Trim()}");
            // Czy NASTĘPNY AppHost posprząta sierotę po poprzednim? Odpal zwykły przebieg "clean".
            var p2 = Process.Start(new ProcessStartInfo(self,selfArgs.Replace("sigkill-all", "clean"))
            { RedirectStandardOutput = true, RedirectStandardError = true })!;
            _ = p2.StandardError.ReadToEndAsync();
            _ = p2.StandardOutput.ReadToEndAsync();
            p2.WaitForExit();
            var after = Sh.Containers().Intersect(orphanContainers).ToList();
            var procsAfter = Sh.Processes();
            var orphanProcsAfter = orphanProcs.Where(kv => procsAfter.TryGetValue(kv.Key, out var name) && name == kv.Value).ToList();
            var netsAfter = Sh.Networks().Intersect(orphanNetworks).ToList();
            Console.WriteLine($"| (po sigkill-all) następny AppHost clean | {p2.ExitCode} | | sierota po nim: " +
                              $"{(after.Count == 0 ? "ZNIKNĘŁA" : "NADAL ISTNIEJE")} | | sieć: {(netsAfter.Count == 0 ? "znikła" : "zostaje")}; " +
                              $"procesy sieroty: {(orphanProcsAfter.Count == 0 ? "0" : string.Join(", ", orphanProcsAfter.Select(kv => $"{kv.Value}({kv.Key})")))} |");
        }

        // Sprzątanie WŁASNYCH pozostałości (tylko to, co pojawiło się po starcie potomka).
        foreach (var kv in orphanProcs) Sh.Run("kill", $"-KILL {kv.Key}");
        foreach (var c in orphanContainers) Sh.Run("docker", $"rm -f {c}");
        foreach (var n in orphanNetworks) Sh.Run("docker", $"network rm {n}");
        foreach (var v in newVolumes) Sh.Run("docker", $"volume rm {v}");
    }
}
