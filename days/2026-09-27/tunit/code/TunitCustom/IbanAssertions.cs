using TUnit.Assertions.Attributes;
using TUnit.Assertions.Core;

namespace TunitCustom;

// ---------------------------------------------------------------------------
// Sposob 1 (recznie): klasa dziedziczaca po Assertion<T> + metoda rozszerzajaca
// na IAssertionSource<T>. Pelna kontrola nad komunikatem bledu.
// ---------------------------------------------------------------------------
public sealed class IbanChecksumAssertion : Assertion<Iban>
{
    public IbanChecksumAssertion(AssertionContext<Iban> context) : base(context) { }

    protected override Task<AssertionResult> CheckAsync(EvaluationMetadata<Iban> metadata)
    {
        if (metadata.Exception is not null)
            return Task.FromResult(AssertionResult.Failed($"zrodlo rzucilo {metadata.Exception.GetType().Name}"));

        var iban = metadata.Value;
        if (iban is null)
            return Task.FromResult(AssertionResult.Failed("IBAN byl null"));

        return Task.FromResult(iban.HasValidChecksum()
            ? AssertionResult.Passed
            : AssertionResult.Failed($"suma kontrolna '{iban.Value}' jest bledna"));
    }

    protected override string GetExpectation() => "to have a valid IBAN checksum";
}

public static class IbanAssertionExtensions
{
    public static IbanChecksumAssertion HasValidChecksum(this IAssertionSource<Iban> source)
    {
        source.Context.ExpressionBuilder.Append(".HasValidChecksum()");
        return new IbanChecksumAssertion(source.Context);
    }
}

// ---------------------------------------------------------------------------
// Sposob 2 (generator): [GenerateAssertion] na zwyklej metodzie statycznej.
// Generator zrodel tworzy za nas klase Assertion<T> i extension na Assert.That.
// ---------------------------------------------------------------------------
public static partial class IbanGeneratedAssertions
{
    [GenerateAssertion(ExpectationMessage = "to be issued in {country}")]
    public static bool IsFromCountry(this Iban iban, string country)
        => iban.Country.Equals(country, StringComparison.OrdinalIgnoreCase);
}
