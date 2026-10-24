# Kod do wydania #3 — TUnit: współdzielone fixture'y, retry, timeout, hook globalny

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`). Podstawy TUnit: wydania #1 i #2.

## Fragment prasówki, którego dotyczy ten kod

> Fixture to klasa z `IAsyncInitializer` (asynchroniczny start) i `IAsyncDisposable`
> (sprzątanie). `[ClassDataSource<T>(Shared = ...)]` wstrzykuje ją do konstruktora (atrybut
> na klasie) lub parametru metody (atrybut na metodzie). Zasięg: `PerTestSession` (jedna na
> cały przebieg), `PerClass`, `Keyed` (jedna na klucz, także między klasami), `None`
> (nowa na test). Zmierzone: 7 instancji utworzonych i 7 zwolnionych.
> `[Retry(3)]` powtarza test (każda próba = nowa instancja klasy, licznik musi być `static`),
> `[Timeout(ms)]` przerywa test i anuluje `CancellationToken`. `[BeforeEvery(Test)]` to
> hook `static` wołany przed każdą próbą każdego testu w zestawie.

## Struktura projektu

```
TunitFixtures/
├── TunitFixtures.csproj    # TUnit 1.69.0, net10.0
├── global.json             # wymagany na .NET 10 SDK (Microsoft.Testing.Platform)
├── FakeDatabase.cs         # fixture: IAsyncInitializer + IAsyncDisposable + liczniki
├── SharedStateTests.cs     # PerTestSession / PerClass / Keyed / None
├── SharingAssertionTests.cs# asercje na liczbie unikalnych instancji ([DependsOn])
├── ResilienceTests.cs      # [Retry] i [Timeout]
├── GlobalHooks.cs          # [BeforeEvery(Test)] + raport [After(TestSession)]
└── .gitignore              # TestResults/, bin/, obj/
```

## Jak odpalić od zera

```bash
# .NET SDK 10 bywa poza domyślnym PATH:
export PATH="$HOME/.dotnet:$PATH"

cd TunitFixtures
dotnet test --output Detailed
```

Uruchamiaj z folderu projektu — SDK szuka `global.json` od bieżącego katalogu.
Raport zbiorczy fixture'ów (Console z hooka `[After(TestSession)]` nie trafia do wyniku
`dotnet test`) zapisuje się do pliku:

```bash
cat /tmp/tunit-fixtures-report.txt
```

Żeby zobaczyć porażkę `[Timeout]`: w `ResilienceTests.cs` ustaw `[Timeout(300)]` i
`Task.Delay(5000, cancellationToken)`.

## Prawdziwy output

Uwaga o metodzie: przebieg wykonałem poleceniem `dotnet test --project <ścieżka>` z
innego katalogu roboczego, z tymczasowym `global.json` o identycznej treści w katalogu
nadrzędnym (usuniętym po teście). Wariant `cd TunitFixtures && dotnet test` z własnym
`global.json` nie był uruchamiany osobno.

Wynik (`--output Detailed`, skrócony do istotnych fragmentów):

```
passed Keyed_TenSamKluczTaSamaInstancje (19ms)
passed PerClass_InstancjaNaKlase (1ms)
passed None_SwiezaInstancjaNaTest (3ms)
passed PerTestSession_JednaInstancjaDlaWszystkich (0ms)
passed Timeout_TestMiesciSieWLimicie (107ms)
passed Flaky_PrzechodziDopieroZaTrzecimPodejsciem (0ms)
  Standard output
    [Retry] proba nr 1, CurrentRetryAttempt=0
    [Retry] proba nr 2, CurrentRetryAttempt=1
    [Retry] proba nr 3, CurrentRetryAttempt=2
  ... (łącznie 18 testów)

Test run summary: Passed!
  total: 18
  failed: 0
  succeeded: 18
  skipped: 0
  duration: 2s 504ms
```

Raport z `/tmp/tunit-fixtures-report.txt` (numery id zależą od równoległości i mogą się
różnić między uruchomieniami):

```
=== RAPORT FIXTURE ===
FakeDatabase: utworzono=7, zwolniono=7
PerTestSession: id=2
PerClass A:     id=3
PerClass B:     id=4
Keyed tenant-1: id=1
Keyed tenant-2: id=5
None:           id=6,7
[BeforeEvery] widzial 20 testow
  init    FakeDatabase#1
  init    FakeDatabase#5
  dispose FakeDatabase#1
  dispose FakeDatabase#5
  init    FakeDatabase#3
  init    FakeDatabase#6
  dispose FakeDatabase#3
  dispose FakeDatabase#6
  init    FakeDatabase#4
  dispose FakeDatabase#4
  init    FakeDatabase#7
  dispose FakeDatabase#7
  init    FakeDatabase#2
  dispose FakeDatabase#2
```

`[BeforeEvery]` zobaczył 20 wywołań przy 18 testach, bo `[Retry(3)]` uruchomił jeden test
trzykrotnie (18 − 1 + 3 = 20).

Porażka `[Timeout(300)]` przy `Task.Delay(5000)` (osobny, tymczasowy przebieg):

```
failed Timeout_TestMiesciSieWLimicie (322ms)
  [Test Failure] TimeoutException: Test 'Timeout_TestMiesciSieWLimicie' timed out after 00:00:00.3000000
--- Task Status: Canceled ---
...
  total: 18
  failed: 1
  succeeded: 17
```

Nie zweryfikowano: `[AfterEvery]`, `[BeforeEvery]` dla Class/Assembly, własne asercje.
