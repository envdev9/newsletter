namespace TunitWebApi.Tests;

/// <summary>
/// [AfterEvery(Class)] -- brakujacy element rodziny [AfterEvery] w tej rubryce:
/// [AfterEvery(Test)] poznalismy w wydaniu #4, [AfterEvery(Assembly)] w wydaniu #7.
/// Dzis [AfterEvery(Class)]: hook globalny wolany RAZ PO KAZDEJ klasie testowej w calym
/// zestawie (nie raz na caly assembly jak Assembly, nie raz na kazdy test jak Test).
///
/// Sygnatura (static void Method(ClassHookContext context)) zadziala od razu -- ten sam
/// wzorzec co [AfterEvery(Assembly)] z AssemblyHookContext w wydaniu #7.
/// ClassHookContext.ClassType identyfikuje, KTORA klasa wlasnie sie skonczyla;
/// ClassHookContext.Tests (IReadOnlyList&lt;TestContext&gt;) pozwala policzyc wyniki
/// (TestContext.Execution.Result?.State) bez wlasnego liczenia w kazdym tescie z osobna.
/// </summary>
public static class ClassHooks
{
    private static int _invocationCount;
    public static int InvocationCount => _invocationCount;

    [AfterEvery(Class)]
    public static void Report(ClassHookContext context)
    {
        var n = Interlocked.Increment(ref _invocationCount);

        var passed = context.Tests.Count(t => t.Execution.Result?.State == TestState.Passed);
        var failed = context.Tests.Count(t => t.Execution.Result?.State == TestState.Failed);
        var inne = context.TestCount - passed - failed;

        Console.WriteLine($"=== [AfterEvery(Class)] wywolanie #{n}: klasa {context.ClassType.Name} ===");
        Console.WriteLine($"  Testow w klasie: {context.TestCount} (passed={passed}, failed={failed}, inne={inne})");
        Console.WriteLine($"  ApiFixture.InitializeCount (globalnie, po tej klasie) = {ApiFixture.InitializeCount}");
    }
}
