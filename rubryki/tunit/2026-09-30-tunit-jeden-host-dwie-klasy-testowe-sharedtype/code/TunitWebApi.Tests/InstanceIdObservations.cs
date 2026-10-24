using System.Collections.Concurrent;

namespace TunitWebApi.Tests;

/// <summary>
/// Zbiera GUID-y zwrocone przez GET /instance-id, zgloszone z roznych klas testowych.
/// Sluzy tylko do pomiaru w [AfterEvery(Assembly)] w AssemblyHooks.cs -- czy dwie rozne
/// klasy dostaly ten sam host, czy dwa rozne.
/// </summary>
public static class InstanceIdObservations
{
    public static ConcurrentDictionary<string, Guid> SeenByClass { get; } = new();

    public static void Record(string className, Guid instanceId) =>
        SeenByClass[className] = instanceId;
}
