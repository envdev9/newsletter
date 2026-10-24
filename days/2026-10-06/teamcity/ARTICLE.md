<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #13 — 6 października 2026

![TeamCity](https://img.shields.io/badge/TeamCity-000000?style=for-the-badge&logo=teamcity&logoColor=white)
![Merge](https://img.shields.io/badge/cascading%20merge-zmierzony%20na%20żywo-brightgreen?style=for-the-badge)

## TeamCity: cascading merge `feature → integration → main` — z prawdziwym agentem i trzema pułapkami

</div>

---

> _"W #8 stało: 'dwa `merge{}` na jednym build type — składniowo możliwe, nie testowane'.
> Dziś przetestowane. Działa. Ale pierwsze trzy próby nie scaliły niczego."_

Wydanie #8 skończyło się obietnicą: łańcuch merge'y na żywym serwerze. Dziś ją spłacamy, i to
na maksimum tego, co da się zrobić w piaskownicy: serwer `jetbrains/teamcity-server:2025.07`
w Dockerze, **prawdziwy agent** (`jetbrains/teamcity-agent:2025.07`), lokalne repo Git i builds, które
naprawdę scalają gałęzie. Kod: [`code/`](code/), instrukcja i surowe logi: [`code/README.md`](code/README.md).

---

### 1. Konstrukcja łańcucha

Jeden build type `Verify`, dwa feature'y `merge { }`:

| Etap | `branchFilter` | `destinationBranch` | Polityka | Warunek |
|---|---|---|---|---|
| 1 | `+:feature/*` | `integration` | merge commit (domyślna) | `successful` (domyślny) |
| 2 | `+:integration` | `main` | `FAST_FORWARD` | `noNewTests` |

Do tego VCS trigger z `+:*` — to on łączy etapy. Merge do `integration` tworzy nowy commit,
trigger widzi go, buduje `integration`, a zielony build na `integration` uruchamia etap 2.
Same feature'y niczego nie uruchamiają, tylko reagują na zakończone buildy.

```kotlin
features {
    merge {
        branchFilter = "+:feature/*"
        destinationBranch = "integration"
        commitMessage = "Auto-merge: %teamcity.build.branch% (build #%build.number%)"
        mergePolicy = AutoMerge.MergePolicy.ALWAYS_MERGE
        mergeCondition = "successful"
        runPolicy = AutoMerge.RunPolicy.AFTER_BUILD_FINISH
    }
    merge {
        branchFilter = "+:integration"
        destinationBranch = "main"
        commitMessage = "Auto-merge: %teamcity.build.branch% (build #%build.number%)"
        mergePolicy = AutoMerge.MergePolicy.FAST_FORWARD
        mergeCondition = "noNewTests"
        runPolicy = AutoMerge.RunPolicy.BEFORE_BUILD_FINISH
    }
}
```

Ten plik (`code/.teamcity/settings.kts`, razem z VCS rootem i profilem chmurowym z sekcji 4)
skompilował się przeciw repo żywego serwera:

```
[INFO] --- teamcity-configs:2025.07:generate (generate-teamcity-config) @ cascade-merge-dsl ---
[INFO] Generate TeamCity configs in /work/target/generated-configs, format kotlin, dslDir: /work
[INFO] BUILD SUCCESS
[INFO] Total time:  37.965 s
```

---

### 2. Wynik: graf z repo serwera

Dwie gałęzie funkcjonalne, `feature/x` i `feature/y`, przeszły przez łańcuch. Stan repo po sesji:

```
*   5bda049 (main, integration) Auto-merge: feature/y (build #9)
|\
| * 6afbfb1 (feature/y) feature y
|/
*   84df7f3 Auto-merge: feature/x (build #4)
|\
| * 17330f8 (HEAD -> feature/x) feature x
|/
* 09ccff7 base
```

`main` i `integration` wskazują ten sam commit — etap 2 zrobił fast-forward, bo `integration` było
potomkiem `main`. Najciekawszy moment: build #10 na `integration` miał `triggered type="vcs"` —
nikt go nie kliknął, odpalił go trigger po merge'u z etapu 1. Część buildów kolejkowałem ręcznie
przez REST (#4, #6, #9), by nie czekać na detekcję zmian; łańcuch od merge'u do builda na
`integration` poszedł już sam.

> 📌 Uczciwie: obserwowałem to na lokalnym repo `file://` w kontenerach, nie na GitHubie.
> Pełnego przebiegu od zera na ostatecznych plikach REST nie powtarzałem — sesja szła
> iteracyjnie, z poprawkami.

---

### 3. Trzy pułapki, które kosztowały pierwsze próby

**Pułapka 1 — `destinationBranch` to nazwa LOGICZNA.** W #8 wpisaliśmy `refs/heads/main`, bo
VCS root miał domyślny branch spec. Tu branch spec ma nawiasy:

```
+:refs/heads/(feature/*)
+:refs/heads/(integration)
+:refs/heads/(main)
```

W TeamCity gałąź w nawiasie to nazwa logiczna (`integration`), a `refs/heads/integration` już nią
nie jest. Z `refs/heads/integration` build #3 dostał status FAILURE:

```
VcsException: Automatic merge failed: Cannot find destination branch to merge into: no VCS branch
maps to the 'refs/heads/integration' logical branch name according to the VCS root branch specification
```

Po zmianie na `integration` i `main` merge ruszył. Zauważ, że to feature PSUJE build: błąd merge'u
zamienia zielony build w czerwony.

**Pułapka 2 — brak `commitMessage` wyłącza merge, bez słowa w UI.** Build #2 był
SUCCESS, a w repo nic się nie zmieniło (build #1 padł wcześniej z powodu klucza branch spec, zob.
sekcja 5). Dopiero log serwera:

```
WARN ... AutoMergeFinishBuildListener: java.lang.IllegalArgumentException: Argument for @NotNull
parameter 'value' of jetbrains/buildServer/serverSide/impl/LazyValueResolver.resolve must not be null
```

Feature dodany przez REST bez `teamcity.automerge.message` powoduje wyjątek w listenerze; build
pozostaje zielony. Uwaga: ten sam brak jest w XML generowanym z DSL, gdy nie ustawisz
`commitMessage` — w moim pierwszym `settings.kts` parametru nie było. W DSL ustaw `commitMessage`
zawsze.

**Pułapka 3 — pusty `commitMessage` też nie merguje, tylko po cichu.** Show DSL pokazuje
`commitMessage = ""` dla featurów bez komunikatu, więc próbowałem wartości pustej. Build #8 (SUCCESS,
wyzwolony triggerem) nie scalił nic, a w `teamcity-server.log` nie było ani wyjątku, ani
komunikatu o pominięciu etapu 1 (udany merge, np. #4, też nie zostawia tam linii, więc cisza w logu
niczego nie odróżnia). Po wpisaniu tekstu build #9 z tej samej gałęzi scalił od razu.
To jedna para prób, więc traktuj ją jako silną wskazówkę, nie dowód: jedyna różnica to komunikat, ale
#8 szedł z triggera, a #9 z ręcznego kolejkowania.

---

### 4. Dowody z logu: co serwer sam mówi o pomijaniu merge'u

`PreTestedMergePredicate` loguje powód pominięcia każdego z dwóch feature'ów. To najlepsze narzędzie
diagnostyczne, jakie znalazłem:

```
VCS merge is skipped for build #3 ... Reason: branch filter "+:integration" does not accept build branch "feature/x"
VCS merge is skipped for build #5 ... Reason: build has other build problems except failed tests
VCS merge is skipped for build #6 ... Reason: branch filter "+:feature/*" does not accept build branch "integration"
```

Build #5 jest pouczający: etap 2 ma `mergeCondition = "noNewTests"`, czyli toleruje padnięte testy,
ale NIE inne problemy. Mój krok `git log` padł z kodem 128 — bo `checkoutMode = ON_SERVER` dostarcza
pliki bez katalogu `.git`. Ten build nie scalił `integration` do `main`. Po naprawie kroku (#6) `main`
dogonił `integration`.

> Stage 1 przy `feature/*` buduje się jako merge commit (`ALWAYS_MERGE` jest domyślny — dlatego
> Show DSL w pierwszym bloku nie ma `mergePolicy`). Drugi blok ma `FAST_FORWARD` jawnie.

---

### 5. Domyślne wartości znikają — i to samo dotyczy kluczy REST

Show DSL potwierdził mechanizm znany z #8: pierwszy `merge { }` wrócił bez `mergePolicy`,
`mergeCondition` i `runPolicy` — a były ustawione na wartości domyślne. Nowy drobiazg: trigger
`vcs { }` wrócił z samym `enableQueueOptimization = false`, bo `branchFilter = "+:*"` jest domyślny.

Dodatkowo błąd własny: klucz brancha w REST to `teamcity:branchSpec` (z dwukropkiem), nie
`teamcity.branchSpec`. Z kropką REST przyjął właściwość (200) i Show DSL wypisał ją jako
`param("teamcity.branchSpec", ...)` — nieznany parametr, który nic nie robi. Build na `feature/x`
dostał FAILURE z komunikatem, że gałąź nie jest monitorowana. Poprawny klucz DSL to `branchSpec`.

---

### 6. Drugi temat: cloud profile i agent pools w DSL

Zgodnie z planem z #8 sprawdziłem, które artefakty "agentowe" DSL w ogóle potrafi opisać.

| Obiekt | W DSL? | Dowód |
|---|---|---|
| Cloud profile Kubernetes | tak, `kubernetesCloudProfile { }` | `javap` na `configs-dsl-kotlin-latest:2025.07` + kompilacja + Show DSL |
| Cloud image Kubernetes | tak, `kubernetesCloudImage { }` | jw. |
| Agent pool | NIE | brak klasy z "pool" w jakimkolwiek z jarów pobranych z repo serwera; Show DSL po dodaniu puli i przypisaniu projektu nie zawierał jej |
| Przypisanie obrazu do puli | tylko jako liczba `agentPoolId` | pole w klasie `CloudImage` |

W `settings.kts` profil wygląda tak:

```kotlin
kubernetesCloudProfile {
    id = "k8s-demo"
    name = "K8s demo"
    serverURL = "http://teamcity.example.invalid:8111"
    terminateIdleMinutes = 15
    apiServerURL = "https://k8s.example.invalid:6443"
    namespace = "ci"
    authStrategy = token { token = "credentialsJSON:00000000-0000-0000-0000-000000000000" }
}
```

Kompilacja wygenerowała `CloudProfile` i `CloudImage` w `project-config.xml`. Te same obiekty
wprowadzone przez REST wróciły w Show DSL jako identyczna składnia. Drobna różnica: serwer przepisał
`id` profilu z `k8s-demo` na `kube-1` (a `system.cloud.profile_id` zostało stare — niespójne, nie
zbadałem skutków).

Agent pool tworzy się wyłącznie przez REST/UI (`POST /app/rest/agentPools`). Projekt można przypisać
do puli, nie tracąc `Default` — po przypisaniu projekt był w obu pulach równocześnie.

> ⚠️ Cloud profile nie połączył się z żadnym klastrem (adres `.invalid`) — sprawdziłem DSL, nie
> działanie profilu.

---

### 7. Dwie rzeczy z samego kompilowania

**Zagnieżdżone komentarze Kotlina.** Kilka kolejnych kompilacji nowego `settings.kts` kończyło się
`Runtime error: settings.kts: project definition is not found (a call to the project() function is
missing)` — mimo że `project { }` był w pliku. Podejrzany: komentarz blokowy z `feature/*` w środku.
W Kotlinie sekwencja `/*` wewnątrz komentarza blokowego otwiera drugi poziom, więc reszta pliku
zostaje "w komentarzu". Błędu kompilacji nie ma, jest tylko ten runtime. Po zamianie na komentarze
liniowe: `BUILD SUCCESS`. Uczciwie: w tym samym czasie zmieniałem też `pom.xml` (wzorzec z #8:
zależności `provided`, bez wtyczki Kotlina, zamiast pomu z ZIP-a Show DSL), więc nie wyizolowałem,
która zmiana była rozstrzygająca. Komentarz był jedyną rzeczą, która wyjaśnia błąd także przy
minimalnym pliku bez features, ale to wniosek z rozumowania, nie z eksperymentu kontrolnego.

**Kreator pierwszego startu = jeden proces.** Sesja HTTP (cookie z `GET /mnt`) musi żyć przez
cały kreator. Trzy osobne wywołania skryptu z #8 dały tym razem `The session is not authenticated`.
Nowy `tc_live.py wizard` robi wszystko w jednym procesie i czeka na kolejne etapy (`stage:`).

---

### Czego NIE sprawdziłem

| Temat | Powód |
|---|---|
| Merge na GitHubie/GitLabie | tylko lokalne repo `file://` w kontenerach |
| Konflikt merge'u i `FAST_FORWARD` przy rozjechanej gałęzi | nie próbowałem |
| Skutek rozjazdu `profileId` w cloud profile | zauważone, nie zbadane |
| Cloud profile z prawdziwym K8s | adres `.invalid`, żaden pod nie powstał |
| `AFTER_BUILD_FINISH` vs `BEFORE_BUILD_FINISH` | zachowanie nie porównywane |
| Pełny przebieg od zera na ostatecznych plikach `rest/` | sesja iteracyjna, poprawki przez PUT |
| `tc_live.py` po usunięciu domyślnego hasła | tylko kompilacja składni, bez uruchomienia |

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — komendy w kolejności, surowe logi z serwera i pułapki.
Sprzątanie po sesji: kontenery, obraz agenta, katalogi `/tmp` i 14 wolumenów Dockera usunięte;
obrazy serwera TeamCity i Mavena były na maszynie przed sesją i zostały.

---

<div align="center">

[← wróć do wydania #13 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
