namespace SkipLab.Tests;

/// <summary>
/// Pomija test, gdy brakuje zmiennej srodowiskowej. Decyzja zapada przy rejestracji testu,
/// zanim ruszy jakikolwiek kod testu (wiec test nie jest nawet "uruchamiany").
/// </summary>
public sealed class RequiresEnvVarAttribute(string name) : SkipAttribute($"brak zmiennej srodowiskowej {name}")
{
    public override Task<bool> ShouldSkip(TestRegisteredContext context)
    {
        var present = !string.IsNullOrEmpty(Environment.GetEnvironmentVariable(name));
        return Task.FromResult(!present);
    }
}

/// <summary>Pomija test poza Linuksem.</summary>
public sealed class LinuxOnlyAttribute() : SkipAttribute("test tylko dla Linuksa")
{
    public override Task<bool> ShouldSkip(TestRegisteredContext context)
        => Task.FromResult(!OperatingSystem.IsLinux());
}
