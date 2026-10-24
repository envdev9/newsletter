using System.Collections.Concurrent;

namespace SkipLab.Tests;

/// <summary>Wspolny dziennik zdarzen z numeracja: pozwala porownac KOLEJNOSC ShouldSkip vs. cialo testu.</summary>
public static class Trace
{
    private static int _seq;
    public static readonly ConcurrentQueue<(int Seq, string What)> Events = new();

    public static int Add(string what)
    {
        var n = Interlocked.Increment(ref _seq);
        Events.Enqueue((n, what));
        return n;
    }
}

/// <summary>Pomija test, gdy brakuje zmiennej srodowiskowej.</summary>
public sealed class RequiresEnvVarAttribute(string name) : SkipAttribute($"brak zmiennej srodowiskowej {name}")
{
    public override Task<bool> ShouldSkip(TestRegisteredContext context)
    {
        Trace.Add($"ShouldSkip[RequiresEnvVar] test={context.TestName}");
        var present = !string.IsNullOrEmpty(Environment.GetEnvironmentVariable(name));
        return Task.FromResult(!present);
    }
}

/// <summary>Pomija test poza Linuksem.</summary>
public sealed class LinuxOnlyAttribute() : SkipAttribute("test tylko dla Linuksa")
{
    public override Task<bool> ShouldSkip(TestRegisteredContext context)
    {
        Trace.Add($"ShouldSkip[LinuxOnly] test={context.TestName}");
        return Task.FromResult(!OperatingSystem.IsLinux());
    }
}
