// Przykład edukacyjny: "file-based apps" w .NET 10 SDK.
// Ten plik NIE ma towarzyszącego .csproj - a mimo to jest pełnoprawnym programem C#.
// Uruchom: dotnet run hello.cs

var name = args.Length > 0 ? args[0] : "świecie";

Console.WriteLine($"Cześć, {name}!");
Console.WriteLine($"To działa bez żadnego .csproj - uruchomione o {DateTime.Now:HH:mm:ss}.");
Console.WriteLine($"Argumentów przekazanych z linii poleceń: {args.Length}");
