using System.Reflection;

Console.WriteLine($"Runtime: {System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription}");

Console.WriteLine("--- Enumerable.Reverse: publiczne przeciazenia ---");
foreach (var m in typeof(Enumerable).GetMethods(BindingFlags.Public | BindingFlags.Static).Where(m => m.Name == "Reverse"))
    Console.WriteLine(Describe(m));

Console.WriteLine("--- MemoryExtensions.Reverse: publiczne przeciazenia ---");
foreach (var m in typeof(MemoryExtensions).GetMethods(BindingFlags.Public | BindingFlags.Static).Where(m => m.Name == "Reverse"))
    Console.WriteLine(Describe(m));

Console.WriteLine("--- HttpMethod: statyczne wlasciwosci ---");
foreach (var p in typeof(HttpMethod).GetProperties(BindingFlags.Public | BindingFlags.Static).OrderBy(p => p.Name))
    Console.WriteLine($"{p.Name} -> \"{p.GetValue(null)}\"");

static string Describe(MethodInfo m) =>
    $"{m.ReturnType.Name} {m.Name}({string.Join(", ", m.GetParameters().Select(p => p.ParameterType.Name))})";
