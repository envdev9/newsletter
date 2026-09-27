<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #4 — 27 września 2026

![TeamCity](https://img.shields.io/badge/TeamCity-000000?style=for-the-badge&logo=teamcity&logoColor=white)
![Kompilacja](https://img.shields.io/badge/kompilacja-niezweryfikowana-orange?style=for-the-badge)

## TeamCity: build features, failure conditions, Docker i composite build

</div>

---

> _"Zielony build to nie to samo co dobry build. Build, w którym po cichu zniknęło
> pół testów, też jest zielony - dopóki nie powiesz TeamCity, że ma się tego
> czepiać."_

W wydaniu #3 zbudowaliśmy łańcuch Build → Test → Pack. Dziś dokładamy warstwę, która
robi różnicę między "CI, które coś odpala" a "CI, któremu można ufać": **build
features**, **failure conditions**, **kroki w Dockerze**, **composite build** i
**versioned settings**. Kod: [`code/.teamcity/settings.kts`](code/.teamcity/settings.kts),
instrukcja: [`code/README.md`](code/README.md).

> ⚠️ **Uczciwie z góry:** w tej sesji nie miałem dostępu do powłoki (każde polecenie
> Bash zostało odrzucone), więc **nie sprawdziłem nawet, czy jest JDK 21 ani Maven**, i
> nie zrobiłem próby pobrania. Kod **nie był kompilowany**; składnia pochodzi z
> dokumentacji i pamięci. Elementy, których nie jestem pewien, są w kodzie oznaczone
> `[?]`, a w tekście symbolem ❓.

---

### 1. Build features: dodatki, które nie są krokami

**Dlaczego to ważne:** krok (`steps`) robi robotę - buduje, testuje. **Build feature**
zmienia *zachowanie wokół* builda: raportuje status, sprząta, mierzy. To odpowiednik
middleware w ASP.NET: nie wchodzi w logikę, ale opakowuje całe wykonanie.

| Feature | Co robi | W kodzie |
|---|---|---|
| 🟢 **Commit status publisher** | wysyła do GitHuba/GitLaba zielony/czerwony znaczek przy commicie | `Release` ❓ |
| 🧹 **Swabra** | sprząta pliki zostawione przez build; wykrywa pliki zablokowane przez proces | `Compile` |
| 📈 **Performance monitor** | wykresy CPU/RAM/dysku agenta w trakcie builda | `Compile` |
| 🔀 **Pull requests** | buduje gałęzie PR-ów (bez tego widzisz tylko główne gałęzie) | tylko opis ❓ |

```kotlin
features {
    swabra { forceCleanCheckout = true }
    perfmon { }
}
```

Commit status publisher wymaga tokenu - w repo trzymamy tylko odwołanie
`credentialsJSON:<uuid>` (jak w wydaniu #3), nigdy sam token. ❓ Dokładny kształt
zagnieżdżonego bloku `publisher = github { authType = personalToken { ... } }` jest z
pamięci - sprawdź w UI: skonfiguruj feature ręcznie, wybierz *Versioned Settings →
Show DSL*, i skopiuj to, co serwer sam wygenerował. To najlepsza droga na każdą
wątpliwość co do składni.

Funkcję *Pull requests* (buduje PR-y z GitHuba) celowo **nie ma w kodzie**: pola
filtrów (kto ma prawo wyzwalać build) znam zbyt słabo, żeby je wpisać bez
kompilatora.

---

### 2. Failure conditions: kiedy zielony ma być czerwony

**Dlaczego to ważne:** domyślnie build pada, gdy krok zwróci exit code ≠ 0. To za mało.

```kotlin
failureConditions {
    executionTimeoutMin = 20
    failOnMetricChange {
        metric = BuildFailureOnMetric.MetricType.TEST_COUNT
        threshold = 5
        comparison = BuildFailureOnMetric.MetricComparison.LESS
        compareTo = build { buildRule = lastSuccessful() }
        // + units ...
    }
    failOnText {
        conditionType = BuildFailureOnText.ConditionType.CONTAINS
        pattern = "warning NU1903"
        failureMessage = "Podatna paczka NuGet (NU1903)"
        reverse = false
    }
}
```

- ⏱️ **Timeout** - zawieszony test nie blokuje agenta w nieskończoność.
- 📉 **Metric change** - "liczba testów spadła o więcej niż 5 względem ostatniego
  udanego builda" łapie sytuację, gdy ktoś wyłączył połowę projektu testowego, a reszta
  jest zielona. Ten sam mechanizm działa dla pokrycia kodu czy rozmiaru artefaktu.
- 🔎 **Fail on text** - build pada, gdy w logu pojawi się wzorzec, nawet przy exit
  code 0. Tu: ostrzeżenie NuGet o podatnej paczce (`NU1903`) zamienia się w błąd.

❓ Nazwy pól `threshold`/`units`/`comparison`/`compareTo` oraz `reverse` to najmniej
pewne miejsca tego pliku.

---

### 3. Docker w krokach: agent bez .NET SDK

**Dlaczego to ważne:** klasyczny ból agentów: "u mnie działa na SDK 8, agent ma 9".
Uruchom krok w kontenerze i wersja SDK staje się częścią konfiguracji, nie agenta.

Są dwa różne mechanizmy - nie mylić:

1. **Docker wrapper** (opcje `dockerImage` na kroku `script`): skrypt wykonuje się
   *wewnątrz* kontenera z podanego obrazu. Agent potrzebuje tylko Dockera.
   ```kotlin
   script {
       scriptContent = "dotnet build -c Release"
       dockerImage = "mcr.microsoft.com/dotnet/sdk:9.0"
       dockerPull = true
   }
   ```
2. **Krok `dockerCommand`**: TeamCity *zarządza* Dockerem - `docker build`, `push`
   itd. Do budowania obrazów aplikacji z `Dockerfile` (u nas `DockerImage`).
   ```kotlin
   dockerCommand {
       commandType = build {
           source = file { path = "Dockerfile" }
           namesAndTags = "prasowka/app:%build.number%"
       }
   }
   ```

Pominąłem `dockerCompose` (krok uruchamiający stack z `docker-compose.yml`) i logowanie
do rejestru (feature `dockerSupport`): nie pamiętam ich pól na tyle, by pisać je bez
kompilatora. ❓ `dockerImagePlatform = ScriptBuildStep.ImagePlatform.Linux` też do
sprawdzenia - pole bywa niepotrzebne.

---

### 4. Composite build: jeden status dla całego łańcucha

**Dlaczego to ważne:** w łańcuchu z wydania #3 każdy build ma osobny status. Na commicie
w GitHubie chcesz **jeden** znaczek: "cały pipeline zielony".

**Composite build** (`type = BuildTypeSettings.Type.COMPOSITE`) nie ma kroków ani
własnego agenta. Zależy snapshotem od ostatniego ogniwa i agreguje wynik całości
- w UI rozwija się jak drzewo buildów. To na nim wisi trigger VCS i commit status
publisher: `Release` w naszym pliku.

```kotlin
object Release : BuildType({
    type = BuildTypeSettings.Type.COMPOSITE
    dependencies { snapshot(DockerImage) { onDependencyFailure = FailureAction.FAIL_TO_START } }
    triggers { vcs { } }
    features { commitStatusPublisher { /* ... */ } }
})
```

Composite wymaga VCS roota (żeby wiedział, jakiej rewizji dotyczy), ale nie
checkoutuje kodu na agencie.

---

### 5. Versioned settings: konfiguracja w repo

**Dlaczego to ważne:** bez tego edycja w UI to zmiana bez historii. Z versioned settings
konfiguracja siedzi w `.teamcity/` w repo, przechodzi code review i da się ją cofnąć.

```kotlin
features {
    versionedSettings {
        mode = VersionedSettings.Mode.ENABLED
        rootExtId = "${PrasowkaVcs.id}"
        settingsFormat = VersionedSettings.Format.KOTLIN
        buildSettingsMode = VersionedSettings.BuildSettingsMode.PREFER_SETTINGS_FROM_VCS
    }
}
```

Kluczowe ustawienie to tryb budowania: *preferuj ustawienia z VCS* (build używa wersji
konfiguracji z tej samej rewizji co kod) vs *aktualne z serwera*. ❓ Nazwy enumów
sprawdź wg opisu wyżej (Show DSL).

---

### Czego nie omówiłem (i dlaczego)

| Temat | Powód |
|---|---|
| `matrix { }` (build features, wiele wariantów naraz, np. SDK 8/9) | pamiętam ideę, nie pamiętam składni wartości ❓ |
| `parallelTests { numberOfBatches = N }` | wymaga runnera, który rozumie podział testów; skrypt `script` sam z siebie nie zadziała ❓ |
| `dockerCompose`, logowanie do rejestru | pola nieznane z pewnością |

---

### ✅ Co zweryfikowano, a czego nie

**Zweryfikowane: nic w sensie kompilacji.** Każde polecenie Bash (w tym `java -version`)
zostało odrzucone przez środowisko, więc nie sprawdziłem ani obecności JDK/Mavena, ani nie
próbowałem pobrania. Nie wklejam żadnego "outputu" - nie mam go. Kod z wydania #3
też pozostaje niezweryfikowany.

Jak sprawdzić samemu: JDK 21 + `mvn compile` w `.teamcity/` (zob.
[`code/README.md`](code/README.md)). Błąd kompilatora wskaże linię - zacznij od
miejsc oznaczonych `[?]`.

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #4 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
