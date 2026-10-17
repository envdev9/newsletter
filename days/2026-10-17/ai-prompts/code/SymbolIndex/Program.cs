// Indeks symboli i diagnostyka na Roslynie (zamiast regexow z chain.py z wydania #18).
//   SymbolIndex index <katalog>   -> symbol \t rodzaj \t dostepnosc \t pliki \t sygnatury
//   SymbolIndex diag  <katalog>   -> bledy kompilatora (CSxxxx plik(linia,kol): tresc) + "# ms=..."
// Sciezki w wyniku sa wzgledem KATALOGU NADRZEDNEGO podanego katalogu (np. Billing/Money.cs).
using System.Diagnostics;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

if (args.Length != 2 || args[0] is not ("index" or "diag"))
{
    Console.Error.WriteLine("uzycie: SymbolIndex index|diag <katalog>");
    return 2;
}

var dir = Path.GetFullPath(args[1]).TrimEnd('/');
var parent = Path.GetDirectoryName(dir)!;
string Rel(string path) => Path.GetRelativePath(parent, path).Replace('\\', '/');

var sw = Stopwatch.StartNew();
var compilation = BuildCompilation(dir);

if (args[0] == "diag")
{
    var diags = compilation.GetDiagnostics();
    var errors = diags.Where(d => d.Severity == DiagnosticSeverity.Error).ToList();
    foreach (var d in errors.OrderBy(d => d.Location.SourceTree?.FilePath).ThenBy(d => d.Location.SourceSpan.Start))
    {
        var pos = d.Location.GetLineSpan();
        var file = d.Location.SourceTree is { } t ? Rel(t.FilePath) : "?";
        Console.WriteLine($"{d.Id} {file}({pos.StartLinePosition.Line + 1},{pos.StartLinePosition.Character + 1}): {d.GetMessage()}");
    }
    var warnings = diags.Count(d => d.Severity == DiagnosticSeverity.Warning);
    Console.WriteLine($"# errors={errors.Count} warnings={warnings}");
    Console.WriteLine($"# ms={sw.ElapsedMilliseconds}");
    return errors.Count == 0 ? 0 : 1;
}

var entries = new SortedDictionary<string, Entry>(StringComparer.Ordinal);

void Add(string name, string kind, Accessibility acc, IEnumerable<SyntaxReference> refs, string? sig)
{
    if (!entries.TryGetValue(name, out var e))
        entries[name] = e = new Entry(kind, acc.ToString().ToLowerInvariant());
    foreach (var r in refs) e.Files.Add(Rel(r.SyntaxTree.FilePath));
    if (sig is not null) e.Sigs.Add(sig);
}

void VisitType(INamedTypeSymbol t, string prefix)
{
    if (t.IsImplicitlyDeclared) return;
    var name = prefix + t.Name;
    Add(name, t.TypeKind.ToString().ToLowerInvariant(), t.DeclaredAccessibility, t.DeclaringSyntaxReferences, null);
    foreach (var m in t.GetMembers())
    {
        var qn = name + "." + m.Name;
        switch (m)
        {
            case INamedTypeSymbol nt:
                VisitType(nt, name + ".");
                break;
            case IMethodSymbol { MethodKind: MethodKind.Ordinary, IsImplicitlyDeclared: false } ms
                when ms.ExplicitInterfaceImplementations.IsEmpty:
                var sig = string.Join(",", ms.Parameters.Select(p => p.Type.ToDisplayString(SymbolDisplayFormat.MinimallyQualifiedFormat)));
                Add(qn, "method", ms.DeclaredAccessibility, ms.DeclaringSyntaxReferences, sig);
                break;
            case IPropertySymbol p when !p.IsImplicitlyDeclared || p.DeclaringSyntaxReferences.Any(r => r.GetSyntax() is ParameterSyntax):
                Add(qn, "property", p.DeclaredAccessibility, p.DeclaringSyntaxReferences, null);
                break;
            case IFieldSymbol f when !f.IsImplicitlyDeclared:
                Add(qn, t.TypeKind == TypeKind.Enum ? "enummember" : "field", f.DeclaredAccessibility, f.DeclaringSyntaxReferences, null);
                break;
            case IEventSymbol ev when !ev.IsImplicitlyDeclared:
                Add(qn, "event", ev.DeclaredAccessibility, ev.DeclaringSyntaxReferences, null);
                break;
        }
    }
}

void VisitNs(INamespaceSymbol ns)
{
    foreach (var n in ns.GetNamespaceMembers()) VisitNs(n);
    foreach (var t in ns.GetTypeMembers()) VisitType(t, "");
}

VisitNs(compilation.Assembly.GlobalNamespace);

foreach (var (name, e) in entries)
    Console.WriteLine($"{name}\t{e.Kind}\t{e.Access}\t{string.Join(";", e.Files.Order())}\t{string.Join(";", e.Sigs.Order())}");
return 0;

static CSharpCompilation BuildCompilation(string dir)
{
    // Odpowiednik ImplicitUsings=enable z SDK (bez MSBuilda).
    const string implicitUsings = """
        global using System;
        global using System.Collections.Generic;
        global using System.IO;
        global using System.Linq;
        global using System.Net.Http;
        global using System.Threading;
        global using System.Threading.Tasks;
        """;
    var trees = new List<SyntaxTree> { CSharpSyntaxTree.ParseText(implicitUsings, path: "<implicit-usings>.cs") };
    foreach (var file in Directory.GetFiles(dir, "*.cs", SearchOption.TopDirectoryOnly).Order(StringComparer.Ordinal))
        trees.Add(CSharpSyntaxTree.ParseText(File.ReadAllText(file), path: file));

    // Referencje = zestawy runtime'u, na ktorym dziala narzedzie (implementacje, nie "reference assemblies").
    var tpa = ((string)AppContext.GetData("TRUSTED_PLATFORM_ASSEMBLIES")!).Split(Path.PathSeparator);
    var refs = tpa
        .Where(p => Path.GetFileName(p) is var f && (f.StartsWith("System.") || f is "mscorlib.dll" or "netstandard.dll"))
        .Select(p => (MetadataReference)MetadataReference.CreateFromFile(p));

    return CSharpCompilation.Create("Probe", trees, refs,
        new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary, nullableContextOptions: NullableContextOptions.Enable));
}

sealed record Entry(string Kind, string Access)
{
    public SortedSet<string> Files { get; } = new(StringComparer.Ordinal);
    public SortedSet<string> Sigs { get; } = new(StringComparer.Ordinal);
}
