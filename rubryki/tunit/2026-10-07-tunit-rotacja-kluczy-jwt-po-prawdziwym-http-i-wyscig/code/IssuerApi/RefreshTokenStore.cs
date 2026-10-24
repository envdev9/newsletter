using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text;

namespace IssuerApi;

public enum RotateStatus { Ok, Unknown, Expired, ReuseDetected }

public sealed record RotateResult(RotateStatus Status, string? User = null, string? NewToken = null);

/// <summary>
/// Jednorazowe refresh tokeny z rodzinami (jak w wydaniu #13), tym razem pod katem WYSCIGU:
/// ile rownoleglych zadan z TYM SAMYM tokenem moze dostac nowy token? Odpowiedz ma byc: dokladnie jedno.
/// O tym decyduje blok lock w Rotate -- test wyscigu jest jedyna rzecza, ktora to pilnuje.
/// Magazyn w pamieci, tylko demo.
/// </summary>
public sealed class RefreshTokenStore(TimeProvider time)
{
    private sealed record Entry(string Family, string User, DateTimeOffset ExpiresAt) { public bool Used; }

    private readonly ConcurrentDictionary<string, Entry> _tokens = new();
    private readonly ConcurrentDictionary<string, bool> _revokedFamilies = new();
    private readonly object _gate = new();

    public string Create(string user) => Issue(user, Guid.NewGuid().ToString("N"));

    public RotateResult Rotate(string presented)
    {
        lock (_gate)
        {
            if (!_tokens.TryGetValue(Hash(presented), out var entry))
                return new(RotateStatus.Unknown);

            if (_revokedFamilies.ContainsKey(entry.Family))
                return new(RotateStatus.ReuseDetected);

            if (entry.Used)
            {
                _revokedFamilies[entry.Family] = true;
                return new(RotateStatus.ReuseDetected);
            }

            if (time.GetUtcNow() >= entry.ExpiresAt)
                return new(RotateStatus.Expired);

            entry.Used = true;
            return new(RotateStatus.Ok, entry.User, Issue(entry.User, entry.Family));
        }
    }

    private string Issue(string user, string family)
    {
        var token = Convert.ToBase64String(RandomNumberGenerator.GetBytes(32))
            .Replace('+', '-').Replace('/', '_').TrimEnd('=');
        _tokens[Hash(token)] = new Entry(family, user, time.GetUtcNow() + IssuerDefaults.RefreshLifetime);
        return token;
    }

    private static string Hash(string token) =>
        Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(token)));
}
