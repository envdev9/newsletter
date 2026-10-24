namespace TunitCustom;

/// <summary>Maly obiekt domenowy, na ktorym pokazemy wlasne asercje: numer IBAN.</summary>
public sealed record Iban(string Value)
{
    public string Country => Value.Length >= 2 ? Value[..2] : "";

    /// <summary>Walidacja mod-97 (ISO 13616).</summary>
    public bool HasValidChecksum()
    {
        var s = Value.Replace(" ", "");
        if (s.Length < 5 || !s.All(char.IsLetterOrDigit)) return false;
        var rearranged = s[4..] + s[..4];
        var remainder = 0;
        foreach (var ch in rearranged)
        {
            var digits = char.IsDigit(ch) ? ch.ToString() : (char.ToUpperInvariant(ch) - 'A' + 10).ToString();
            foreach (var d in digits)
                remainder = (remainder * 10 + (d - '0')) % 97;
        }
        return remainder == 1;
    }
}
