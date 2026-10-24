namespace FilterLab.Tests;

// Klasa blokuje DWA klucze naraz: nie nałoży się ani z kluczem "orders", ani z "stock".
[NotInParallel(["orders", "stock"])]
public class TransferTests
{
    [Test] public async Task T1() { await Probe.Run("AB"); }
    [Test] public async Task T2() { await Probe.Run("AB"); }
}

[NotInParallel("orders")]
public class OrdersWriters
{
    [Test] public async Task O1() { await Probe.Run("orders"); }
    [Test] public async Task O2() { await Probe.Run("orders"); }
}

[NotInParallel("stock")]
public class StockWriters
{
    [Test] public async Task S1() { await Probe.Run("stock"); }
    [Test] public async Task S2() { await Probe.Run("stock"); }
}
