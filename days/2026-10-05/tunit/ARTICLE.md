<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #12 — 5 października 2026

![TUnit](https://img.shields.io/badge/TUnit-2EA44F?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-ekspert-8250DF?style=for-the-badge)

## TUnit: `[AfterEvery(Assembly)]` i `[AfterEvery(Class)]` z DWOMA projektami testowymi naraz

</div>

---

> _"Jeden projekt testowy to teoria. Dwa projekty testowe to pomiar."_

W wydaniach #4, #7 i #9 poznaliśmy całą rodzinę `[AfterEvery]`: `Test` → `Class` →
`Assembly`. Każde z tych wydań kończyło się jednak tą samą zastrzeżoną niepewnością: w
repo był tylko **jeden** projekt testowy, więc pytanie "czy `[AfterEvery(Assembly)]`
odpala się raz na assembly, czy raz na cały przebieg `dotnet test`" było czysto
teoretyczne — przy jednym projekcie te dwie interpretacje dają identyczny wynik. Dziś to
domykamy: solution z **dwoma** projektami testowymi (`Catalog.Tests`, `Shipping.Tests`),
jeden `dotnet test` na poziomie solution, i realny pomiar PID procesu oraz liczników
statycznych w każdym z nich. Sprawdzone na `.NET SDK 10.0.400`, `TUnit 1.72.16` (nowsza
niż 1.72.10 z #9 — zweryfikowane na NuGet) — **9/9 testów przechodzi**, powtórzone
dwukrotnie bez flakowania, z identycznym wzorcem przy każdym przebiegu.

| 🧩 Pytanie | 🏷️ Jak zmierzone | 💡 Wynik |
|---|---|---|
| Czy `[AfterEvery(Assembly)]` widzi testy z OBU projektów? | `AssemblyHookContext.TestCount` w każdym projekcie z osobna | nie — każdy projekt widzi WYŁĄCZNIE swoje testy (5 vs 4) |
| Czy to jeden proces, czy dwa? | `Environment.ProcessId` w hooku każdego projektu | dwa RÓŻNE PID-y — osobne procesy systemowe |
| Czy `dotnet test` odpala projekty po kolei, czy naraz? | kolejność linii w `--output Detailed` | NARAZ — output się przeplata, czasy trwania pokrywają się |
| Czy statyczny stan przecieka między projektami? | identycznie nazwana klasa `SharedState` w obu projektach | nie — dwa niezależne liczniki, zero wzajemnego wpływu |

---

## 1. 🏗️ Co jest pod testem: dwa niezależne projekty w jednym solution

Zamiast jednego projektu testowego z wielu poprzednich wydań — dziś **solution**
(`TunitMultiProject.slnx`) z dwoma osobnymi projektami TUnit, każdy ze swoją logiką i
swoim zestawem hooków:

```
code/
├── TunitMultiProject.slnx
├── global.json                 # "test": { "runner": "Microsoft.Testing.Platform" }
├── Catalog.Tests/               # projekt #1: 2 klasy testowe, 5 testów
│   ├── PricingCalculator.cs     # logika pod testem (VAT, rabat)
│   ├── PricingTests.cs          # 3 testy
│   ├── DiscountTests.cs         # 2 testy
│   ├── SharedState.cs           # statyczne liczniki TEGO projektu
│   ├── AssemblyHooks.cs         # [AfterEvery(Assembly)]
│   └── ClassHooks.cs            # [AfterEvery(Class)]
└── Shipping.Tests/              # projekt #2: 1 klasa testowa, 4 testy
    ├── ShippingCostCalculator.cs
    ├── ShippingCostTests.cs     # 4 testy
    ├── SharedState.cs           # IDENTYCZNA nazwa klasy jak w Catalog.Tests -- celowo
    ├── AssemblyHooks.cs
    └── ClassHooks.cs
```

Logika biznesowa (`PricingCalculator`, `ShippingCostCalculator`) jest celowo trywialna —
clou wydania to zachowanie hooków, nie VAT czy stawki za kilogram. Kluczowy
szczegół: **obie klasy `SharedState` mają identyczną nazwę, identyczną strukturę i
identyczne API**, ale żyją w dwóch różnych projektach (`Catalog.Tests.SharedState` vs
`Shipping.Tests.SharedState`). To jest zamierzony eksperyment kontrolny — jeśli coś w
`dotnet test` miałoby "zlać" stan między projektami, zobaczylibyśmy to na liczniku.

## 2. 📍 `[AfterEvery(Assembly)]` widzi WYŁĄCZNIE swój projekt

Hook w `Catalog.Tests/AssemblyHooks.cs`:

```csharp
public static class AssemblyHooks
{
    [AfterEvery(Assembly)]
    public static void Report(AssemblyHookContext context)
    {
        var n = SharedState.RecordAssemblyFire();

        var passed = context.TestClasses
            .SelectMany(c => c.Tests)
            .Count(t => t.Execution.Result?.State == TestState.Passed);

        Console.WriteLine($"=== [Catalog.Tests] [AfterEvery(Assembly)] wywolanie #{n} ===");
        Console.WriteLine($"  PID procesu = {Environment.ProcessId}");
        Console.WriteLine($"  Testow w TEJ assembly: {context.TestCount} (passed={passed})");
        Console.WriteLine($"  SharedState.CatalogTestsSeen = {SharedState.CatalogTestsSeen}");
    }
}
```

Analogiczny hook w `Shipping.Tests` różni się tylko nazwą w logu. Realny output
`dotnet test` uruchomiony **na poziomie solution** (oba projekty w jednym wywołaniu):

```
=== [Catalog.Tests] [AfterEvery(Assembly)] wywolanie #1 ===
  PID procesu = 576190
  Testow w TEJ assembly: 5 (passed=5)
  SharedState.CatalogTestsSeen (static pole TYLKO tego projektu) = 2

=== [Shipping.Tests] [AfterEvery(Assembly)] wywolanie #1 ===
  PID procesu = 576189
  Testow w TEJ assembly: 4 (passed=4)
  SharedState.ShippingTestsSeen (static pole TYLKO tego projektu) = 1
```

`Catalog.Tests` ma 5 testów (2 klasy), `Shipping.Tests` ma 4 testy (1 klasa) — każdy hook
zaraportował **dokładnie liczbę testów swojego własnego projektu**, nie `9` (suma obu).
Gdyby `[AfterEvery(Assembly)]` był odpalany "raz na cały przebieg `dotnet test`"
(hipoteza, którą trzeba było wykluczyć), `context.TestCount` musiałby wynosić 9 w obu
miejscach albo hook odpaliłby się tylko raz, w jednym z dwóch projektów. Zamiast tego
odpalił się **dwa razy, osobno, z poprawnym podziałem 5/4**.

> 🎯 **Dlaczego to ważne:** jeśli piszesz hook `[AfterEvery(Assembly)]`, który np.
> publikuje zbiorczy raport "ile testów przeszło w tym `dotnet test`" do systemu CI, i
> Twoje solution ma więcej niż jeden projekt testowy — **dostaniesz tyle wywołań hooka,
> ile masz projektów testowych**, każde z osobnym, częściowym licznikiem. Agregację
> "łącznie X z Y" musisz zrobić sam poza TUnit (np. po stronie CI, zbierając wyniki z
> wielu procesów), hook assembly-level Ci tego nie da za darmo.

## 3. 🖥️ To są dwa RÓŻNE procesy systemowe, nie dwa wątki jednego

`Environment.ProcessId` w logu powyżej: `576190` dla `Catalog.Tests`, `576189` dla
`Shipping.Tests` — **różne PID-y**. Drugi przebieg (powtórzony niezależnie) dał
`576305`/`576304` — inne liczby (bo to nowe procesy przy nowym wywołaniu `dotnet test`),
ale wciąż **dwa różne PID-y w ramach JEDNEGO przebiegu**, konsekwentnie.

To nie jest szczegół czysto kosmetyczny. `Microsoft.Testing.Platform` (hosting, na którym
stoi TUnit — patrz wydanie #1) kompiluje każdy projekt testowy do samodzielnego pliku
wykonywalnego. `dotnet test` na poziomie solution nie "ładuje" wielu assembly testowych do
jednego procesu — **uruchamia każdy projekt jako osobny proces** i zbiera wyniki. Stąd
`[AfterEvery(Assembly)]` nie ma żadnej możliwości "zobaczyć" drugiego projektu nawet
teoretycznie — nie ma do niego dostępu przez pamięć procesu, bo to inny proces w systemie
operacyjnym.

## 4. ⏱️ `dotnet test` na solution odpala projekty NARAZ, nie po kolei

Dodatkowa, nieplanowana obserwacja z tego samego przebiegu: linie `Running tests from
...` dla obu `.dll` pojawiły się w logu **jedna po drugiej, natychmiast**, a nie
"najpierw cały `Catalog.Tests`, potem cały `Shipping.Tests`". Standard output z obu
projektów się przeplata (hook `Catalog.Tests` i wyniki testów `Shipping.Tests` w tej samej
sekcji logu), a czasy trwania obu procesów pokrywają się: `1s 141ms` i `1s 239ms` w
przebiegu #1, `1s 335ms` i `1s 341ms` w przebiegu #2 — to nie jest "project A skończony
po 1.1s, project B zaczął się po project A i trwał kolejne 1.2s" (co dałoby sumę ~2.3s w
jednej linii czasowej), to dwa procesy **działające równolegle**, co potwierdza też
całkowity czas przebiegu (`1s 937ms`/`2s 039ms` — bliski czasowi NAJDŁUŻSZEGO projektu,
nie SUMIE obu).

> 🎯 **Dlaczego to ważne:** przy wielu projektach testowych w solution `dotnet test`
> domyślnie skaluje się w poprzek projektów, nie tylko w poprzek testów wewnątrz jednego
> projektu (równoległość wewnątrz-assembly to temat wydania #2). To dobra wiadomość dla
> czasu CI — ale też powód, czemu hook `[AfterEvery(Assembly)]` w jednym projekcie
> **nigdy** nie powinien zakładać, że w danym momencie jest jedynym aktywnym kodem
> testowym w systemie (np. nie pisz do tego samego pliku na dysku bez synchronizacji
> między-procesowej, jeśli oba projekty mogłyby pisać naraz).

## 5. 🧮 `[AfterEvery(Class)]` liczy się per projekt, nie globalnie

`Catalog.Tests` ma dwie klasy (`PricingTests`, `DiscountTests`) → hook `[AfterEvery(Class)]`
odpalił się tam **dwa razy**. `Shipping.Tests` ma jedną klasę (`ShippingCostTests`) → hook
odpalił się tam **raz**. Łącznie w całym przebiegu solution: trzy wywołania
`[AfterEvery(Class)]`, ale żadne z nich nie "widziało" klas z drugiego projektu —
numeracja (`#1`, `#2`) w każdym projekcie zaczyna się od zera niezależnie, bo to osobny
proces z osobną pamięcią statyczną:

```
=== [Catalog.Tests] [AfterEvery(Class)] wywolanie #1: klasa DiscountTests ===
  Testow w klasie: 2 (passed=2)
=== [Catalog.Tests] [AfterEvery(Class)] wywolanie #2: klasa PricingTests ===
  Testow w klasie: 3 (passed=3)
=== [Catalog.Tests] [AfterEvery(Assembly)] wywolanie #1 ===
  ...

=== [Shipping.Tests] [AfterEvery(Class)] wywolanie #1: klasa ShippingCostTests ===
  Testow w klasie: 4 (passed=4)
=== [Shipping.Tests] [AfterEvery(Assembly)] wywolanie #1 ===
  ...
```

Widać też coś, co było tylko domyślne w wydaniu #9: **w ramach jednej assembly**
wszystkie `[AfterEvery(Class)]` kończą się PRZED jedynym `[AfterEvery(Assembly)]` tej
samej assembly — kolejność w logu to `Class #1`, `Class #2`, dopiero potem `Assembly #1`,
konsekwentnie w obu projektach i w obu przebiegach. `Assembly` naprawdę jest "na końcu",
nie "równolegle do" klas tej samej assembly.

## 6. 🔒 Statyczny stan nie przecieka między projektami — nawet przy identycznej nazwie klasy

Najbardziej namacalny dowód z tego wydania: `Catalog.Tests.SharedState` i
`Shipping.Tests.SharedState` to **dwie różne klasy o identycznej nazwie, strukturze i
logice** (ten sam kod, skopiowany między projektami celowo). Po przebiegu:

- `SharedState.CatalogTestsSeen` (tylko w `Catalog.Tests`) = **2** (dwie klasy odpaliły
  swój `[AfterEvery(Class)]`).
- `SharedState.ShippingTestsSeen` (tylko w `Shipping.Tests`) = **1** (jedna klasa).

Gdyby to był ten sam typ w tej samej pamięci (np. gdyby `dotnet test` na solution
ładował oba projekty do jednego `AppDomain`/procesu), drugi licznik "widziałby" wpływ
pierwszego albo rzucił konflikt nazw przy kompilacji. Nic z tego się nie dzieje — bo to
są dwie kompletnie osobne assembly w dwóch osobnych procesach (sekcja 3).

> 🎯 **Dlaczego to ważne:** to rozwiewa realną obawę zespołów migrujących z jednego
> wielkiego projektu testowego na wiele mniejszych (np. per-moduł, żeby skrócić czas
> budowania/CI) — "a co jeśli mój singleton/cache statyczny w kodzie testowym się
> pomieszają między projektami". Nie pomieszają się. Granica projektu testowego = granica
> assembly = granica procesu = granica całej pamięci statycznej, bez wyjątków.

---

## ✅ Co zweryfikowano, a co nie

- ✔️ `dotnet test` na poziomie solution (`TunitMultiProject.slnx`, dwa projekty): **9/9
  przeszło** (5 w `Catalog.Tests`, 4 w `Shipping.Tests`), TUnit 1.72.16, .NET SDK
  10.0.400, net10.0 — powtórzone dwukrotnie, identyczny wzorzec przy każdym przebiegu
  (różne PID-y, te same liczby wywołań hooków). Pełny log w [`code/README.md`](code/README.md).
- ✔️ TUnit 1.72.16 to aktualna wersja na NuGet w chwili pisania (`dotnet add package
  TUnit --version "*"`) — nowsza niż 1.72.10 z wydania #9.
- ✔️ `[AfterEvery(Assembly)]` z WIELOMA projektami testowymi w jednym `dotnet test`: **to
  domyka pytanie otwarte od wydań #7/#9** — hook odpala się RAZ NA PROJEKT (assembly), z
  `context.TestCount` ograniczonym do testów TEGO projektu, nigdy do sumy wszystkich
  projektów w solution.
- ✔️ Dowód procesowy: `Environment.ProcessId` różny dla każdego projektu w tym samym
  przebiegu `dotnet test` — `Microsoft.Testing.Platform` uruchamia każdy projekt testowy
  jako osobny proces systemowy, nie jako osobny wątek/AppDomain w jednym procesie.
- ✔️ Obserwacja dodatkowa (nieplanowana): `dotnet test` na solution z wieloma projektami
  odpala je WSPÓŁBIEŻNIE (przeplatający się output, pokrywające się czasy trwania), nie
  sekwencyjnie.
- ✔️ `[AfterEvery(Class)]` z wieloma projektami: liczy się niezależnie per projekt (2 w
  `Catalog.Tests`, 1 w `Shipping.Tests`), kolejność `Class` → `Assembly` zachowana w
  obrębie każdej assembly z osobna.
- ✔️ Izolacja stanu statycznego między projektami: dwie identycznie nazwane klasy
  (`SharedState`) w dwóch projektach, zero wzajemnego wpływu — zmierzone, nie założone.
- ⚠️ Nie testowałem: Aspire + TUnit (`DistributedApplicationTestingBuilder` — zajmuje się
  tym dziś osobne wydanie rubryki Aspire), odświeżanie tokenu JWT (`refresh_token`),
  `RS256`/klucze asymetryczne w JWT (dotychczas tylko `HS256`/klucz symetryczny — patrz
  wydanie #9). Oba tematy zostają na kolejne wydania.
- ⚠️ Nie testowałem: zachowanie przy WIĘKSZEJ liczbie projektów testowych (3+) ani przy
  projektach, które się nawzajem referencjonują (`ProjectReference` między dwoma
  projektami testowymi) — tu dwa projekty są całkowicie niezależne, bez wspólnych
  referencji poza samym TUnit.

**Pełny, uruchamialny przykład:** [`code/Catalog.Tests/`](code/Catalog.Tests/) +
[`code/Shipping.Tests/`](code/Shipping.Tests/), spięte w jedno
[`code/TunitMultiProject.slnx`](code/TunitMultiProject.slnx).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — komendy + prawdziwy output `dotnet test`.

---

<div align="center">

[← wróć do wydania #12 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
