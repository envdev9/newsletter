using System.IO.Compression;
using System.Reflection;

Console.WriteLine($"Runtime: {System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription}");

Type[] types = [typeof(ZipFile), typeof(ZipFileExtensions), typeof(ZipArchive), typeof(ZipArchiveEntry)];
foreach (var t in types)
{
    Console.WriteLine($"--- {t.Name}: publiczne metody *Async / CreateAsync / DisposeAsync ---");
    var found = t.GetMethods(BindingFlags.Public | BindingFlags.Static | BindingFlags.Instance | BindingFlags.DeclaredOnly)
        .Where(m => m.Name.EndsWith("Async"))
        .Select(Describe)
        .OrderBy(s => s, StringComparer.Ordinal)
        .ToList();
    if (found.Count == 0) Console.WriteLine("(brak)");
    foreach (var s in found) Console.WriteLine(s);
}

static string Describe(MethodInfo m) =>
    $"{(m.IsStatic ? "static " : "")}{m.ReturnType.Name} {m.Name}({string.Join(", ", m.GetParameters().Select(p => p.ParameterType.Name))})";
