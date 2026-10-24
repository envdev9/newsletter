using AuthTestKit;

namespace AuthApi.Security.Tests;

public static class AssemblyHooks
{
    [AfterEvery(Assembly)]
    public static void Report(AssemblyHookContext context)
    {
        Console.WriteLine($"=== [AuthApi.Security.Tests] [AfterEvery(Assembly)] PID={Environment.ProcessId} " +
                          $"testow={context.TestCount} AuthFixture.InitializeCount={AuthFixture.InitializeCount} ===");
    }
}
