using DataLab.Core;
using Microsoft.Extensions.DependencyInjection;
using TUnit.Core;
using TUnit.Core.Interfaces;

namespace DataLab.Tests;

/// <summary>
/// Własny konstruktor klas testowych: każda instancja klasy testowej dostaje WŁASNY scope DI.
/// Scope sprzątamy w OnTestEnd (ITestEndEventReceiver).
/// </summary>
public sealed class DiClassConstructor : IClassConstructor, ITestEndEventReceiver
{
    private static readonly ServiceProvider Root = Composition.Build();
    private static readonly Dictionary<object, IServiceScope> Scopes = new(ReferenceEqualityComparer.Instance);

    public Task<object> Create(Type type, ClassConstructorMetadata classConstructorMetadata)
    {
        var scope = Root.CreateScope();
        var instance = ActivatorUtilities.CreateInstance(scope.ServiceProvider, type);
        lock (Scopes) Scopes[instance] = scope;
        return Task.FromResult(instance);
    }

    public ValueTask OnTestEnd(TestContext context)
    {
        var instance = context.Metadata.TestDetails.ClassInstance;
        IServiceScope? scope;
        lock (Scopes)
        {
            Scopes.Remove(instance, out scope);
        }
        scope?.Dispose();
        return ValueTask.CompletedTask;
    }

    public int Order => 0;
}
