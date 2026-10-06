using TUnit.Core;

namespace AuthTestKit;

public static class KitHooks
{
    [AfterEvery(Assembly)]
    public static void KitAfterAssembly(AssemblyHookContext context)
    {
        Console.WriteLine($"=== [AuthTestKit] hook zdefiniowany W BIBLIOTECE, odpalony dla assembly {context.Assembly.GetName().Name} ===");
    }
}
