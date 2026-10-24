using System.Diagnostics;
using System.Runtime.CompilerServices;

namespace ReportingLab;

/// <summary>Mierzy, ile testow z danej grupy bylo jednoczesnie w srodku ciala, i zapisuje os czasu.</summary>
public static class Probe
{
    private static readonly object Gate = new();
    private static readonly Stopwatch Clock = Stopwatch.StartNew();
    private static readonly Dictionary<string, int> Current = new();
    private static readonly Dictionary<string, int> Peak = new();
    private static readonly List<(string Name, string Group, long Start, long End)> Timeline = new();
    private static int _totalCurrent;
    private static int _totalPeak;

    public static async Task Run(string group, int delayMs = 300, [CallerMemberName] string name = "")
    {
        long start;
        lock (Gate)
        {
            start = Clock.ElapsedMilliseconds;
            Current[group] = Current.GetValueOrDefault(group) + 1;
            Peak[group] = Math.Max(Peak.GetValueOrDefault(group), Current[group]);
            _totalCurrent++;
            _totalPeak = Math.Max(_totalPeak, _totalCurrent);
        }

        await Task.Delay(delayMs);

        lock (Gate)
        {
            Current[group]--;
            _totalCurrent--;
            Timeline.Add((name, group, start, Clock.ElapsedMilliseconds));
        }
    }

    public static string Summary()
    {
        lock (Gate)
        {
            var parts = Peak.OrderBy(p => p.Key).Select(p => $"{p.Key}={p.Value}");
            return $"szczyt per grupa: {string.Join(", ", parts)}; szczyt lacznie: {_totalPeak}";
        }
    }

    public static IEnumerable<string> TimelineLines()
    {
        lock (Gate)
        {
            var t0 = Timeline.Count == 0 ? 0 : Timeline.Min(e => e.Start);
            return Timeline.OrderBy(e => e.Start)
                .Select(e => $"{e.Name,-4} {e.Group,-6} {e.Start - t0,5} -> {e.End - t0,5} ms")
                .ToList();
        }
    }
}

public static class SessionReport
{
    [AfterEvery(Assembly)]
    public static void Print(AssemblyHookContext context)
    {
        Console.WriteLine("PROBE " + Probe.Summary());
        foreach (var line in Probe.TimelineLines())
        {
            Console.WriteLine("PROBE   " + line);
        }
    }
}
