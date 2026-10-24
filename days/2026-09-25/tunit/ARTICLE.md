<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #2 — 25 września 2026

![TUnit](https://img.shields.io/badge/TUnit-2EA44F?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-D73A49?style=for-the-badge)

## TUnit: dane, hooki i równoległość — sterowanie tym, co testy robią naraz

</div>

---

> _"Testy w TUnit domyślnie biegną równolegle. To świetna wiadomość — dopóki dwa z nich
> nie sięgną po ten sam plik, tę samą tabelę albo ten sam port."_

Wczoraj: pierwszy test i generatory źródeł. Dziś trzy rzeczy, które odróżniają
"zestaw testów na próbę" od zestawu, z którym da się żyć w CI: **testy sterowane danymi**,
**hooki cyklu życia** i **kontrola równoległości**. Wszystko sprawdzone lokalnie na
`.NET SDK 10.0.400` i `TUnit 1.69.0` — kod w [`code/`](code/) buduje się, a
**36 testów przechodzi** (prawdziwy output niżej).

| 🧩 Temat | 🏷️ Atrybuty | 💡 W jednym zdaniu |
|---|---|---|
| Dane | `[Arguments]`, `[MethodDataSource]`, `[MatrixDataSource]`+`[Matrix]` | jedna metoda, wiele przypadków |
| Hooki | `[Before]`/`[After]` z `Test`, `Class`, `Assembly` | setup/teardown na właściwym poziomie |
| Równoległość | `[NotInParallel]`, `[DependsOn]`, `[ParallelLimiter<T>]` | zakaz, kolejność, limit |

---

## 1. 📊 Data-driven: jedna metoda, wiele przypadków

Testowany kod to celowo prosta funkcja rabatu z zaokrągleniem do groszy
(`PriceCalculator.ApplyDiscount`). Prosta, bo bohaterem są atrybuty.

**`[Arguments]`** — dane inline, każdy atrybut to osobny test w raporcie:

```csharp
[Test]
[Arguments(100.00, 10, 90.00)]
[Arguments(19.99, 0, 19.99)]
[Arguments(10.05, 50, 5.03, DisplayName = "polowa z zaokragleniem 5.025 -> 5.03")]
public async Task ApplyDiscount_Arguments(double price, int percent, double expected) { ... }
```

Uwaga praktyczna: atrybuty w C# nie przyjmują `decimal`, więc kwoty podajemy jako
`double` i rzutujemy — stąd wygodniej dla pieniędzy sięgnąć po źródło metodowe.
`DisplayName` zastępuje domyślną nazwę `Metoda(arg1, arg2)` w raporcie (widać to w
outpucie: `passed polowa z zaokragleniem 5.025 -> 5.03`).

**`[MethodDataSource]`** — dane z metody statycznej, więc mogą być obliczane, `decimal`,
złożone:

```csharp
public static IEnumerable<Func<(decimal Price, int Percent, decimal Expected)>> DiscountCases()
{
    yield return () => (200m, 25, 150m);
    yield return () => (0.99m, 50, 0.50m);
    yield return () => (1234.56m, 15, 1049.38m);
}

[Test]
[MethodDataSource(nameof(DiscountCases))]
public async Task ApplyDiscount_MethodDataSource(decimal price, int percent, decimal expected) { ... }
```

Zwracamy `Func<...>`, a nie gotowe krotki — dzięki temu każdy test dostaje **świeży**
obiekt. Dla krotek liczb nie ma to znaczenia, ale gdy dane to mutowalne obiekty, dzielenie
jednej instancji między przypadki to klasyczne źródło testów, które przechodzą pojedynczo,
a padają razem. (Rekomendacja `Func<T>` pochodzi z dokumentacji TUnit; tu zweryfikowałem
tylko, że wariant z krotką kompiluje się i działa.)

**`[MatrixDataSource]` + `[Matrix]`** — iloczyn kartezjański wartości parametrów.
`[Matrix(10.0, 99.99)]` × `[Matrix(0, 50, 100)]` = **6 testów** z jednej metody, a
niezmiennik "rabat nigdy nie podnosi ceny" sprawdzamy na całej siatce. W outpucie widać
wszystkie sześć kombinacji, np. `NigdyNieWiekszaNizCena(99.99, 50)`.

> 🎯 **Dlaczego to ważne:** w TUnit każdy przypadek danych to **osobny, niezależnie
> uruchamiany test** (widoczny osobno w raporcie, ze swoim czasem i wynikiem) — a co za
> tym idzie, także niezależnie równoległy. Jeden zły wiersz nie chowa reszty.

---

## 2. 🪝 Hooki: setup i teardown na trzech piętrach

`[Before(Zakres)]` / `[After(Zakres)]`, gdzie zakres to `Test`, `Class` albo `Assembly`.
Zasada: **Test** = metoda instancyjna, **Class** i **Assembly** = metoda `static`.
Poniżej dziennik zdarzeń z prawdziwego przebiegu (klasa z dwoma testami):

```
[Before Assembly] start przebiegu
[Before Class]    HookTests
[Before Test]     Drugi
    ...cialo testu Drugi
[Before Test]     Pierwszy
    ...cialo testu Pierwszy
[After  Test]     Drugi
[After  Test]     Pierwszy
[After  Class]    HookTests
...
[After  Assembly] koniec przebiegu
```

Dwie rzeczy, które ten log zdradza (i które łatwo przeoczyć):

1. **Kolejność testów w klasie nie jest kolejnością w pliku.** `Drugi` wystartował przed
   `Pierwszy`, a ich hooki się przeplatają (`Before Test Pierwszy` wszedł, zanim
   `After Test Drugi` się wykonał). Testy z jednej klasy też biegną równolegle —
   **nie zakładaj kolejności i nie trzymaj stanu w polach `static` bez potrzeby**.
2. **Hooki `Test` dostają `TestContext`** — stąd w logu nazwa testu
   (`context.Metadata.TestName`). To wygodny punkt zaczepienia do logowania czy
   diagnostyki.

Dwa drobiazgi z kompilatora: analizator **TUnit0042** ostrzega, gdy hooki globalne
(`Assembly`) mieszkają w klasie z testami — dlatego w kodzie siedzą w osobnej
`GlobalHooks`. Instancja klasy testowej powstaje **per test**, więc pola instancyjne
(`_instanceId`) są bezpiecznie izolowane — jak w xUnit.

> 🎯 **Dlaczego to ważne:** dobór zakresu to decyzja o koszcie. Uruchomienie kontenera z
> bazą w `[Before(Test)]` to minuty w dużym zestawie; w `[Before(Assembly)]` — raz. Ale
> wspólny stan wymaga wtedy izolacji danych między testami (a tu wracamy do równoległości).

---

## 3. ⚡ Równoległość: zakaz, kolejność, limit

Domyślnie TUnit odpala testy równolegle. Zamiast opowiadać, **zmierzyłem szczytową
liczbę jednocześnie działających testów** (licznik `Gauge` z `Interlocked`; każdy test
"pracuje" 200–300 ms). Wyniki z prawdziwego przebiegu:

| 🔬 Scenariusz | 🏷️ Atrybut | 📈 Zmierzony szczyt jednoczesności |
|---|---|---|
| A. Domyślnie (6 testów) | — | **6** |
| B. Wspólny klucz, 2 klasy × 2 testy | `[NotInParallel("shared-resource")]` | **1** |
| C. Kolejność 3 kroków | `[DependsOn]` | `Krok1_Utworz -> Krok2_Odczytaj -> Krok3_Usun` |
| D. Limit dla klasy (6 testów) | `[ParallelLimiter<MaxTwoLimit>]` | **2** |

**`[NotInParallel("klucz")]`** — testy o tym samym kluczu nigdy nie nakładają się w
czasie, *nawet między różnymi klasami* (w demie: `UseA`/`UseB` w jednej klasie,
`UseC`/`UseD` w drugiej — szczyt 1). Testy bez tego klucza dalej biegną równolegle
obok. To narzędzie na współdzielony zasób: plik, wiersz w bazie, port.

**`[DependsOn(nameof(Inny))]`** — test startuje dopiero po zakończeniu wskazanego.
Krok 1 śpi 300 ms, a krok 2 i tak czeka. Zwróć uwagę na etykę: zależności między
testami to **zapach** (testy powinny być niezależne). Sensowne w scenariuszach
"utwórz → odczytaj → usuń" na drogim zasobie, gdzie rozbicie na niezależne testy
kosztowałoby więcej niż zależność.

**`[ParallelLimiter<T>]`** — `T` implementuje `IParallelLimit` (`int Limit`), a atrybut
ogranicza równoległość *co najwyżej do N* zamiast do 1:

```csharp
public class MaxTwoLimit : IParallelLimit
{
    public int Limit => 2;
}

[ParallelLimiter<MaxTwoLimit>]
public class LimitedParallelTests { ... }   // 6 testów, zmierzony szczyt: 2
```

Interfejs mieszka w przestrzeni `TUnit.Core.Interfaces` (bez `using` kompilator zgłasza
`CS0246` — na to trafiłem). Idealne, gdy zasób znosi kilka jednoczesnych klientów
(pula połączeń, rate limit zewnętrznego API), ale nie 50.

> 🎯 **Dlaczego to ważne:** flaky testy w CI to najczęściej **ukryty wspólny stan
> zderzony z równoległością**, a nie "pechowy timing". Trzy narzędzia = trzy poziomy
> odpowiedzi: *nie naraz* (`NotInParallel`), *po sobie* (`DependsOn`), *nie za wielu*
> (`ParallelLimiter`). Lepiej zdecydować świadomie, niż wyłączać równoległość globalnie.

---

## ✅ Co zweryfikowano, a co nie

- ✔️ `dotnet test`: **36/36 przeszło** (TUnit 1.69.0, .NET SDK 10.0.400), zmierzone
  szczyty równoległości i kolejność hooków pochodzą z tego przebiegu.
- ⚠️ Console z testów widać w podsumowaniu dopiero z flagą `--output Detailed`
  (domyślnie output pomijany dla przechodzących testów).
- ⚠️ Nie testowałem: `[ParallelLimiter]` na poziomie pojedynczego testu / globalnie,
  `[DependsOn]` przy porażce zależności (zachowanie: nie sprawdzone), `[ClassDataSource]`,
  hooków `[BeforeEvery]`/`[AfterEvery]`. Nie opisuję ich, bo nie mam dowodu.
- ⚠️ `global.json` z wczoraj nadal obowiązkowy na .NET 10 SDK. Uwaga: SDK szuka go od
  **bieżącego katalogu roboczego**, nie od ścieżki projektu — uruchamiaj `dotnet test`
  z folderu projektu.

**Pełny, uruchamialny przykład:** [`code/TunitAdvanced/`](code/TunitAdvanced/).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — komendy + prawdziwy output `dotnet test`.

---

<div align="center">

[← wróć do wydania #2 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
