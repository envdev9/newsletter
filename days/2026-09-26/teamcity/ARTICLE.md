<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #3 — 26 września 2026

![TeamCity](https://img.shields.io/badge/TeamCity-000000?style=for-the-badge&logo=teamcity&logoColor=white)

## Pipeline .NET w TeamCity: szablony, parametry i łańcuch zależności

</div>

---

> _"Trzy build configurations, które kopiują sobie te same pięć ustawień, to trzy
> miejsca do poprawienia, gdy zmieni się jedno. Szablon, parametry i zależności
> sprawiają, że pipeline build → test → pack ma jedno źródło prawdy."_

W wydaniu #1 powstał pojedynczy build z jednym krokiem `echo`. Dziś składamy z tego
prawdziwy pipeline dla .NET z trzech etapów (**Build → Test → Pack i publish**) i
uczymy się trzech mechanizmów, które robią z TeamCity coś więcej niż zdalne
odpalanie `dotnet build`: **szablonów**, **parametrów** i **zależności między
buildami**. Kod: [`code/.teamcity/settings.kts`](code/.teamcity/settings.kts),
instrukcja i uczciwy stan weryfikacji: [`code/README.md`](code/README.md).

> **Ważne z góry:** tym razem *nie* udało się zweryfikować kompilacji tego pliku.
> Próba pobrania przenośnego JDK 21 i Maven do `/tmp` (żeby ominąć ścianę z wydania
> #1) została odrzucona przez środowisko - opis w sekcji na końcu. Kod jest
> napisany według dokumentacji Kotlin DSL, ale **nie był kompilowany**.

---

### 1. Szablon (template): wspólny szkielet zamiast copy-paste

**Dlaczego to ważne:** w .NET znasz to z `Directory.Build.props` - wspólne ustawienia
w jednym miejscu, projekty je dziedziczą. Szablon TeamCity to to samo dla build
configurations.

Szablon (`Template`) wygląda jak build configuration, ale **nie da się go uruchomić**.
To wyłącznie wzorzec: VCS root, parametry, wymagania wobec agenta, kroki, triggery.
Konkretna build configuration deklaruje `templates(DotnetStage)` i dziedziczy całość.

```kotlin
object DotnetStage : Template({
    name = "Etap .NET (szablon)"
    vcs { root(PrasowkaVcs) }
    params { /* patrz niżej */ }
    requirements { contains("teamcity.agent.jvm.os.name", "Linux") }
})

object Build : BuildType({
    templates(DotnetStage)
    name = "1. Build"
    // ...tylko to, czym Build różni się od reszty
})
```

Dwie reguły, o które potyka się każdy początkujący:

- Szablon trzeba **zarejestrować w projekcie**: `template(DotnetStage)` obok
  `buildType(...)`. Sama deklaracja `object` nie wystarczy.
- **Override**: build configuration może nadpisać to, co dziedziczy. U nas `Test`
  redeklaruje `param("configuration", "Debug")` - wartość z szablonu (`Release`)
  przestaje tam obowiązywać, w `Build` i `Pack` zostaje. Wartość z potomka zawsze
  wygrywa nad wartością z szablonu.

---

### 2. Parametry: trzy rodzaje i jeden sekret

**Dlaczego to ważne:** parametry są klejem całej konfiguracji - numer wersji, ścieżki,
klucz do NuGet. Ich zły dobór kończy się kluczem API w logu builda.

W TeamCity parametr to para nazwa-wartość, a **prefiks nazwy** decyduje, gdzie
parametr trafi:

| Prefiks | Rodzaj | Gdzie widoczny |
|---|---|---|
| (brak), np. `configuration` | konfiguracyjny | tylko w konfiguracji builda, do użycia jako `%configuration%` |
| `env.`, np. `env.DOTNET_NOLOGO` | środowiskowy | zmienna środowiskowa procesu kroku - `dotnet` CLI ją zobaczy |
| `system.`, np. `system.artifacts.dir` | systemowy | właściwość builda przekazywana do runnerów i skryptów |

Do wartości odwołujemy się w skryptach i polach przez `%nazwa%`, np.
`dotnet build -c %configuration%`. Zasięg jest hierarchiczny: parametr zadeklarowany
w projekcie (`version.prefix = 1.0`) widzą wszystkie build configurations i szablony
pod nim; szablon przekazuje swoje potomkom; potomek może nadpisać.
Literalny znak procenta zapisuje się jako `%%`.

Najważniejszy jest typ `password`:

```kotlin
password(
    "env.NUGET_API_KEY",
    "credentialsJSON:00000000-0000-0000-0000-000000000000",  // fikcyjny UUID
    label = "Klucz API NuGet",
    display = ParameterDisplay.HIDDEN
)
```

Wartość takiego parametru jest maskowana w logach i w UI, a - co kluczowe dla repo -
**w `settings.kts` nie ma samego sekretu**, tylko odwołanie `credentialsJSON:<uuid>`
do wartości zapisanej (zaszyfrowanej) na serwerze. Plik możesz bezpiecznie
commitować. Ten UUID w naszym przykładzie jest oczywiście fikcyjny; prawdziwy
dostajesz, gdy w UI dodasz sekret do projektu.

---

### 3. Zależności: snapshot vs artifact - dwie różne rzeczy

**Dlaczego to ważne:** to najczęściej mylona para pojęć w TeamCity, a od jej
zrozumienia zależy, czy testujesz dokładnie ten kod i dokładnie te binaria, które
potem trafiają do NuGet.

- **Snapshot dependency** dotyczy **kolejności i spójności rewizji**. Mówi: "ten
  build ma sens tylko na tej samej wersji kodu, co tamten, i ma się wykonać po nim".
  Nie przenosi żadnych plików. TeamCity zbuduje z tego **łańcuch buildów** (build
  chain) i - jeśli istnieje już build na tej rewizji - może go użyć ponownie zamiast
  budować drugi raz.
- **Artifact dependency** dotyczy **plików**: ściąga artefakty innego builda na
  agenta bieżącego. Nie wymusza sama z siebie kolejności - dlatego w praktyce
  występuje w parze ze snapshotem.

```kotlin
object Test : BuildType({
    templates(DotnetStage)
    dependencies {
        snapshot(Build) {
            onDependencyFailure = FailureAction.FAIL_TO_START
        }
        artifacts(Build) {
            buildRule = sameChainOrLastFinished()
            artifactRules = "build/** => %system.artifacts.dir%/build"
        }
    }
})
```

- `onDependencyFailure = FAIL_TO_START` - jeśli Build padł, Test w ogóle nie startuje
  (zamiast startować i psuć statystyki).
- `sameChainOrLastFinished()` - "weź artefakty z buildu **z tego samego łańcucha**;
  gdy uruchomiono mnie ręcznie, poza łańcuchem, weź ostatni zakończony". To zabezpiecza
  przed testowaniem binariów z innej rewizji niż kod.

**Artifact rules** to mały język z operatorem `=>`: po lewej co zebrać, po prawej
dokąd. Po stronie producenta (`Build`): `artifacts/build/** => build` - "cały
katalog `artifacts/build` zapisz w artefakcie pod nazwą `build/`". Po stronie
konsumenta (`Test`, `Pack`): `build/** => artifacts/build` - "rozpakuj to na agencie
do `artifacts/build`". Dwa razy `=>`, dwie strony tego samego kontraktu.

---

### 4. Cały łańcuch i trigger tylko na końcu

W pliku są trzy configurations: `Build`, `Test` (snapshot na Build) i `Pack`
(snapshot na Test, artefakty z Build). `Pack` robi `dotnet pack` i `dotnet nuget
push` z `%env.NUGET_API_KEY%`.

Ciekawy szczegół: **trigger VCS mamy wyłącznie w `Pack`**. Push uruchamia ostatnie
ogniwo, a snapshot dependencies same ściągają przed nim `Test` i `Build`. Jedno
miejsce konfiguracji zamiast trzech triggerów, które trzeba by synchronizować.

Numer wersji: `buildNumberPattern = "%version.prefix%.%build.counter%"` składa
numer z parametru projektu (`1.0`) i licznika builda, a `dotnet build -p:Version=%build.number%`
wpisuje go do assembly. Dzięki temu paczka NuGet niesie ten sam numer, który widzisz
na liście buildów.

Uwaga na nazwę: gdy potomek chce odczytać właściwość builda, od którego zależy, używa
składni `%dep.<id_build_configuration>.build.number%`. Id zależy od id projektu na
serwerze, więc w naszym pliku celowo tego nie używamy - nie umielibyśmy uczciwie
wskazać poprawnej wartości bez żywego serwera.

---

### Co zweryfikowaliśmy, a czego nie (uczciwie)

**Zweryfikowane:** nic w sensie kompilacji. Wykonaliśmy tylko sprawdzenie środowiska:
`mvn` nie jest zainstalowany (`which mvn` - brak), a `java` jest tu z wcześniejszych
wydań w wersji 17 (wtyczka Maven wymaga 21). Dysk ma teraz ok. 46 GB wolnego, więc
ograniczenie miejsca z wydania #1 nie obowiązuje.

**Niezweryfikowane, i dlaczego:** zgodnie z planem próbowaliśmy pobrać przenośną
binarkę JDK 21 (Temurin z `api.adoptium.net`) i Apache Maven do katalogu w `/tmp`.
Polecenie pobierania (`curl`) zostało **odrzucone przez środowisko** (tryb bez zgody
na takie polecenia). Nie obchodziliśmy tego ograniczenia innymi drogami. W efekcie:

- **nie** uruchomiliśmy `mvn compile` ani `teamcity-configs:generate`,
- **nie** mamy prawdziwego wygenerowanego XML-a - nie wklejamy żadnego, bo nie
  wolno zmyślać outputu,
- **nie** zweryfikowaliśmy retroaktywnie `settings.kts` z wydania #1,
- składnia pochodzi z dokumentacji Kotlin DSL i pamięci autora. Miejsca, w których
  ryzyko pomyłki jest największe: nazwy parametrów `password(...)` (`label`,
  `display`), `sameChainOrLastFinished()` oraz to, że kroki `script {}` i
  `requirements { contains(...) }` w naszej wersji DSL (`2026.3-dsl6`) mają dokładnie
  taki kształt. Nie zakładaj więc, że plik skompiluje się bez poprawek.

Jak sprawdzić samemu: JDK 21 w `JAVA_HOME`, potem `mvn compile` w katalogu
`.teamcity/` - szczegóły w [`code/README.md`](code/README.md). Ostrzeżenie z wydania
#1 dalej obowiązuje: dla konkretnych typów kroków (np. runnera `dotnet`) wtyczka
Maven bez żywego serwera może nie mieć potrzebnych zależności - dlatego w przykładzie
używamy generycznego kroku `script` z `dotnet` CLI, a nie dedykowanego runnera .NET.

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #3 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
