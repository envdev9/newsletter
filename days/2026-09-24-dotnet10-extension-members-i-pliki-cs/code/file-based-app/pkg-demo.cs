// Bonus: pliki file-based potrafią też ściągać paczki NuGet bez żadnego .csproj,
// dzięki dyrektywie #:package na górze pliku.
// Uruchom: dotnet run pkg-demo.cs   (pierwsze uruchomienie pobierze paczkę, kolejne z cache)
#:package Humanizer@2.14.1

using Humanizer;

string[] phrases = ["dotnet_run_app", "extension_members_in_csharp_14", "no_more_csproj"];

foreach (var phrase in phrases)
{
    Console.WriteLine($"{phrase} -> {phrase.Humanize()}");
}
