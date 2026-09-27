# Kod do wydania #4 — TUnit: własne asercje, `[AfterEvery]`, retry warunkowy

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`). Podstawy TUnit: wydania #1–#3.

## Fragment prasówki, którego dotyczy ten kod

> Własną asercję piszesz na dwa sposoby: ręcznie (`Assertion<T>` + extension na
> `IAssertionSource<T>`, pełna kontrola nad komunikatem) albo generatorem
> (`[GenerateAssertion]` na metodzie `bool`). `[AfterEvery(Test)]` to `static` hook wołany
> po każdej próbie każdego testu i widzący jego wynik. Własny atrybut dziedziczący po
> `RetryAttribute` i nadpisujący `ShouldRetry` ponawia tylko wyjątki przejściowe — błąd
> asercji kończy test od razu.

## Struktura projektu

```
TunitCustom/
├── TunitCustom.csproj        # TUnit 1.69.0, net10.0
├── global.json               # wymagany na .NET 10 SDK (Microsoft.Testing.Platform)
├── Iban.cs                   # obiekt domenowy (walidacja mod-97)
├── IbanAssertions.cs         # Assertion<T> (ręcznie) + [GenerateAssertion]
├── CustomAssertionTests.cs   # użycie, .And, komunikaty błędów
├── AfterEveryHooks.cs        # [AfterEvery(Test)]
├── ConditionalRetryTests.cs  # RetryOnTransientAttribute + TransientException
└── .gitignore                # TestResults/, bin/, obj/
```

## Jak odpalić od zera

```bash
cd TunitCustom
dotnet test --output Detailed --results-directory /tmp/tunit-results
```

Uruchamiaj z folderu projektu — SDK szuka `global.json` od bieżącego katalogu.
`--results-directory` trzyma raport HTML poza repo (domyślnie `TestResults/` ląduje w
bieżącym katalogu roboczym).

Uwaga o metodzie: moje przebiegi wykonałem poleceniem `dotnet test --project <ścieżka>`
z innego katalogu roboczego, z tymczasowym `global.json` o identycznej treści w katalogu
nadrzędnym. Wariant `cd TunitCustom && dotnet test` nie był uruchamiany osobno.

## Prawdziwy output

Skrócony wynik `--output Detailed`:

```
passed AsercjeMoznaLaczyc_And (14ms)
passed PoprawnyIban_PrzechodziRecznaAsercje (34ms)
passed PoprawnyIban_PrzechodziAsercjeWygenerowana (39ms)
passed BlednyIban_RzucaAssertionException_ZNaszymKomunikatem (31ms)
  Standard output
    Expected to have a valid IBAN checksum
    but suma kontrolna 'PL00109010140000071219812874' jest bledna

    at Assert.That(new Iban("PL00109010140000071219812874")).HasValidChecksum()
    [AfterEvery] BlednyIban_RzucaAssertionException_ZNaszymKomunikatem => Passed
passed Przejsciowy_Blad_JestPonawiany (26ms)
  Standard output
    [Transient] proba 1
    [AfterEvery] Przejsciowy_Blad_JestPonawiany => Failed
    [ShouldRetry] proba=1, wyjatek=TransientException
    [Transient] proba 2
    [AfterEvery] Przejsciowy_Blad_JestPonawiany => Failed
    [ShouldRetry] proba=2, wyjatek=TransientException
    [Transient] proba 3
    [AfterEvery] Przejsciowy_Blad_JestPonawiany => Passed
passed ZlyKraj_KomunikatZGeneratora (19ms)
  Standard output
    Expected to be issued in DE
    but found Iban { Value = PL61109010140000071219812874, Country = PL }

    at Assert.That(new Iban("PL61109010140000071219812874")).IsFromCountry("DE")
    [AfterEvery] ZlyKraj_KomunikatZGeneratora => Passed

Test run summary: Passed!
  total: 6
  failed: 0
  succeeded: 6
  skipped: 0
```

Brak retry dla błędu logiki (tymczasowy test `[RetryOnTransient(3)]` z asercją, która
musi zawieść; usunięty z repo):

```
[Logic] proba 1
[AfterEvery] Logiczny_Blad_NieJestPonawiany => Failed
[ShouldRetry] proba=1, wyjatek=AssertionException
Test run summary: Failed!  total: 1  failed: 1
```

Nie zweryfikowano: `[AfterEvery(Class/Assembly)]`, `WebApplicationFactory`, współgranie
`ShouldRetry` z `[Timeout]`.
