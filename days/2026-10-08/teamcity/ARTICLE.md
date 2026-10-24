<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #15 — 8 października 2026

![TeamCity](https://img.shields.io/badge/TeamCity-000000?style=for-the-badge&logo=teamcity&logoColor=white)
![Build chain](https://img.shields.io/badge/build%20chain-sequential%20%2B%20parallel-brightgreen?style=for-the-badge)
![Domyślne](https://img.shields.io/badge/domy%C5%9Blna%20reakcja%20na%20pad-RUN__ADD__PROBLEM-red?style=for-the-badge)

## TeamCity: łańcuch buildów w 10 linijkach Kotlina — i domyślne ustawienie, które pozwala testom biec po padniętej kompilacji

</div>

---

> _"Pipeline się wywalił na kompilacji, a testy i tak ruszyły"._ W TeamCity to nie bug. To wartość domyślna
> zależności snapshot generowanej przez `sequential { }`. Zmierzyłem to dziś na żywym serwerze z agentem.

Do tej pory (#3, #5, #8) łączyliśmy buildy zależnościami snapshot ręcznie. Dziś DSL-owy skrót, który robi to za
Ciebie: **`sequential { }`** i **`parallel { }`**. Serwer `jetbrains/teamcity-server:2025.07` w Dockerze,
dwa agenty `jetbrains/teamcity-agent:2025.07`, konfiguracja wczytana z repo przez versioned settings (pętla z #14).
Kod i surowe wyniki: [`code/`](code/), instrukcja: [`code/README.md`](code/README.md).

**Dlaczego to ważne dla .NET deva?** Typowy pipeline to `restore/build → testy + analiza → pack → publish`.
Opisanie go jako łańcucha daje Ci ponowne użycie wyników (Compile raz, nie przy każdym kliknięciu), równoległość
(testy obok lintera) i kontrolę nad tym, co się dzieje, gdy etap pada. Ta ostatnia kontrola ma pułapki.

---

### 1. Cały łańcuch w jednym bloku

```kotlin
project {
    val chain = sequential {
        buildType(Stage("Compile", "echo compiling && test ! -f /tmp/fail-compile"))
        parallel {
            buildType(Stage("Test", "echo testing && sleep 5"))
            buildType(Stage("Lint", "echo linting && sleep 5 && test ! -f /tmp/fail-lint"))
        }
        buildType(Stage("Package", "echo packaging"), options = {
            reuseBuilds = ReuseBuilds.NO
            onDependencyFailure = FailureAction.FAIL_TO_START
        })
        buildType(Stage("Summary", "echo summary"), options = {
            onDependencyFailure = FailureAction.IGNORE
            onDependencyCancel = FailureAction.IGNORE
        })
    }
    chain.buildTypes().forEach { buildType(it) }
}
```

`Stage` to moja malutka klasa dziedzicząca po `BuildType` (id, nazwa, jeden krok `script`). Cała magia jest w
`sequential`: **to makro**, które pisze za Ciebie bloki `snapshot(...)`. Dowód: Show DSL z żywego serwera zwraca
je rozwinięte (dla `Package`):

```kotlin
dependencies {
    snapshot(ChainDemo_Lint) {
        reuseBuilds = ReuseBuilds.NO
        onDependencyFailure = FailureAction.FAIL_TO_START
    }
    snapshot(ChainDemo_Test) {
        reuseBuilds = ReuseBuilds.NO
        onDependencyFailure = FailureAction.FAIL_TO_START
    }
}
```

`parallel` w środku daje dwie krawędzie do `Package` i żadnej między `Test` a `Lint`.

**Kompilacja:** ten sam `settings.kts` przeszedł `mvn compile` w kontenerze `maven:3.9-eclipse-temurin-21`
względem repo pluginów żywego serwera: `BUILD SUCCESS` (jak w #8/#13). Pierwsza próba z zimnym cache Mavena
trwała 3 min 25 s, następne 1–2 min.

---

### 2. `parallel` znaczy "niezależne", nie "jednocześnie"

Z jednym agentem zmierzyłem (kolumny: start–koniec, czas serwera):

```
3 Lint  #1  01:27:01 – 01:27:11
2 Test  #1  01:27:12 – 01:27:21
```

Wykonały się jedno po drugim, bo `parallel` tylko **usuwa zależność** między nimi. Po dołożeniu drugiego agenta
`Test #2` i `Lint #2` wystartowały w tej samej sekundzie (`01:29:08`). Planowanie równoległości to sprawa agentów,
nie DSL-a.

---

### 3. Ponowne użycie: kolejka kłamie, ale chwilę

Drugie uruchomienie `Summary` bez żadnych zmian. W kolejce zobaczyłem **pięć** buildów (id 6–10: cały łańcuch),
po kilku sekundach zniknęły cztery z nich, a `Summary #2` wystartował po 6 s i podpiął się pod **istniejący**
`Package #1` (build 4). Serwer wstawia do kolejki kopie, a potem, po sprawdzeniu zmian, zastępuje je
buildami do ponownego użycia. Nie ma w tym VCS (brak rootów w buildach, `changes: count 0`), a ponowne użycie
i tak działa.

Potem uruchomiłem `Package` bezpośrednio. Opcja `reuseBuilds = ReuseBuilds.NO` na `Package` dotyczy zależności
`Test` i `Lint`, więc:

| Build | Wynik |
|---|---|
| `Compile` | nie uruchomiony ponownie (zostaje `#1`) |
| `Test #2`, `Lint #2` | nowe, mimo że `#1` były zielone |
| `Package #2` | nowy |

Czyli: opcje podajesz przy **odbiorcy** zależności, a odnoszą się do tego, czy wolno zabrać gotowy build
**poprzednika**.

---

### 4. Jak padnie etap: trzy zachowania zmierzone

Padnięcie `Lint` wymusiłem plikiem `/tmp/fail-lint` na agentach (`test ! -f ...`), bez zmiany konfiguracji.

| Zależność | Wynik zmierzony |
|---|---|
| `Package` z `FAIL_TO_START` | build `#N/A`, `failedToStart: true`, status "Snapshot dependency failed: ... Lint". Skrypt się nie wykonał. `Test #3` w tym czasie dobiegł do końca zielony |
| `Summary` z `IGNORE` na tym samym nieudanym `Package` | `Summary #3` **SUCCESS** (uruchomiony przez REST z jawnie wskazanym builem 18) |
| `Test` z domyślnym `sequential` na padniętym `Compile` | `Test #4` **uruchomił się** (9 s na agencie) i skończył `FAILURE: Snapshot dependency failed: ... Compile (new)` |

Ostatni wiersz to tytułowy haczyk. W wygenerowanym XML-u `Test` ma
`run-build-if-dependency-failed = RUN_ADD_PROBLEM`: "uruchom build, ale dodaj problem". Kosztuje Cię to czas
agenta i sprawia, że testy biegną na kodzie, który się nie skompilował. Jeśli chcesz zatrzymania łańcucha,
**ustaw `FAIL_TO_START` jawnie** w `options` (tak jak zrobiłem przy `Package`).

Drugi haczyk: Show DSL wypisuje tę domyślną zależność jako **pusty blok**:

```kotlin
snapshot(ChainDemo_Compile) {
}
```

Patrząc na kod z "Show DSL" nie zobaczysz, że ten etap nie zatrzyma się po błędzie poprzednika.

---

### Podsumowanie

| Fakt | Zmierzone |
|---|---|
| `sequential`/`parallel` to makro generujące `snapshot(...)` | tak, Show DSL zwraca rozwinięte bloki |
| `parallel` = brak zależności, nie równoległość | 1 agent: po kolei, 2 agenty: ta sama sekunda |
| Zbędne buildy w kolejce przy ponownym użyciu | 5 w kolejce, uruchomiony 1 |
| `reuseBuilds = NO` | `Compile` użyty ponownie, `Test`/`Lint`/`Package` nowe |
| `FAIL_TO_START` | `failedToStart`, krok się nie wykonuje |
| `IGNORE` | etap biegnie po nieudanym poprzedniku |
| Domyślne `sequential` | etap biegnie po nieudanym poprzedniku i kończy się FAILURE |

---

### Czego NIE sprawdziłem

| Temat | Powód |
|---|---|
| Czy zwykłe `snapshot(X) { }` (bez `sequential`) ma ten sam domyślny `RUN_ADD_PROBLEM` | sprawdzałem tylko to, co wygenerował `sequential` |
| `Summary` bez `IGNORE` jako kontrola | nie uruchomiłem wersji bez opcji, więc nie wiem na pewno, co by zrobił |
| `onDependencyCancel`, `ReuseBuilds.ANY`, `runOnSameAgent` | tylko kompilacja i Show DSL, bez uruchomienia |
| Łańcuch z prawdziwym VCS (synchronizacja rewizji między etapami) | buildy bez roota, tylko repo ustawień |
| Zależności artefaktowe w łańcuchu | nie dodawałem |
| `parallel` zagnieżdżone w `parallel` | nie próbowałem |
| `Summary` na padniętym `Package` w zwykłym uruchomieniu | build 18 wskazałem jawnie w żądaniu REST, żeby wymusić ten scenariusz |

---

### 📎 Jak uruchomić kod z tego wydania

[`code/README.md`](code/README.md): komendy w kolejności i surowe odpowiedzi serwera. Sprzątanie: kontenery
`tc-p15`, `tc-p15-agent`, `tc-p15-agent2` usunięte z `-v`, obraz agenta pobrany przeze mnie usunięty, katalog roboczy
(hasło demo, cache Mavena) usunięty. Obrazy serwera i Mavena były przed sesją i zostały.

---

<div align="center">

[← wróć do wydania #15 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
