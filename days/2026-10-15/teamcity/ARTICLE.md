<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #22 — 15 października 2026

![TeamCity](https://img.shields.io/badge/TeamCity-000000?style=for-the-badge&logo=teamcity&logoColor=white)
![Artifact deps](https://img.shields.io/badge/zale%C5%BCno%C5%9Bci-artefaktowe-blue?style=for-the-badge)
![Haczyk](https://img.shields.io/badge/haczyk-nieaktualny%20artefakt-red?style=for-the-badge)

## TeamCity: zielone testy na artefakcie z builda, który nie jest Twój — snapshot to nie artefakt

</div>

---

> _"Snapshot mówi: Compile #5. Test mówi: wszystko OK. A plik, który przetestował, pochodzi z Compile #3."_
> Tak wyszło z pomiaru na żywym serwerze. Poniżej: jak do tego dochodzi i jedna linijka, która to blokuje.

W #15 połączyliśmy buildy w łańcuch zależnościami **snapshot** (kolejność, wspólna rewizja, reakcja na pad).
Snapshot **nie przenosi plików**. Do tego służą zależności **artefaktowe** (`artifacts(...)`), i tu jest
pułapka: obie zależności mają osobne reguły wyboru builda i potrafią wskazać dwa różne buildy.
Serwer `jetbrains/teamcity-server:2025.07` w Dockerze, jeden agent `jetbrains/teamcity-agent:2025.07`,
konfiguracja z repo przez versioned settings. Kod: [`code/`](code/), instrukcja: [`code/README.md`](code/README.md).

**Dlaczego to ważne dla .NET deva?** Klasyczny pipeline: `dotnet publish` w jednym buildzie, a `dotnet test` /
skan / deploy w następnym, na **tych samych binarkach**. Jeśli etap testowy pobierze paczkę z innego builda niż
ten, którego rewizję zatwierdził łańcuch, to testujesz coś innego niż wydajesz, a pipeline jest zielony.

---

### 1. Dwie zależności, dwa pytania

```kotlin
object Test : BuildType({
    id("Test")
    dependencies {
        snapshot(Compile) { onDependencyFailure = FailureAction.FAIL_TO_START }
        artifacts(Compile) {
            buildRule = sameChainOrLastFinished()
            artifactRules = "build-out/** => in"
        }
    }
    ...
})
```

| Zależność | Odpowiada na pytanie | Opcje |
|---|---|---|
| `snapshot(Compile)` | **po którym** buildzie i na której rewizji mam biec? | `reuseBuilds`, `onDependencyFailure` |
| `artifacts(Compile)` | **z którego** builda wziąć pliki i które? | `buildRule`, `artifactRules` |

`Compile` publikuje `out/**` jako `build-out/**` (`artifactRules = "out/** => build-out"`), a `Test` odbiera to do
katalogu `in/` (lewa strona `=>` to ścieżka w artefaktach źródła, prawa to katalog u odbiorcy).
Kompilator DSL wygenerował z tego (fragment XML z realnego `BUILD SUCCESS`, plik
[`generated-sample-Test.xml`](code/generated-sample-Test.xml)):

```xml
<revisionRule name="sameChainOrLastFinished" revision="latest.sameChainOrLastFinished" />
<artifact sourcePath="build-out/** =&gt; in" />
```

---

### 2. Pomiar: ten sam łańcuch, dwa `buildRule`

Skrypt kroku wypisuje do statusu builda numer zależności snapshot i **treść pliku z artefaktu**
(`##teamcity[buildStatus ...]`, żeby było widać w REST bez pobierania logu). `Test` używa
`sameChainOrLastFinished()`, `TestLast` używa `lastSuccessful()`. Oba mają `snapshot(Compile)`.

Najpierw kolejka z **przypiętym** snapshotem na `Compile #1` (REST: `<snapshot-dependencies><build id="1"/>`),
mimo że istnieje już `Compile #2`:

```
7  Test      #3 SUCCESS | Test #3, snapshot Compile #1, artefakt: compiled by Compile #1 (build id 1)
9  TestLast  #1 SUCCESS | TestLast #1, snapshot Compile #1, artefakt: compiled by Compile #2 (build id 5)
```

- `Test`: snapshot `#1`, artefakt z `#1`. Spójnie.
- `TestLast`: snapshot `#1`, artefakt z `#2`. **Rozjazd.** `lastSuccessful` nie patrzy na łańcuch, tylko bierze
  najnowszy udany `Compile`.

Zależność snapshot wcale nie ustawia wersji artefaktu. Przy zwykłym uruchomieniu zwykle nie widać różnicy,
bo łańcuch bierze najnowszy build. Rozjazd wychodzi przy buildach przypiętych (rebuild, promocja, kolejka
z kilku gałęzi), czyli wtedy, gdy ma znaczenie.

---

### 3. Haczyk numer dwa: pad kompilacji, a testy zielone na starym pliku

Na agencie położyłem `/tmp/fail-compile` (krok `Compile` zaczyna się od `set -e`, potem `test ! -f ...`) i
uruchomiłem `TestLast` oraz `Test` bez przypinania:

```
16 Compile   #5   FAILURE | Exit code 1 (Step: Compile (Command Line))
17 TestLast  #3   FAILURE | TestLast #3, snapshot Compile #5, artefakt: compiled by Compile #3 (build id 14)
18 Compile   #6   FAILURE | Exit code 1 (Step: Compile (Command Line))
19 Test      #N/A FAILURE | Snapshot dependency failed: ... Compile
```

- `TestLast` (zwykły `snapshot(Compile) { }`): **krok się wykonał** (4 s na agencie) i przeczytał artefakt
  z `Compile #3`, czyli ostatniego udanego buildu, nie z tego łańcucha. Status końcowy to FAILURE, bo serwer dopisuje problem, ale testy
  przebiegły na starych plikach. Gdyby Twój krok nie sprawdzał kodu wyjścia zależności, wynik byłby zielony.
- `Test` (`FAIL_TO_START`): build `#N/A`, krok się nie wykonał.

Zwykły `snapshot(X) { }` ma domyślnie `run-build-if-dependency-failed = RUN_ADD_PROBLEM` — to potwierdza
**dwukrotnie**: wygenerowany XML kompilacji i REST z żywego serwera
(`GET /app/rest/buildTypes/id:ArtDemo_TestLast/snapshot-dependencies`). To zamyka otwarte pytanie z #15
("czy zwykły `snapshot` ma ten sam default"). Tak, ma.

Rada: dla etapu, który zużywa artefakty, ustaw jawnie `FAIL_TO_START` **i** `sameChainOrLastFinished()`
(albo `buildNumber`/`tag` dla świadomej promocji). `lastSuccessful()` zostaw dla narzędzi, którym wystarczy
"najnowsza paczka z gałęzi".

---

### 4. Dwie pułapki po drodze (kosztowały mnie po jednym przebiegu)

| Pułapka | Co się stało |
|---|---|
| Wieloliniowy skrypt kroku bez `set -e` | `test ! -f /tmp/fail-compile` zwrócił 1, ale skrypt szedł dalej i kończył się `cat` (exit 0). `Compile` był zielony mimo pliku-blokady. Dopiero `set -e` dał FAILURE |
| `PUT .../authorized` z ciałem `true\n` (z newline) | Serwer odpowiedział `200 false` i agent został nieautoryzowany. Z ciałem `true` bez newline: `200 true` |

Trzecia, mała: parametr zależności ma nazwę zbudowaną z **pełnego id** build type'u, więc
`%dep.Compile.build.number%` jest puste, a poprawne jest `%dep.ArtDemo_Compile.build.number%` (id ma prefiks
projektu). Ten błąd wyłapałem czytając wygenerowany XML.

---

### Podsumowanie

| Fakt | Zmierzone |
|---|---|
| `snapshot` i `artifacts` wybierają builda niezależnie | tak: snapshot `#1`, artefakt z `#2` (`lastSuccessful`) |
| `sameChainOrLastFinished` trzyma się łańcucha | tak: artefakt z buildu `#1` przy przypiętym snapshocie |
| Zwykły `snapshot { }` przy padzie | krok się wykonał, `RUN_ADD_PROBLEM`, artefakt ze starego builda |
| `FAIL_TO_START` | `#N/A`, krok się nie wykonał |
| Kompilacja `settings.kts` | `mvn compile` → `BUILD SUCCESS` na wersji v1; końcowa wersja wczytana przez serwer z repo |

---

### Czego NIE sprawdziłem

| Temat | Powód |
|---|---|
| `mvn compile` na **końcowej** wersji `settings.kts` | kompilowałem v1; po niej doszły tylko komunikat statusu, `set -e` i poprawka nazwy parametru, a serwer wczytał końcową wersję z repo (pokazały to REST `steps` i udane buildy) |
| Dwa agenty (artefakt między różnymi maszynami) | jeden agent; transport przez serwer jest tak czy tak, ale rozdziału maszyn nie mierzyłem |
| Zachowanie, gdy artefakt nie istnieje (zła `artifactRules`) | nie testowałem |
| `buildNumber(...)`, `tag(...)`, `cleanDestination = true`, `runOnSameAgent` | tylko `sameChainOrLastFinished` i `lastSuccessful` |
| Zależność artefaktowa **bez** snapshot | nie testowałem |
| Prawdziwy VCS w łańcuchu | buildy bez VCS roota, tylko repo ustawień |
| Podkomenda `gett` (log builda) | odrzucona przez sesję; status czytałem przez `buildStatus` |
| Pełny przebieg od zera na finalnych plikach | sesja szła przyrostowo (3 wersje `settings.kts`) |

---

### 📎 Jak uruchomić kod z tego wydania

[`code/README.md`](code/README.md): komendy w kolejności i surowe odpowiedzi serwera. Sprzątanie: kontenery
`tc-p22`, `tc-p22-agent` usunięte z `-v`, obraz agenta (pobrany przeze mnie) usunięty, katalog roboczy z hasłem usunięty.

---

<div align="center">

[← wróć do wydania #22 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
