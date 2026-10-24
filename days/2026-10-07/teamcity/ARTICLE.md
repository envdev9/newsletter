<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #14 — 7 października 2026

![TeamCity](https://img.shields.io/badge/TeamCity-000000?style=for-the-badge&logo=teamcity&logoColor=white)
![Versioned Settings](https://img.shields.io/badge/versioned%20settings-pętla%20zmierzona%20na%20żywo-brightgreen?style=for-the-badge)
![Konflikt](https://img.shields.io/badge/konflikt-łatka%20vs%20settings.kts-orange?style=for-the-badge)

## TeamCity: konfiguracja w Gicie działa w OBIE strony — i potrafi się pokłócić sama ze sobą

</div>

---

> _"Mój config jest w repo, więc jest bezpieczny"._ Do chwili, gdy ktoś kliknie zmianę w UI, a drugi
> człowiek zrobi push do tego samego kroku. Wtedy serwer odmawia przyjęcia Twojego commita, a ślad
> zostaje w statusie versioned settings i w logu.

W #8 i #13 pokazywałem serwer, który JEDNORAZOWO generuje Kotlin (Show DSL). Dziś domykamy pętlę, którą
zapowiadał `STATE.md`: **`versionedSettings` z prawdziwym repo**. Serwer `jetbrains/teamcity-server:2025.07`
w Dockerze, repo `file:///srv/settings.git` w jego kontenerze, żadnego agenta (nic się tu nie buduje).
Kod i surowe logi: [`code/`](code/), instrukcja: [`code/README.md`](code/README.md).

**Dlaczego to ważne dla .NET deva?** Bo po włączeniu tej funkcji config CI przestaje być "stanem serwera",
a staje się kodem z code review — ale tylko jeśli rozumiesz, co się dzieje, gdy zmienia go dwóch aktorów:
człowiek w Gicie i człowiek w UI.

---

### 1. Włączenie: serwer sam commituje (po minucie)

Jedno wywołanie REST (`rest/04-versioned-settings-enable.json`): `synchronizationMode: enabled`, `format: kotlin`,
VCS root wskazujący repo. Efekt w repo (po ok. minucie — serwer kompiluje DSL u siebie):

```
5fe014a admin Versioned settings configuration updated (TeamCity change in 'Loop Demo' project)
 .teamcity/pom.xml      | 104 +
 .teamcity/settings.kts |  42 +
```

Serwer wygenerował całe `settings.kts` (projekt + build type `Hello` z krokiem `echo hello-v1`) oraz `pom.xml`.
W logu pojawiła się jedna pułapka: przełączenie projektu na Kotlin z repo bez ustawień oznacza, że **projekt jest
na chwilę read-only**, „waiting for initial commit from VCS to be applied”. Jest to komunikat WARN w
`teamcity-versioned-settings.log`, nie błąd.

> 📌 Uwaga: VCS root samego repo z ustawieniami nie trafił do wygenerowanego `settings.kts` (a istnieje na
> serwerze). Zaobserwowałem, nie zbadałem dlaczego.

---

### 2. Pętla dewelopera: push → serwer

Z klona repo wypchnąłem `loop/v2-settings.kts`: zmieniony krok, nowy parametr `greeting` i **cały nowy
build type `Bye`**, którego serwer wcześniej nie znał. Pomiar: **82 s od pushu do `LoopDemo_Bye` w REST**.
Log rozkłada to na etapy: wykrycie rewizji (`Detected new revision bde2ce6` 01:30:07), potem 63 s generowania
DSL (`Settings from VCS are generated` 01:31:10) i przeładowanie:

```
changed files: [created: [LoopDemo/buildTypes/LoopDemo_Bye.xml], updated: [LoopDemo/buildTypes/LoopDemo_Hello.xml]]
```

Te ok. 30–65 s na każdą zmianę to koszt kompilacji Kotlina po stronie serwera. W pętli „zmień → sprawdź” jest to
odczuwalne, dlatego lokalnie kompiluj `settings.kts` Mavenem (jak w #8/#13), zanim pushniesz.

---

### 3. Pętla UI → repo: serwer NIE edytuje Twojego pliku

Zmieniłem treść kroku przez REST (odpowiednik klikania w UI). Serwer zacommitował to jako autor `admin`,
ale **nie dotknął `settings.kts`**. Dodał nowy plik:

```
eba27b2 admin New build step parameter added
 .teamcity/patches/buildTypes/Hello.kts | 26 +
```

```kotlin
changeBuildType(RelativeId("Hello")) {
    expectSteps {
        script {
            name = "Greet"
            scriptContent = "echo hello-v2 %greeting%"
        }
    }
    steps {
        update<ScriptBuildStep>(0) {
            clearConditions()
            scriptContent = "echo hello-from-rest %greeting%"
        }
    }
}
```

To **łatka**: „oczekuję, że krok wygląda tak (`expectSteps`), i zmień go na to (`update`)”. Komentarz w pliku
mówi wprost: żeby ją „zastosować”, zmień build type i usuń łatkę. Dla Kotlin DSL, który jest programem, a nie
wygenerowanym plikiem, to jedyny bezpieczny sposób — serwer nie przepisuje Twojego kodu. Po odczycie tego commita
przez serwer log mówi `settings are up-to-date, skip reloading projects`: pętla jest idempotentna.

---

### 4. Konflikt: łatka kontra `settings.kts`

Teraz najciekawsze. Łatka czeka w repo, a deweloper zmienia TEN SAM krok w `settings.kts` (`loop/v3-conflict-settings.kts`
→ `echo hello-v3`). Serwer odczytał rewizję `8e28915`, skompilował DSL, zaaplikował łatkę — i odrzucił całość:

```
Actual build step and build step expected by patch at position 0 are different, reason:
Different values of parameter with name 'script.content': 'echo hello-v3 %greeting%' != 'echo hello-v2 %greeting%'
```

Status (`GET /app/rest/projects/id:LoopDemo/versionedSettings/status`) pokazuje `type: warn`,
`UI changes error` oraz plik `patches/buildTypes/Hello.kts`. **Serwer zostaje przy ostatniej dobrej
konfiguracji** — zweryfikowałem, że krok nadal brzmi `echo hello-from-rest %greeting%`, czyli Twój push z `v3` nie
obowiązuje. (UI nie oglądałem — sprawdzałem tylko REST i log.)

**Haczyk, który mnie zaskoczył:** w tym stanie wprowadziłem kolejną zmianę przez REST (`greeting` → `czesc`).
Serwer ją przyjął (200) i zacommitował jako rozszerzenie łatki NA WIERZCH zepsutej rewizji (`d93a614`). Następny
odczyt skończył się tym samym błędem. Czyli: dopóki status jest błędny, każda zmiana w UI pogłębia dług, a nie
naprawia.

**Naprawa** (`loop/v4-resolved-settings.kts`): wnieś zmiany z łatki do `settings.kts` ręcznie i `git rm` łatkę
w tym samym commicie. Wynik: `Changes from VCS are applied to project settings, last change 'v4: ...', time spent:
32s,897ms`, krok `echo hello-v4 %greeting%`, `greeting` = `czesc`.

---

### 5. Literówka: błąd kompilacji z linią

`loop/v5-compile-error-settings.kts` (`scriptContents` zamiast `scriptContent`):

```json
"versionedSettingsError":[{"message":"Unresolved reference: scriptContents","type":"Compilation error","file":"settings.kts [23:13]"}]
```

Błąd z numerem linii i kolumny, a serwer znów zostaje przy poprzedniej dobrej wersji (`greeting` = `czesc`).
Wniosek praktyczny: **status versioned settings jest Twoim "pipeline'em" dla configu** — monitoruj go.

---

### Podsumowanie pułapek

| Sytuacja | Co robi serwer |
|---|---|
| Włączenie Kotlin na pustym repo | commit `settings.kts` + `pom.xml` po ok. minucie; projekt chwilowo read-only |
| Push z nowym build type | pojawia się w REST po 66–82 s (pomiar) |
| Zmiana w UI/REST | nowy plik `patches/buildTypes/<Id>.kts`, `settings.kts` nietknięty |
| Ta sama zmiana w `settings.kts` i w łatce | odrzuca rewizję (`UI changes error`), zostaje stara konfiguracja |
| Zmiana w UI przy błędnym statusie | przyjęta i dokładana do łatki na zepsutej rewizji |
| Błąd kompilacji DSL | `Compilation error` z linią i kolumną, stara konfiguracja zostaje |

---

### Czego NIE sprawdziłem

| Temat | Powód |
|---|---|
| Czy build faktycznie używa ustawień z rewizji VCS (`buildSettingsMode`) | brak agenta, żaden build się nie wykonał |
| Blok `versionedSettings { }` wewnątrz DSL | konfigurację włączyłem przez REST |
| GitHub/GitLab, uwierzytelnianie, webhooki, wartości secure | tylko lokalne repo `file://` |
| Jednoczesny push serwera i człowieka (rozjazd historii) | nie próbowałem |
| Interwał pollingu repo mierzony osobno | mam tylko czas całkowity (66–82 s) |
| `showSettingsChanges: true` z mojego żądania | odpowiedź zwróciła `false`, nie sprawdziłem czemu |

---

### 📎 Jak uruchomić kod z tego wydania

[`code/README.md`](code/README.md) — komendy w kolejności i surowe odpowiedzi serwera. Sprzątanie: kontener
`tc-p14` usunięty z `-v` (jego wolumeny anonimowe razem z nim), plik z hasłem demo skasowany; obraz serwera
TeamCity był na maszynie przed sesją i został.

---

<div align="center">

[← wróć do wydania #14 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
