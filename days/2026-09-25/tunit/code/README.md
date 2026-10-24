# Kod do wydania #2 — TUnit: dane, hooki i równoległość

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`). Podstawy TUnit: wydanie #1.

## Fragment prasówki, którego dotyczy ten kod

> Domyślnie TUnit odpala testy równolegle — także testy z jednej klasy i każdy wiersz
> danych osobno. Sterujesz tym atrybutami: `[NotInParallel("klucz")]` (nigdy naraz dla
> wspólnego zasobu), `[DependsOn(nameof(X))]` (po zakończeniu X) i
> `[ParallelLimiter<T>]` (co najwyżej N naraz, `T : IParallelLimit`). Dane: `[Arguments]`
> (inline), `[MethodDataSource]` (metoda statyczna, zwracaj `Func<T>`), `[MatrixDataSource]`
> + `[Matrix]` (iloczyn kartezjański). Hooki `[Before]`/`[After]` z zakresem `Test`
> (instancyjne), `Class` i `Assembly` (statyczne).
> Zmierzone szczyty jednoczesności: domyślnie 6, `NotInParallel` 1, `ParallelLimiter` 2.

## Struktura projektu

```
TunitAdvanced/
├── TunitAdvanced.csproj   # TUnit 1.69.0, net10.0
├── global.json            # wymagany na .NET 10 SDK (Microsoft.Testing.Platform)
├── PriceCalculator.cs     # testowany kod (rabat z zaokrągleniem)
├── DataDrivenTests.cs     # [Arguments], [MethodDataSource], [MatrixDataSource]
├── HookTests.cs           # hooki Test/Class/Assembly + wspólny dziennik zdarzeń
├── ParallelismTests.cs    # scenariusze A-D z pomiarem szczytu jednoczesności
└── .gitignore             # TestResults/, bin/, obj/
```

## Jak odpalić od zera

```bash
# .NET SDK 10 bywa poza domyślnym PATH:
export PATH="$HOME/.dotnet:$PATH"

cd TunitAdvanced
dotnet test --output Detailed
```

`--output Detailed` jest potrzebne, żeby zobaczyć dziennik hooków i raporty
równoległości (Console z przechodzących testów jest inaczej pomijany). Wykonuj to z
folderu projektu — SDK szuka `global.json` od bieżącego katalogu.

## Prawdziwy output (skrócony do istotnych fragmentów)

Przebieg wykonano na `.NET SDK 10.0.400`, `TUnit 1.69.0`. Uwaga o metodzie: uruchomiłem
`dotnet test --project <ścieżka> --output Detailed` z innego katalogu roboczego, z
tymczasowym `global.json` o identycznej treści w katalogu nadrzędnym (bo `global.json`
projektu nie jest widoczny spoza jego folderu). Wariant `cd TunitAdvanced && dotnet test`
z własnym `global.json` projektu jest tym samym mechanizmem co w wydaniu #1, ale
dla tego wydania nie był uruchamiany osobno.

```
passed polowa z zaokragleniem 5.025 -> 5.03 (46ms)
passed ApplyDiscount_Arguments(19.99, 100, 0) (1ms)
passed ApplyDiscount_MethodDataSource(200, 25, 150) (46ms)
passed ApplyDiscount_PoprawnyZakres(101) (33ms)
passed ApplyDiscount_NigdyNieWiekszaNizCena(99.99, 50) (0ms)
passed Work(1) (301ms)
passed Krok1_Utworz (408ms)
passed Krok2_Odczytaj (21ms)
passed Krok3_Usun (18ms)
passed Limited(6) (306ms)
  ... (łącznie 36 wpisów)
  Standard output
    --- Dziennik zdarzen calego przebiegu ---
    [Before Assembly] start przebiegu
    [Before Class]    HookTests
    [Before Test]     Drugi
        ...cialo testu Drugi
    [Before Test]     Pierwszy
        ...cialo testu Pierwszy
    [After  Test]     Drugi
    [After  Test]     Pierwszy
    [After  Class]    HookTests
    [A] domyslnie: szczyt wspolbieznosci = 6
    [C] DependsOn - kolejnosc: Krok1_Utworz -> Krok2_Odczytaj -> Krok3_Usun
    [D] ParallelLimiter(2): szczyt wspolbieznosci = 2
    [B] NotInParallel("shared-resource"): szczyt wspolbieznosci = 1
    [After  Assembly] koniec przebiegu

Test run summary: Passed!
  total: 36
  failed: 0
  succeeded: 36
  skipped: 0
  duration: 3s 418ms
```

**36 testów (15 data-driven: 4+3+2+6; 2 z hooków; 19 z równoległości: 6+4+3+6), 0
nieudanych.** Kolejność wierszy w oryginalnym outpucie jest niedeterministyczna
(równoległość) — dlatego fragment jest skrócony i uporządkowany tematycznie; wartości
szczytów i kolejność `DependsOn` są deterministyczne i pochodzą 1:1 z przebiegu.
