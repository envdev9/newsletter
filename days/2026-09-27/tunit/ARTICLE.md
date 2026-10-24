<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #4 — 27 września 2026

![TUnit](https://img.shields.io/badge/TUnit-2EA44F?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-ekspert-8250DF?style=for-the-badge)

## TUnit: własne asercje, `[AfterEvery]` i retry tylko dla błędów przejściowych

</div>

---

> _"Test, który po cichu ponawia każdy błąd, nie jest odporny — jest ślepy."_

Wczoraj: fixture'y, `[Retry]`, `[Timeout]`, `[BeforeEvery]`. Dziś trzy klocki, które
składają się na **własny język testów** Twojego projektu: asercje domenowe
(`Assert.That(iban).HasValidChecksum()`), hook „po każdym teście” i retry, który wie,
*dlaczego* test padł. Sprawdzone na `.NET SDK 10.0.400` i `TUnit 1.69.0` — **6 testów
przechodzi** (prawdziwy output w [`code/README.md`](code/README.md)).

| 🧩 Temat | 🏷️ API | 💡 W jednym zdaniu |
|---|---|---|
| Asercja ręczna | `Assertion<T>` + extension na `IAssertionSource<T>` | pełna kontrola nad logiką i komunikatem |
| Asercja z generatora | `[GenerateAssertion]` | zwykła metoda `bool` → asercja na `Assert.That` |
| Hook „po” | `[AfterEvery(Test)]` | kod po każdej próbie każdego testu, z dostępem do wyniku |
| Retry warunkowy | `RetryAttribute.ShouldRetry(...)` | ponawiaj tylko wyjątki przejściowe |

---

## 1. 🧱 Własne asercje: dwie drogi

Bohater dnia: `Iban` — rekord z walidacją sumy kontrolnej mod-97. Chcemy pisać:

```csharp
await Assert.That(new Iban("PL61109010140000071219812874")).HasValidChecksum();
```

**Droga 1 — ręcznie.** Dziedziczysz po `Assertion<T>`, implementujesz `CheckAsync` i
`GetExpectation`, a do tego dopisujesz extension na `IAssertionSource<T>` (to ten interfejs
zwraca `Assert.That(...)`):

```csharp
public sealed class IbanChecksumAssertion : Assertion<Iban>
{
    public IbanChecksumAssertion(AssertionContext<Iban> context) : base(context) { }

    protected override Task<AssertionResult> CheckAsync(EvaluationMetadata<Iban> metadata) { ... }
    protected override string GetExpectation() => "to have a valid IBAN checksum";
}

public static IbanChecksumAssertion HasValidChecksum(this IAssertionSource<Iban> source)
{
    source.Context.ExpressionBuilder.Append(".HasValidChecksum()");
    return new IbanChecksumAssertion(source.Context);
}
```

Linijka z `ExpressionBuilder` sprawia, że w komunikacie błędu widać wyrażenie z Twojego
kodu. Zobacz efekt (prawdziwy komunikat z przebiegu, gdy podamy IBAN z błędną sumą):

```
Expected to have a valid IBAN checksum
but suma kontrolna 'PL00109010140000071219812874' jest bledna

at Assert.That(new Iban("PL00109010140000071219812874")).HasValidChecksum()
```

**Droga 2 — generator.** Wystarczy zwykła metoda statyczna zwracająca `bool`
z atrybutem `[GenerateAssertion]` — klasę `Assertion<T>` i extension wygeneruje source
generator:

```csharp
public static partial class IbanGeneratedAssertions
{
    [GenerateAssertion(ExpectationMessage = "to be issued in {country}")]
    public static bool IsFromCountry(this Iban iban, string country) => ...;
}
```

Komunikat porażki (też z przebiegu) — `{country}` podstawiło się z argumentu, a wartość
wypisała się sama:

```
Expected to be issued in DE
but found Iban { Value = PL61109010140000071219812874, Country = PL }
```

Obie asercje łączą się przez `.And`
(`Assert.That(iban).HasValidChecksum().And.IsFromCountry("GB")` — test przechodzi).

> 🎯 **Dlaczego to ważne:** asercje domenowe zamieniają pięć linijek `Assert.That(x.Prop)`
> w jedno zdanie, a — co ważniejsze — **komunikat porażki mówi językiem domeny**.
> Reguła kciuka: generator dla 90% przypadków (predykat bool), ręczna klasa gdy chcesz
> własny komunikat „dlaczego” (jak wyżej: „suma kontrolna … jest błędna”).

---

## 2. 🪝 `[AfterEvery(Test)]`: hook „po” dla całego zestawu

Bliźniak wczorajszego `[BeforeEvery]`: `static` metoda z parametrem `TestContext`, wołana
po **każdej próbie** każdego testu w assembly — bez wpisywania w klasy. Nasz loguje wynik:

```csharp
[AfterEvery(Test)]
public static void LogOutcome(TestContext context)
{
    var state = context.Execution.Result?.State.ToString() ?? "(brak wyniku)";
    Console.WriteLine($"[AfterEvery] {context.Metadata.TestName} => {state}");
}
```

Zaobserwowane: hook widzi **wynik** (`Passed`/`Failed`) i wpada do „Standard output” danego
testu — inaczej niż `[After(TestSession)]` z wczoraj, którego `Console` do wyniku nie
trafiał. Dostaje wołanie także po nieudanych próbach `[Retry]` (patrz niżej).

> 🎯 **Dlaczego to ważne:** to miejsce na zbieranie artefaktów diagnostycznych **tylko dla
> padniętych testów** (zrzut logów, dump bazy), ujednolicone dla całego projektu.
> _(Sprawdziłem tylko odczyt wyniku i logowanie; samego zbierania artefaktów nie testowałem.)_

---

## 3. 🎯 Retry warunkowy: ponawiaj tylko to, co przejściowe

`[Retry(n)]` z wczoraj ponawia **wszystko**, także prawdziwe błędy logiki. Klasa
`RetryAttribute` ma jednak wirtualną metodę `ShouldRetry`, więc własny atrybut robi to
precyzyjnie:

```csharp
public sealed class RetryOnTransientAttribute(int times) : RetryAttribute(times)
{
    public override Task<bool> ShouldRetry(TestContext context, Exception exception, int currentRetryAttempt)
        => Task.FromResult(exception is TransientException);
}
```

Dwa zmierzone scenariusze (log z prawdziwych przebiegów):

**a) wyjątek przejściowy → retry, przechodzi za trzecim razem:**

```
[Transient] proba 1
[AfterEvery] Przejsciowy_Blad_JestPonawiany => Failed
[ShouldRetry] proba=1, wyjatek=TransientException
[Transient] proba 2
[AfterEvery] Przejsciowy_Blad_JestPonawiany => Failed
[ShouldRetry] proba=2, wyjatek=TransientException
[Transient] proba 3
[AfterEvery] Przejsciowy_Blad_JestPonawiany => Passed
```

**b) błąd asercji → brak retry, test od razu pada** (w osobnym, tymczasowym teście —
usuniętym z repo, bo celowo się wywala):

```
[Logic] proba 1
[AfterEvery] Logiczny_Blad_NieJestPonawiany => Failed
[ShouldRetry] proba=1, wyjatek=AssertionException
failed Logiczny_Blad_NieJestPonawiany
  total: 1  failed: 1
```

Uwaga na numerację: `currentRetryAttempt` w `ShouldRetry` był **1** po pierwszej
porażce (a `CurrentRetryAttempt` w teście z wczoraj — 0 dla pierwszej próby). Analizator
TUnit zabrania też własnego `[AttributeUsage]` na takim atrybucie (błąd `TUnit0028`).

> 🎯 **Dlaczego to ważne:** ślepy `[Retry]` zamienia realny błąd w „flaky, ale zielone”.
> Retry warunkowy zostawia plaster tam, gdzie jest sens (sieć, zewnętrzne API), a błąd
> logiki nadal kończy się czerwono i od razu.

---

## ✅ Co zweryfikowano, a co nie

- ✔️ `dotnet test`: **6/6 przeszło** (TUnit 1.69.0, .NET SDK 10.0.400); komunikaty błędów,
  log `[AfterEvery]` i sekwencje retry cytowane powyżej pochodzą z tych przebiegów.
- ✔️ Brak retry dla `AssertionException` — potwierdzone tymczasowym testem (1 próba, padł),
  którego nie ma w repo.
- ⚠️ Nie testowałem: `[AfterEvery(Class/Assembly)]`, testów z `WebApplicationFactory`
  (osobny temat na kolejne wydanie), własnych asercji na typach generycznych/kolekcjach,
  ani tego, jak `ShouldRetry` współgra z `[Timeout]`.
- ⚠️ Nazw i sygnatur (`Assertion<T>`, `AssertionContext<T>`, `EvaluationMetadata<T>`,
  `ShouldRetry`) nie brałem z dokumentacji, tylko sprawdziłem, że kompilują się i działają
  na 1.69.0 — w innych wersjach TUnit API asercji potrafi się zmieniać.
- ⚠️ `global.json` z `Microsoft.Testing.Platform` wciąż obowiązkowy na .NET 10 SDK.
  Wskazówka: `dotnet test` bez `--results-directory` zapisuje `TestResults/` w bieżącym
  katalogu roboczym (nie w katalogu projektu) — u mnie wylądowało to poza projektem.

**Pełny, uruchamialny przykład:** [`code/TunitCustom/`](code/TunitCustom/).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — komendy + prawdziwy output `dotnet test`.

---

<div align="center">

[← wróć do wydania #4 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
