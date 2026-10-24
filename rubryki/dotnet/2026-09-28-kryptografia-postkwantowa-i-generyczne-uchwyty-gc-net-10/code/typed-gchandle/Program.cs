using System;
using System.Runtime.InteropServices;

Console.WriteLine("--- 1. stary GCHandle (non-generic, boxing) ---");
int number = 42;
GCHandle oldHandle = GCHandle.Alloc(number); // boxuje int -> object
object? boxed = oldHandle.Target;
Console.WriteLine("typ Target: " + boxed!.GetType().FullName + ", wartosc: " + boxed);
oldHandle.Free();

Console.WriteLine("--- 2. GCHandle<T> generyczny, bez boxingu, bez rzutowania ---");
var sb = new System.Text.StringBuilder("hello");
GCHandle<System.Text.StringBuilder> typedHandle = new(sb);
System.Text.StringBuilder target = typedHandle.Target; // brak rzutowania - typ wynika z T
Console.WriteLine("target.ToString() = " + target);
typedHandle.Dispose();

Console.WriteLine("--- 3. PinnedGCHandle<T> - przypiecie tablicy i surowy wskaznik ---");
int[] buffer = { 1, 2, 3, 4, 5 };
PinnedGCHandle<int[]> pinned = new(buffer);
unsafe
{
    int* ptr = GCHandleExtensions.GetAddressOfArrayData(pinned);
    ptr[0] = 999; // pisanie bezposrednio do pamieci tablicy zarzadzanej
}
Console.WriteLine("buffer po zapisie przez wskaznik: " + string.Join(",", buffer));
pinned.Dispose();

Console.WriteLine("--- 4. WeakGCHandle<T> - typowany slaby uchwyt ---");

var weak = MakeWeak();
Console.WriteLine("przed GC: obiekt zyje = " + CheckAlive(weak));
GC.Collect();
GC.WaitForPendingFinalizers();
GC.Collect();
Console.WriteLine("po GC: obiekt zyje = " + CheckAlive(weak));
weak.Dispose();

Console.WriteLine("--- 5. Haczyk: PinnedGCHandle<T> na tablicy typow referencyjnych ---");
Console.WriteLine("Stary GCHandle.Alloc(string[], Pinned):");
try
{
    var refArr = new string[] { "a", "b" };
    var oldPinned = GCHandle.Alloc(refArr, GCHandleType.Pinned);
    Console.WriteLine("  brak wyjatku (nieoczekiwane)");
    oldPinned.Free();
}
catch (Exception ex)
{
    Console.WriteLine("  rzucil: " + ex.GetType().Name + ": " + ex.Message);
}

Console.WriteLine("Nowy PinnedGCHandle<string[]>:");
var refArr2 = new string[] { "a", "b" };
PinnedGCHandle<string[]> newPinned = new(refArr2);
unsafe
{
#pragma warning disable CS8500 // wskaznik na typ zarzadzany - swiadome, to wlasnie badamy
    string* ptr = GCHandleExtensions.GetAddressOfArrayData(newPinned);
    Console.WriteLine("  brak wyjatku; wskaznik = " + ((IntPtr)ptr) + "; ptr[0] == refArr2[0]: " + ReferenceEquals(ptr[0], refArr2[0]));
#pragma warning restore CS8500
}
newPinned.Dispose();

[System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
static WeakGCHandle<object> MakeWeak()
{
    var obj = new object();
    return new WeakGCHandle<object>(obj, trackResurrection: false);
}

[System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
static bool CheckAlive(WeakGCHandle<object> h)
{
    return h.TryGetTarget(out _);
}
