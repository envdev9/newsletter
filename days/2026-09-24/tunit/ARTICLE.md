<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #1 — 24 września 2026

![TUnit](https://img.shields.io/badge/TUnit-2EA44F?style=for-the-badge)

## TUnit: pierwszy test bez refleksji w runtime

</div>

---

> _"xUnit odkrywa Twoje testy za każdym razem, gdy je odpalasz - skanując assembly
> refleksją. TUnit wie, jakie masz testy, zanim jeszcze program się uruchomi - bo
> kompilator wygenerował dla nich kod w momencie budowania."_

Dziś zaczynamy od zera nowy dział: **TUnit** - nowoczesny framework testowy dla .NET,
alternatywa dla xUnit/NUnit/MSTest, które większość z nas zna na pamięć. Pierwszy test,
pierwsze asercje, i jedna rzecz, która realnie odróżnia TUnit od "tej trójki": zamiast
refleksji w czasie działania programu, TUnit używa **generatorów źródeł** (source
generators) już w czasie kompilacji. Sprawdzone lokalnie na `.NET SDK 10.0.400` i
`TUnit 1.69.0` - kod w [`code/`](code/) realnie się buduje i **3 testy przechodzą**.

---

## Czym w ogóle jest TUnit i po co nam kolejny framework testowy

Jeśli pisałeś testy w xUnit, NUnit albo MSTest, znasz ten schemat: klasa z testami,
atrybut `[Fact]`/`[Test]`/`[TestMethod]` na metodzie, `Assert.Equal(oczekiwana,
wynik)`. TUnit (open source, autor: Tom Longhurst) trzyma się tego samego,
znajomego kształtu - `[Test]` na metodzie, klasa jako kontener - więc nie musisz uczyć
się nowego paradygmatu. Różnica jest **pod maską**, i to ona jest dziś tematem.

### Refleksja w runtime kontra generatory źródeł - skąd w ogóle ta różnica

xUnit, NUnit i MSTest działają tak: gdy odpalasz `dotnet test`, framework w czasie
**działania programu** skanuje Twoje assembly refleksją (`Assembly.GetTypes()`,
`GetMethods()`, szukanie atrybutów) i dopiero wtedy buduje listę testów do uruchomienia.
To działa, ale ma dwa realne koszty:

1. **Czas startu.** Im więcej testów i klas w assembly, tym dłużej trwa samo
   "odkrywanie", zanim jakikolwiek test faktycznie ruszy.
2. **Refleksja nie współgra z AOT/trimmingiem.** Native AOT i trimming (wycinanie
   nieużywanego kodu z finalnej binarki) polegają na tym, że kompilator **statycznie**
   wie, co jest używane. Refleksja w runtime psuje tę analizę - trimmer nie ma jak
   wiedzieć, że `GetMethods()` znajdzie akurat Twoją metodę testową, więc albo
   zachowuje więcej kodu "na wszelki wypadek", albo trzeba go ręcznie o tym uczyć.

TUnit odwraca kolejność: **generator źródeł** (kod, który dopisuje kolejny kod - wbudowany
mechanizm C# od paru lat, tu wykorzystany do granic możliwości) analizuje Twoje klasy
testowe **w momencie kompilacji** i generuje gotową, statyczną listę testów jako zwykły
kod C#. Żadnego skanowania w runtime - program od razu wie, jakie testy ma uruchomić,
bo ta wiedza jest "wypieczona" w binarce. To przekłada się na szybszy start testów
(zwłaszcza przy dużych zestawach) i pełną kompatybilność z Native AOT/trimmingiem - coś,
czego starsze frameworki oparte na refleksji nie potrafią zaoferować bez kompromisów.

### Pierwszy test

Sama definicja testu wygląda znajomo - zwykła klasa, zwykła metoda, atrybut `[Test]`:

```csharp
namespace TunitDemo;

public class CalculatorTests
{
    [Test]
    public async Task Add_TwoLiczby_ZwracaSume()
    {
        var calculator = new Calculator();

        var result = calculator.Add(2, 3);

        await Assert.That(result).IsEqualTo(5);
    }
}
```

Dwie rzeczy, które od razu rzucają się w oczy w porównaniu do `Assert.Equal(5, result)`
z xUnit:

- **`Assert.That(result).IsEqualTo(5)`** - płynne (fluent) API zamiast statycznej
  metody z dwoma argumentami. Czytasz to jak zdanie: "asercja, że wynik jest równy 5".
  Nie trzeba pamiętać, czy pierwszy argument to wartość oczekiwana, czy faktyczna (klasyczna
  pułapka `Assert.Equal(expected, actual)`, łatwa do pomylenia).
- **`await`** - asercje w TUnit są asynchroniczne. To nie kosmetyka: dzięki temu framework
  może np. równolegle zbierać wyniki wielu asercji w jednym teście (`Assert.Multiple`) bez
  blokowania wątku. Na pierwszy rzut oka to dodatkowy `await` do napisania, ale w praktyce
  kompilator przypomni Ci, jeśli go zapomnisz (ostrzeżenie o niezaawaitowanym Tasku).

### Asercje na wyjątkach i wartościach prostych

Drugi test w projekcie pokazuje asercję na wyjątku - zamiast `Assert.Throws<T>(() =>
...)` znanego z xUnit, w TUnit też piszesz to przez fluent `Assert.That`:

```csharp
[Test]
public async Task Divide_PrzezZero_RzucaWyjatek()
{
    var calculator = new Calculator();
    var dzialanie = () => calculator.Divide(10, 0);

    await Assert.That(dzialanie).Throws<DivideByZeroException>();
}
```

A trzeci - że proste asercje na `bool` (`IsTrue()`/`IsFalse()`) czytają się równie
naturalnie jak te na liczbach czy stringach. Pełny kod wszystkich trzech testów:
[`code/TunitDemo/CalculatorTests.cs`](code/TunitDemo/CalculatorTests.cs).

### Pułapka, na którą trafisz przy pierwszym `dotnet test` - i jak ją ominąć

To jest coś, czego dokumentacja "Hello World" zwykle nie mówi, a ja trafiłem na to od
razu przy pierwszym uruchomieniu: na **.NET 10 SDK** samo `dotnet test` w projekcie
TUnit kończy się błędem:

```
error : Testing with VSTest target is no longer supported by Microsoft.Testing.Platform
on .NET 10 SDK and later. If you use dotnet test, you should opt-in to the new dotnet
test experience.
```

Powód: TUnit (jak MSTest i NUnit w najnowszych wersjach) korzysta z **Microsoft.Testing.Platform**
(w skrócie MTP) - nowego, lżejszego "silnika" do uruchamiania testów, który zastępuje
starszy VSTest. Na .NET 10 SDK trzeba **jawnie** przełączyć `dotnet test` na nowy silnik.
Robi się to jednym plikiem `global.json` obok projektu:

```json
{
  "test": {
    "runner": "Microsoft.Testing.Platform"
  }
}
```

Po tym `dotnet test` działa dokładnie tak, jak się spodziewasz. Ten plik jest już w
[`code/TunitDemo/global.json`](code/TunitDemo/global.json) - jeśli zaczynasz własny
projekt TUnit od zera, dodaj go od razu, żeby nie trafić na ten sam błąd.

### Dlaczego to ważne w praktyce

Dla typowego projektu webowego ta różnica (source generators vs refleksja) dziś jeszcze
nie "boli" - kilkaset testów startuje szybko w obu podejściach. Zaczyna mieć znaczenie w
dwóch miejscach: **duże monorepo z tysiącami testów** (gdzie czas odkrywania testów
realnie sumuje się w CI) oraz **projekty celujące w Native AOT** (mikroserwisy z bardzo
krótkim czasem startu, aplikacje na urządzenia z ograniczonymi zasobami) - tam refleksja
w testach bywa źródłem błędów trudnych do zdiagnozowania podczas trimmingu. TUnit daje
ten sam, znajomy sposób pisania testów, ale bez tego kompromisu na przyszłość.

**Pełny, uruchamialny przykład:** [`code/TunitDemo/`](code/TunitDemo/).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — dokładne komendy + prawdziwy output
`dotnet test`.

---

<div align="center">

[← wróć do wydania #1 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
