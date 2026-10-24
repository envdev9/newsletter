using System.Diagnostics;
using System.Runtime.CompilerServices;

namespace FilterLab.Tests;

/// <summary>Mierzy, ile testów z danej grupy jednocześnie jest w ciele, i zapisuje oś czasu.</summary>
public static class Probe
{
    private static readonly object Gate = new();
    private static readonly Stopwatch Clock = Stopwatch.StartNew();
    private static readonly Dictionary<string, int> Current = new();
    private static readonly Dictionary<string, int> Peak = new();
    private static readonly List<(string Name, string Group, long Start, long End)> Timeline = new();

    public static async Task Run(string group, int delayMs = 300, [CallerMemberName] string name = "")
    {
        long start;
        lock (Gate)
        {
            start = Clock.ElapsedMilliseconds;
            Current[group] = Current.GetValueOrDefault(group) + 1;
            Peak[group] = Math.Max(Peak.GetValueOrDefault(group), Current[group]);
        }

        await Task.Delay(delayMs);

        lock (Gate)
        {
            Current[group]--;
            Timeline.Add((name, group, start, Clock.ElapsedMilliseconds));
        }
    }

    public static IEnumerable<string> Lines()
    {
        lock (Gate)
        {
            var t0 = Timeline.Count == 0 ? 0 : Timeline.Min(e => e.Start);
            yield return "szczyt per grupa: " + string.Join(", ", Peak.OrderBy(p => p.Key).Select(p => $"{p.Key}={p.Value}"));
            foreach (var e in Timeline.OrderBy(e => e.Start))
            {
                yield return $"  {e.Name,-4} {e.Group,-5} {e.Start - t0,5} -> {e.End - t0,5} ms";
            }
        }
    }
}

public static class SessionReport
{
    [AfterEvery(Assembly)]
    public static void Print(AssemblyHookContext context)
    {
        foreach (var line in Probe.Lines().ToList())
        {
            Console.WriteLine("PROBE " + line);
        }
    }
}
