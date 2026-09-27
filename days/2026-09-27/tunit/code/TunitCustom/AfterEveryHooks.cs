namespace TunitCustom;

/// <summary>
/// Hook globalny "po": [AfterEvery(Test)] wola sie po KAZDEJ probie kazdego testu w calym
/// zestawie (odpowiednik [BeforeEvery] z wydania #3). Widzi wynik testu -- tu tylko go logujemy.
/// </summary>
public static class AfterEveryHooks
{
    [AfterEvery(Test)]
    public static void LogOutcome(TestContext context)
    {
        var state = context.Execution.Result?.State.ToString() ?? "(brak wyniku)";
        Console.WriteLine($"[AfterEvery] {context.Metadata.TestName} => {state}");
    }
}
