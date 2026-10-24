using Microsoft.Extensions.DependencyInjection;

namespace DataLab.Core;

/// <summary>Reguła rabatu: klient lojalnościowy dostaje procent, zamówienie od progu dodatkowy rabat kwotowy.</summary>
public sealed class PricingService(IDiscountPolicy policy)
{
    public decimal Total(decimal net, string tier)
    {
        if (net < 0) throw new ArgumentOutOfRangeException(nameof(net));
        var percent = policy.PercentFor(tier);
        var afterPercent = net * (1 - percent / 100m);
        var flat = net >= 500m ? 20m : 0m;
        return Math.Round(Math.Max(0m, afterPercent - flat), 2);
    }
}

public interface IDiscountPolicy
{
    int PercentFor(string tier);
}

public sealed class TierDiscountPolicy : IDiscountPolicy
{
    public int PercentFor(string tier) => tier switch
    {
        "none" => 0,
        "silver" => 5,
        "gold" => 10,
        "platinum" => 15,
        _ => throw new ArgumentException($"Nieznany poziom: {tier}", nameof(tier)),
    };
}

/// <summary>Scoped "unit of work" - ma identyfikator, żeby dało się zmierzyć ile scope'ów powstało.</summary>
public sealed class RequestScopeMarker : IDisposable
{
    private static int _created;
    private static int _disposed;
    public static int Created => _created;
    public static int Disposed => _disposed;

    public int Id { get; } = Interlocked.Increment(ref _created);
    public void Dispose() => Interlocked.Increment(ref _disposed);
}

public static class Composition
{
    public static ServiceProvider Build()
    {
        var services = new ServiceCollection();
        services.AddSingleton<IDiscountPolicy, TierDiscountPolicy>();
        services.AddScoped<RequestScopeMarker>();
        services.AddScoped<PricingService>();
        return services.BuildServiceProvider(new ServiceProviderOptions { ValidateScopes = true, ValidateOnBuild = true });
    }
}
