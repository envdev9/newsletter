using System.Reflection;

Console.WriteLine($"Runtime: {System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription}");

Console.WriteLine("--- OrderedDictionary<,>: publiczne przeciazenia TryAdd / TryGetValue / TryGetValue-podobne ---");
foreach (var m in typeof(OrderedDictionary<,>)
             .GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly)
             .Where(m => m.Name is "TryAdd" or "TryGetValue" or "TryGetValue" or "GetAt" or "SetAt" or "IndexOf" or "Insert" or "RemoveAt")
             .OrderBy(m => m.Name).ThenBy(m => m.GetParameters().Length))
{
    var ps = string.Join(", ", m.GetParameters().Select(p => $"{Pretty(p.ParameterType)} {p.Name}"));
    Console.WriteLine($"{m.Name}({ps})");
}

Console.WriteLine("--- SlhDsa w System.Security.Cryptography ---");
var slh = typeof(System.Security.Cryptography.RSA).Assembly.GetTypes()
    .Where(t => t.IsPublic && t.Name.StartsWith("SlhDsa")).Select(t => t.Name).OrderBy(n => n).ToArray();
Console.WriteLine(slh.Length == 0 ? "(brak typow SlhDsa*)" : string.Join(", ", slh));

static string Pretty(Type t) =>
    t.IsByRef ? "out " + Pretty(t.GetElementType()!) :
    t == typeof(int) ? "int" : t.IsGenericParameter ? t.Name : t.Name;
