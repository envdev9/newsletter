using System.Text;

namespace SkipLab;

/// <summary>Maly kod "produkcyjny" pod testami: wynik zalezy od srodowiska, wiec testy musza umiec sie pomijac.</summary>
public static class Slugifier
{
    public static string Slugify(string input)
    {
        var sb = new StringBuilder();
        var lastDash = true;
        foreach (var ch in input.Trim().ToLowerInvariant())
        {
            if (char.IsLetterOrDigit(ch)) { sb.Append(ch); lastDash = false; }
            else if (!lastDash) { sb.Append('-'); lastDash = true; }
        }
        return sb.ToString().TrimEnd('-');
    }
}

public static class FsProbe
{
    /// <summary>Tworzy w katalogu plik "a.tmp" i sprawdza, czy "A.TMP" to ten sam plik.</summary>
    public static bool IsCaseSensitive(string directory)
    {
        var lower = Path.Combine(directory, "probe-" + Guid.NewGuid().ToString("N") + ".tmp");
        var upper = Path.Combine(directory, Path.GetFileName(lower).ToUpperInvariant());
        File.WriteAllText(lower, "x");
        try { return !File.Exists(upper); }
        finally { File.Delete(lower); }
    }
}

public static class DbSettings
{
    public const string VariableName = "SKIPLAB_DB";

    public static string? ConnectionString() =>
        Environment.GetEnvironmentVariable(VariableName) is { Length: > 0 } v ? v : null;
}
