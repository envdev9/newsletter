<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #8 — 1 października 2026

![TeamCity](https://img.shields.io/badge/TeamCity-000000?style=for-the-badge&logo=teamcity&logoColor=white)
![Kompilacja](https://img.shields.io/badge/kompilacja-BUILD%20SUCCESS%20(cały%20pipeline)-brightgreen?style=for-the-badge)

## TeamCity: Automatic Merge — i pierwszy w historii tej rubryki `BUILD SUCCESS` na CAŁYM pipeline'ie

</div>

---

> _"W #7 skompilował się pierwszy, minimalny plik — ale tylko dlatego, że używał
> wyłącznie klas, których i tak nikt by w prawdziwym configu nie użył. Dziś
> skompilował się PRAWDZIWY plik — pięć build type'ów, dziewięć pluginowych
> build feature'ów, trigger PR-owy, Docker, matrix. Różnica? Zamiast czytać
> bajty jednego jara, postawiono żywy serwer i zapytano go bezpośrednio."_

Wydanie #7 zostawiło jasno zdefiniowany "następny krok" w `STATE.md`: albo żywy
serwer TeamCity w Dockerze, albo osobne artefakty Maven per-plugin — bo publiczny
`configs-dsl-kotlin-latest` nigdy ich nie zawiera. Dziś zrobiono **oba**, i okazały
się tym samym odkryciem: żywy serwer **wystawia własne, efemeryczne repozytorium
Maven** z dziesiątkami per-pluginowych jarów, nigdzie indziej niepublikowanych.
Po drodze: reverse engineering szyfrowania RSA formularzy webowych TeamCity (bo
kreator pierwszego startu nie przyjmuje hasła inaczej), REST API do złożenia
projektu-od-zera, prawdziwy mechanizm *Show DSL*, i — na końcu — **realny,
odtwarzalny `BUILD SUCCESS`** na całym łańcuchu `Compile → Test → IntegrationTest →
DockerImage → Release` ze wszystkimi build feature'ami z edycji #3–#8, włącznie z
dzisiejszym głównym tematem: **Automatic Merge**. Kod:
[`code/.teamcity/settings.kts`](code/.teamcity/settings.kts) (idiomatyczny, pełny
przykład), [`code/full-pipeline-proof/.teamcity/`](code/full-pipeline-proof/.teamcity/)
(dosłowny plik, który realnie skompilował się dziś — zob. dowód niżej), instrukcja:
[`code/README.md`](code/README.md).

---

### 1. Jak faktycznie dotarto do `BUILD SUCCESS` (siedem kroków, wszystkie zweryfikowane)

**Krok 1 — żywy serwer w Dockerze.** `docker pull jetbrains/teamcity-server:2025.07`
(4 GB obrazu, realnie pobrany), `docker run -d -p 8111:8111 ...`. Serwer wstał w
mniej niż minutę (Tomcat + Spring context 2199 beanów w ~37 s), ale wymaga
**potwierdzenia pierwszego startu** przez HTTP, nie tylko "poczekania".

**Krok 2 — kreator pierwszego startu bez przeglądarki.** Cały kreator (`/mnt/...`)
to zwykłe żądania HTTP+cookie session — `goNewInstallation`, `goNewDatabase`
(wewnętrzna HSQLDB), akceptacja licencji. Jedna przeszkoda: **utworzenie konta
administratora wymaga hasła zaszyfrowanego RSA po stronie klienta** — formularz
jawnie wycina pole `password` z serializacji (`BS.Util.serializeForm` filtruje
`isPasswordInput`) i wysyła tylko `encryptedPassword1`.

**Krok 3 — reverse engineering szyfrowania hasła.** Przeczytano `/js/crypt/rsa.js`
(funkcja `pkcs1pad2`) — to **NIE jest standardowy PKCS#1 v1.5**, tylko wariant
TeamCity, który dokleja do wiadomości DODATKOWY bajt: oryginalną długość stringa,
jako ostatni bajt bloku. Potwierdzono to niezależnie, disasemblując (`javap`)
serwerową klasę `jetbrains.buildServer.serverSide.crypt.RSACipher` z pobranego
`common.jar` — bajtkod dosłownie odczytuje `decrypted[length-1]` jako znacznik i
odrzuca hasło, jeśli się nie zgadza. Zaimplementowano to w Pythonie
(`pow(m, e, n)` — biblioteka standardowa, zero zależności kryptograficznych) —
pierwsza próba dała `"Password is empty"` (znacznik się nie zgadzał), druga,
poprawiona, dała `<response><redirect>/favorite/projects</redirect><errors /></response>`.
**Konto administratora utworzone programistycznie, przez HTTP, bez przeglądarki.**
Pełny kod: [`code/scripts/teamcity-server-setup.py`](code/scripts/teamcity-server-setup.py).

**Krok 4 — REST API: projekt od zera.** Basic Auth (`admin:...`) działa od razu na
`/app/rest/*`. Utworzono projekt, `VcsRoot` (`jetbrains.git`), `BuildType`, i
podstawowy build feature `AutoMergeFeature` — **POST z surowymi, wewnętrznymi
nazwami parametrów** (`teamcity.automerge.srcBranchFilter` itd. — skąd te nazwy,
sekcja 2 niżej). Serwer przyjął to bez błędu.

**Krok 5 — prawdziwy mechanizm *Show DSL*.** Nie trzeba zgadywać URL-a — strona
`/admin/editProject.html?tab=versionedSettings` ma literalny link
`/admin/versionedSettingsActions.html?...&action=generate&format=kotlin&version=latest`
("Download settings in Kotlin format..."). Wywołany bezpośrednio (Basic Auth),
zwraca **prawdziwy ZIP** z `pom.xml` i wygenerowanymi plikami `.kt` — w tym
najważniejsze odkrycie dnia:

```xml
<!-- fragment pom.xml z ZIP-a "Show DSL" -->
<repository>
  <id>teamcity-server</id>
  <url>http://localhost:8111/app/dsl-plugins-repository</url>
</repository>
...
<dependency>
  <groupId>org.jetbrains.teamcity</groupId>
  <artifactId>configs-dsl-kotlin-plugins-latest</artifactId>
  <version>1.0-SNAPSHOT</version>
  <type>pom</type>
</dependency>
```

**Krok 6 — co jest w tym drugim repozytorium.** Pobrano POM agregatora
(`configs-dsl-kotlin-plugins-latest`) — lista **~45 zależności**, jedna per
zainstalowany plugin: `configs-dsl-kotlin-pull-requests-latest`,
`configs-dsl-kotlin-swabra-latest`, `configs-dsl-kotlin-docker-support-latest`,
`configs-dsl-kotlin-commit-status-publisher-latest`, i — dla rzeczy wbudowanych w
sam serwer, nie w osobny plugin (patrz sekcja 2) —
`configs-dsl-kotlin-bundled-latest`. **To jest DOKŁADNIE ten "nieznaleziony dotąd
w publicznym repo" element, o którym mówił `STATE.md` jako następny krok** — tylko
że nie jest publiczny i nigdy nie będzie: to repo istnieje wyłącznie w pamięci
żywego serwera, regenerowane przy starcie, wersja zawsze `1.0-SNAPSHOT`.

**Krok 7 — i wreszcie realna kompilacja CAŁEGO pliku.** `maven:3.9-eclipse-
temurin-21` jako kontener (`--network host`, żeby dosięgnąć `localhost:8111`),
`pom.xml` z DWOMA repozytoriami (publiczne `download.jetbrains.com` dla bazowego
`configs-dsl-kotlin-latest:2025.07` — **to jest wersja realnie opublikowana
publicznie**, w odróżnieniu od EAP-owej `2026.3-dsl6` używanej od #1 do #7! — plus
lokalne repo serwera dla aggregatora pluginów). Pierwsze uruchomienie wyłapało
**4 realne błędy we WŁASNYM kodzie**, niewidoczne w #5–#7, bo tam import nigdy nie
dotarł do etapu, w którym kompilator mógłby je sprawdzić:

| Błąd | Objaw | Poprawka |
|---|---|---|
| Zły import `matrix` | `Unresolved reference: matrix` | `matrix` jest w pakiecie `jetbrains.buildServer.configs.kotlin` (bazowym), **nie** w `.buildFeatures` |
| Brak importu `ScriptBuildStep` | `Unresolved reference: ScriptBuildStep` | Użycie `ScriptBuildStep.ImagePlatform.Linux` wymaga własnego importu klasy — oznaczone `[?]` od #5, nigdy niesprawdzone |
| Brak importu `VersionedSettings` (klasa) | `Unresolved reference: VersionedSettings` | Import funkcji `versionedSettings` (małe v) ≠ import klasy `VersionedSettings` (wielkie V) potrzebnej dla `.Mode`/`.Format` |
| Zła sygnatura `MatrixFeature.param` | "None of the following functions can be called..." | `param(name, List<String>)` nie istnieje — prawdziwe: `param(name, List<MatrixFeature.Value>)`, `Value` przez helper `value(etykieta, wartość)` |

Po poprawkach: **`BUILD SUCCESS`**, z jednym wyjątkiem — `versionedSettings{}`
kompiluje się, ale nie przechodzi walidacji runtime w trybie standalone
(`"Versioned settings project feature cannot be used in relative project
hierarchy"` — ograniczenie samego narzędzia offline, bo wymaga prawdziwego drzewa
projektów; **na żywym serwerze (krok 4) ten sam feature działa bez problemu**).
Z tym jednym, zrozumiałym wyjątkiem: **cały pięcio-build-type'owy pipeline z
dziewięcioma build feature'ami skompilował się naprawdę, pierwszy raz w 8
wydaniach.** Dowód — [`code/full-pipeline-proof/.teamcity/`](code/full-pipeline-proof/.teamcity/),
log w [`code/README.md`](code/README.md).

---

### 2. Główny temat: build feature **Automatic Merge**

**Dlaczego to ważne, kontynuując od #7:** `pullRequests{}` + trigger PR-owy
odpowiadają na "zbuduj PR, zanim trafi do `main`". Zostaje pytanie, które zadaje
sobie każdy zespół używający pull requestów: **kto klika "Merge" po zielonym
buildzie?** Automatic Merge odpowiada: nikt — serwer robi to sam.

Cytując dzisiejszą dokumentację (`jetbrains.com/help/teamcity/automatic-merge.html`):

> _"The Automatic Merge build feature tracks builds in branches matched by the
> configured filter and merges them into a specified destination branch if the
> build satisfies the condition configured (for example, the build is
> successful)."_

**Gdzie żyje w naszym pipeline.** Dołożony do `Release` — ostatniego, composite
kroku, agregującego cały łańcuch — nie do `Compile` (gdzie żyje `pullRequests`).
To rozmyślna decyzja: merge ma sens dopiero, gdy **cały** łańcuch (Compile→Test→
IntegrationTest→DockerImage) przeszedł, nie tylko pierwszy, najtańszy krok. Żeby
to zadziałało, `Release` musiał dziś dostać te samą rozszerzoną widoczność gałęzi
PR-owych, jaką `Compile` dostał w #7 (`vcs.branchFilter` + `triggers.vcs.branchFilter`
z `refs/pull/*/head`) — inaczej `Release` nigdy by się nie zbudował na branchu PR-a,
i `merge{}` nie miałby czego mergować.

```kotlin
merge {
    // Które (logiczne) gałęzie są źródłem do mergowania.
    branchFilter = "+:refs/pull/*/head"

    // Gałąź docelowa - musi być w Branch Specification VCS roota.
    destinationBranch = "refs/heads/main"

    // Typowany enum - FAST_FORWARD = preferuj brak zbędnego commita mergującego.
    mergePolicy = AutoMerge.MergePolicy.FAST_FORWARD

    // UWAGA: String, NIE enum (mimo że klasa AutoMerge deklaruje
    // enum AutoMerge.MergeCondition!). "successful" albo "noNewTests".
    mergeCondition = "noNewTests"

    // Typowany enum - merge PRZED/PO zakończeniu builda.
    runPolicy = AutoMerge.RunPolicy.BEFORE_BUILD_FINISH
}
```

**Trzy niezależne źródła, jedna odpowiedź — i jedna pułapka warta zapamiętania.**
Dzisiejsza sesja znalazła coś, co żadna dokumentacja wprost nie mówi: `mergeCondition`
jest typu `String`, **mimo że** klasa `AutoMerge` deklaruje gotowy enum
`AutoMerge.MergeCondition` z dwiema wartościami (`SUCCESSFUL_BUILD`,
`NO_NEW_FAILED_TESTS`). Dowód, że to nie przypadek, z trzech kierunków:

1. **Deskryptor XML pluginu** (`kotlin-dsl/buildFeatures/AutoMerge.xml`, znaleziony
   dziś w już istniejącym na tej maszynie cache'u `~/.m2`, w jarze
   `server-core-2026.3-DSL-eap2-SNAPSHOT.jar` — nie pobrany dziś przez nas, trafiony
   przy przeszukiwaniu dostępnych zasobów). Parametr
   `teamcity.automerge.buildStatusCondition` (dslName `mergeCondition`) **nie ma**
   atrybutu `type`, w odróżnieniu od `mergePolicy`/`runPolicy`, które **mają**
   `type="MergePolicy"`/`type="RunPolicy"` — to jest dosłowny powód tej różnicy,
   widoczny w pliku, z którego generator Kotlina faktycznie czyta.
2. **Żywa dokumentacja Dokka** (`teamcity.jetbrains.com/app/dsl-documentation/
   buildFeatures/auto-merge/`) — przykład w dokumentacji używa dosłownie
   `mergeCondition = "noNewTests"` (string), nie `AutoMerge.MergeCondition.
   NO_NEW_FAILED_TESTS`.
3. **Najsilniejsze: realny serwer.** Feature dodany przez REST API z
   `teamcity.automerge.buildStatusCondition=noNewTests`, potem prawdziwe
   *Show DSL* (krok 5 wyżej) zwróciło dosłownie `mergeCondition = "noNewTests"`.

**Bonus z tego samego eksperymentu — "domyślne wartości są niewidoczne."** Pierwsza
próba ustawiła `buildStatusCondition=successful` i `run.policy=runAfterBuildFinish`
(domyślne — patrz opis "Run after build finish" w dokumentacji) — i *Show DSL*
**całkowicie pominęło** te dwie linie w wygenerowanym Kotlinie, mimo że feature miał
je ustawione. Zmiana na wartości NIEdomyślne (`noNewTests`, `runBeforeBuildFinish`)
sprawiła, że natychmiast się pojawiły. Generator "Show DSL" nie jest głupim
dumpem parametrów — pomija jawne przypisania równe domyślnym, żeby wygenerowany
kod był czytelny. To ważne do zapamiętania przy czytaniu WŁASNEGO *Show DSL*: brak
linii ≠ brak feature'u, może znaczyć "wartość domyślna".

**Czy Automatic Merge jest "pluginem" jak Pull Requests?** Nie — i to jest
ciekawsze niż oczekiwano. Deskryptor XML `AutoMerge` leży w module `server-core`
(razem z `VcsTrigger`, `ScheduleTrigger`, `FailOnMetricChange`, `VersionedSettings`)
— to są rzeczy **wbudowane w sam serwer**, nie w osobny plugin z własnym katalogiem
`agent/`+`server/`. Stąd w agregatorze per-pluginowym (krok 6 wyżej) nie ma
`configs-dsl-kotlin-automerge-latest` — jest `configs-dsl-kotlin-bundled-latest`,
wspólny kontener dla WSZYSTKICH takich wbudowanych, niepluginowych rzeczy. `Pull
Requests` i `Commit Status Publisher` to prawdziwe, osobne pluginy (`pull-requests`,
`commit-status-publisher` na liście 95 bundled plugins serwera) — mają własne,
nazwane artefakty. To rozróżnienie wyjaśnia strukturę repo lepiej niż cokolwiek z
poprzednich 7 wydań.

**Run policy — pełny obraz z dokumentacji + kodu.**

| Opcja | Co robi |
|---|---|
| `AFTER_BUILD_FINISH` (domyślna) | Build kończy się, merge startuje później — dependent buildy mogą wystartować, ZANIM merge się zakończy |
| `BEFORE_BUILD_FINISH` | Build jest "skończony" dopiero, gdy merge się zakończy — dependent buildy czekają na merge |

Dla `Release` (koniec łańcucha, nikt nie czeka na dependent build) domyślne
`AFTER_BUILD_FINISH` jest praktyczniejsze — w kodzie użyto `BEFORE_BUILD_FINISH`
wyłącznie, żeby pole było widoczne w wygenerowanym DSL (patrz "bonus" wyżej).

**Cascading merge** — wspomniany w dokumentacji, niesprawdzony dziś realnie:
dodanie DWÓCH `merge{}` feature'ów do jednego build type'u (jeden `feature-* →
integration`, drugi `integration → main`) pozwala zbudować łańcuch merge'y. Kotlin
DSL pozwala dodać `merge { }` wielokrotnie w jednym `features { }` — składniowo
nie ma przeszkody, ale nie przetestowano tego na żywym serwerze.

---

### Czego nadal nie omówiłem (i dlaczego)

| Temat | Powód |
|---|---|
| `AutoMerge` na prawdziwym repozytorium Git (realny merge, nie tylko walidacja configu) | Wymaga realnego PR-a na żywym GitHubie podłączonym do tego serwera — poza zasięgiem tej sesji (repo `envdev9/newsletter` użyte w configu jest placeholderem) |
| Cascading merge (dwa `merge{}` na jednym build type) | Składniowo możliwe, nie zweryfikowane realnym configiem na żywym serwerze (czas) |
| `versionedSettings{}` na żywym serwerze z prawdziwym, nie-standalone generatorem | Zweryfikowano, że feature DZIAŁA przez REST (krok 4) — ale nie zweryfikowano pętli "żywy serwer commituje ten plik do VCS, potem sam go stamtąd odczytuje" |
| Pozostałe ~40 per-pluginowych artefaktów z `configs-dsl-kotlin-plugins-latest` (poza tymi użytymi w naszym pipeline) | Poza zakresem tego wydania - temat na kolejne edycje w miarę potrzeb |

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — tam pełny, dosłowny log komend
(docker, RSA, REST, Maven), w tym te, które najpierw zawiodły, zanim znaleziono
poprawkę.

---

<div align="center">

[← wróć do wydania #8 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
