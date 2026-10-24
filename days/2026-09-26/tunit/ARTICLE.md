<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #3 — 26 września 2026

![TUnit](https://img.shields.io/badge/TUnit-2EA44F?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-D73A49?style=for-the-badge)

## TUnit: współdzielone fixture'y, retry, timeout i hook globalny

</div>

---

> _"Najdroższa linijka w zestawie testów to `await container.StartAsync()`. Pytanie
> nie brzmi, czy ją napisać, tylko ile razy będzie wykonana."_

Wczoraj: dane, hooki i równoległość. Dziś temat, który rozstrzyga o czasie CI:
**kto tworzy drogi zasób, ile razy i kto go sprząta**. Do tego dwa pasy bezpieczeństwa
(`[Retry]`, `[Timeout]`) i jeden hook, który łapie każdy test w zestawie. Sprawdzone na
`.NET SDK 10.0.400` i `TUnit 1.69.0` — **18 testów przechodzi** (prawdziwy output w
[`code/README.md`](code/README.md)).

| 🧩 Temat | 🏷️ API | 💡 W jednym zdaniu |
|---|---|---|
| Fixture'y | `[ClassDataSource<T>]`, `SharedType` | zasób wstrzykiwany, z wybranym zasięgiem życia |
| Cykl życia | `IAsyncInitializer`, `IAsyncDisposable` | asynchroniczny start i sprzątanie zasobu |
| Odporność | `[Retry(n)]`, `[Timeout(ms)]` | powtórz niestabilny, przerwij zawieszony |
| Hook globalny | `[BeforeEvery(Test)]`, `[After(TestSession)]` | kod dla każdego testu / raz na koniec |

---

## 1. 🏭 `[ClassDataSource<T>]`: fixture z zasięgiem życia

Fixture to zwykła klasa. Jeśli implementuje `IAsyncInitializer` (`Task InitializeAsync()`),
TUnit **czeka** na jej asynchroniczną inicjalizację przed testem; jeśli `IAsyncDisposable`,
zwolni ją sam. Nasza `FakeDatabase` udaje bazę, która startuje 200 ms, i liczy, ile
instancji powstało i ile zwolniono:

```csharp
public class FakeDatabase : IAsyncInitializer, IAsyncDisposable
{
    public async Task InitializeAsync() { await Task.Delay(200); IsReady = true; ... }
    public ValueTask DisposeAsync() { ... }
}
```

Zasięg wybiera `Shared`. Fixture trafia do konstruktora (atrybut na **klasie**) albo do
parametru metody (atrybut na **metodzie**):

```csharp
[ClassDataSource<FakeDatabase>(Shared = SharedType.PerTestSession)]
public class SessionA(FakeDatabase db) { ... }

[ClassDataSource<FakeDatabase>(Shared = SharedType.Keyed, Key = "tenant-1")]
public class KeyedA(FakeDatabase db) { ... }
```

Zmierzyłem, ile instancji powstaje w 4 scenariuszach (12 testów korzystających z
fixture'a; identyfikatory z prawdziwego przebiegu):

| 🔬 `SharedType` | 📦 Znaczenie | 🧾 Zmierzone id instancji |
|---|---|---|
| `PerTestSession` | jedna na cały przebieg, także między klasami | klasy `SessionA` i `SessionB`: **jedno** id (2) |
| `PerClass` | jedna na klasę | `PerClassA` → 3, `PerClassB` → 4 |
| `Keyed` | jedna na klucz, także między klasami | `tenant-1` (2 klasy) → 1, `tenant-2` → 5 |
| `None` | nowa na każdy test | dwa testy → 6 i 7 |

Razem **7 utworzonych, 7 zwolnionych** — TUnit sprząta każdą instancję sam. Dziennik z
przebiegu pokazuje też *kiedy*: instancje `PerClass` i `Keyed` są zwalniane w trakcie
przebiegu (po zakończeniu swoich konsumentów), a instancja `PerTestSession` (#2) —
jako **ostatnia**, na samym końcu.

> 🎯 **Dlaczego to ważne:** `PerTestSession` zamienia N × 200 ms w 1 × 200 ms — ale za
> cenę wspólnego stanu widocznego dla testów biegnących równolegle (wczorajszy temat!).
> `Keyed` to złoty środek: np. izolacja per „tenant” lub per schemat bazy, gdzie jeden
> zasób obsługuje grupę testów, a inna grupa dostaje własny. Dobór zasięgu to decyzja
> o kosztach **i** o izolacji jednocześnie.

Jedna pułapka z kompilatora: `[ClassDataSource]` na **parametrze** konstruktora lub
metody kończy się błędami `TUnit0038` i `TUnit0070` (analizator żąda
`[CombinedDataSources]`). Atrybut na klasie lub metodzie działa bez tego — tak jest w kodzie.

---

## 2. 🛟 `[Retry]` i `[Timeout]`: pasy bezpieczeństwa

**`[Retry(3)]`** powtarza test po porażce, do 3 razy. Uwaga: **każda próba to nowa
instancja klasy testowej**, więc licznik prób musi być `static` (jak w kodzie). Log z
przebiegu: test zawodzi do trzeciej próby i wtedy przechodzi:

```
[Retry] proba nr 1, CurrentRetryAttempt=0
[Retry] proba nr 2, CurrentRetryAttempt=1
[Retry] proba nr 3, CurrentRetryAttempt=2
```

Numer próby daje `TestContext.Current!.Execution.CurrentRetryAttempt` (indeksowany od 0).

**`[Timeout(ms)]`** przerywa test po limicie i — jeśli metoda przyjmuje
`CancellationToken` — anuluje ten token, żeby kod mógł się zwinąć. Zmierzony efekt, gdy
zmieniłem limit na 300 ms, a test czeka 5 s:

```
failed Timeout_TestMiesciSieWLimicie (322ms)
  [Test Failure] TimeoutException: Test 'Timeout_TestMiesciSieWLimicie' timed out after 00:00:00.3000000
--- Task Status: Canceled ---
```

Test padł po ~322 ms, nie po 5 s; do komunikatu TUnit dokłada stos wątku obsługi
timeoutu (dla zawieszonego kodu to cenne diagnostycznie). W repo test ma bezpieczne
`[Timeout(2_000)]`, żeby całość przechodziła.

> 🎯 **Dlaczego to ważne:** `[Timeout]` chroni pipeline przed jednym zawieszonym testem,
> który blokuje cały job do limitu CI. `[Retry]` jest natomiast **plasterem**, nie
> lekarstwem: maskuje niestabilność. Używaj świadomie (zewnętrzne API, sieć) i nie
> traktuj „zielone po retry” jako „naprawione”.

---

## 3. 🌐 Hook globalny: `[BeforeEvery]` i `[After(TestSession)]`

`[BeforeEvery(Test)]` to metoda `static`, którą TUnit woła przed **każdym** testem w
całym zestawie — bez wpisywania jej w każdą klasę (odpowiednik globalnego setupu). Nasza
zapisuje `context.Metadata.TestName`. Wynik: hook zobaczył **20 uruchomień** przy 18
testach — bo `[Retry]` uruchomił jeden test trzy razy (18 − 1 + 3 = 20). Czyli hook
liczy **próby**, nie testy.

`[After(TestSession)]` woła się raz na końcu; użyłem go do raportu zbiorczego. Zaskoczenie:
`Console.WriteLine` z tego hooka **nie pojawia się** w wyniku `dotnet test` (nawet z
`--output Detailed`), więc raport zapisuję do pliku w katalogu tymczasowym.

---

## ✅ Co zweryfikowano, a co nie

- ✔️ `dotnet test`: **18/18 przeszło** (TUnit 1.69.0, .NET SDK 10.0.400), liczby instancji,
  id fixture'ów, kolejność zwalniania i liczba wywołań `[BeforeEvery]` pochodzą z tego przebiegu.
- ✔️ Porażka `[Timeout]` — zaobserwowana w osobnym, tymczasowym przebiegu (1 test padł, 17
  przeszło); kod w repo ma bezpieczny limit.
- ⚠️ Nie testowałem: `[AfterEvery]`, `[BeforeEvery(Class/Assembly)]`, własnych asercji
  (`Assertion<T>`), `[Retry]` z warunkiem/`RetryOn`, ani `[ClassDataSource]` z wieloma typami naraz.
  Nie opisuję ich, bo nie mam dowodu.
- ⚠️ Kolejność zwalniania fixture'ów i przydział numerów id zależą od równoległości —
  konkretne numery mogą się różnić między uruchomieniami; niezmiennik (ile unikalnych id)
  jest weryfikowany asercjami.
- ⚠️ `global.json` nadal obowiązkowy na .NET 10 SDK, a SDK szuka go od **bieżącego
  katalogu roboczego** (uruchamiaj z folderu projektu).

**Pełny, uruchamialny przykład:** [`code/TunitFixtures/`](code/TunitFixtures/).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — komendy + prawdziwy output `dotnet test`.

---

<div align="center">

[← wróć do wydania #3 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
