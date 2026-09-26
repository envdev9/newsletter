using System.Collections.Concurrent;
using TUnit.Core.Interfaces;

namespace TunitFixtures;

/// <summary>
/// Udawana "droga" baza: tworzenie trwa 200 ms. Liczy, ile instancji powstało i ile
/// zostało zwolnionych, i zapisuje zdarzenia w dzienniku.
/// </summary>
public class FakeDatabase : IAsyncInitializer, IAsyncDisposable
{
    private static int _created;
    private static int _disposed;

    public static int Created => Volatile.Read(ref _created);
    public static int Disposed => Volatile.Read(ref _disposed);
    public static ConcurrentQueue<string> Journal { get; } = new();

    public int InstanceId { get; } = Interlocked.Increment(ref _created);
    public bool IsReady { get; private set; }

    public async Task InitializeAsync()
    {
        await Task.Delay(200);
        IsReady = true;
        Journal.Enqueue($"init    FakeDatabase#{InstanceId}");
    }

    public ValueTask DisposeAsync()
    {
        Interlocked.Increment(ref _disposed);
        Journal.Enqueue($"dispose FakeDatabase#{InstanceId}");
        return ValueTask.CompletedTask;
    }
}
