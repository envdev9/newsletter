# Kod do wydania #13 — TeamCity: cascading merge (feature → integration → main) na żywym serwerze

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Dwa `merge { }` na jednym build type tworzą łańcuch: `feature/*` → `integration` → `main`.
> Zmierzone na żywym serwerze TeamCity 2025.07 z prawdziwym agentem: build zielony na
> `feature/y` dał merge commit na `integration`, VCS trigger sam zbudował `integration`,
> a drugi `merge { }` przesunął `main` fast-forwardem. Po drodze trzy pułapki, które nie
> wychodzą w żadnej dokumentacji: `destinationBranch` to nazwa LOGICZNA (wg nawiasów w
> `branchSpec`), brak `commitMessage` wyłącza merge (wyjątek w logu), a pusty
> `commitMessage` wyłącza go po cichu.

## Struktura

```
code/
├── .teamcity/
│   ├── settings.kts          # DSL: 2x merge{}, VCS root z branchSpec, kubernetesCloudProfile + Image
│   └── pom.xml               # wzorzec z #8 (repo pluginów żywego serwera pod localhost:8111)
├── scripts/tc_live.py        # kreator pierwszego startu (RSA) + dowolny REST + "Show DSL" -> ZIP
├── rest/                     # 01-23: dosłowne ciała żądań REST użyte w sesji (kolejność = numer)
├── generated-sample/         # XML wygenerowany przez realny BUILD SUCCESS z .teamcity/
└── show-dsl-sample/          # Kotlin zwrócony przez serwer (Show DSL) dla projektu zbudowanego przez REST
```

Wymagania: Docker, Python 3, ok. 8 GB miejsca (obraz serwera ~4 GB, obraz agenta, obraz Mavena,
cache Mavena), ok. 20 minut.

---

## Część 1: odtworzenie krok po kroku

### 1.1 Serwer + kreator (bez przeglądarki)

```bash
docker run -d --name tc-p13 -p 8111:8111 jetbrains/teamcity-server:2025.07
export TC_ADMIN_PASSWORD='<wymysl-haslo-demo>'
python3 scripts/tc_live.py wizard
```

Zmierzony przebieg (fragment): `FIRST_START_SCREEN` → `goNewInstallation` → `DB_SETTINGS_SCREEN` →
`goNewDatabase` → `CREATE_NEW_DB` → ok. 20 razy `APPLICATION_STARTING` (co 5 s) → akceptacja
licencji → `createAdminSubmit -> 200 <response><redirect>/favorite/projects</redirect><errors /></response>`.

**Pułapka (zmierzona):** w #8 kreator był trzema osobnymi wywołaniami skryptu. Tu pierwsza próba
też tak wyglądała i skończyła się `The session is not authenticated. Access denied.` — sesja
(cookie z `GET /mnt`) musi przetrwać między krokami, więc `wizard` robi wszystko w jednym procesie.

### 1.2 Projekt przez REST

```bash
python3 scripts/tc_live.py rest POST /app/rest/projects                          rest/01-project.xml
python3 scripts/tc_live.py rest POST /app/rest/vcs-roots                         rest/02-vcsroot.xml
python3 scripts/tc_live.py rest POST /app/rest/buildTypes                        rest/03-buildtype.xml
python3 scripts/tc_live.py rest POST /app/rest/buildTypes/id:CascadeDemo_Verify/features rest/04-merge-stage1.xml
python3 scripts/tc_live.py rest POST /app/rest/buildTypes/id:CascadeDemo_Verify/features rest/05-merge-stage2.xml
```

Serwer przyjął DWA feature'y tego samego typu (`BUILD_EXT_1`, `BUILD_EXT_2`), oba `200`.

> Pliki `rest/` w ostatecznej postaci zawierają poprawki znalezione w trakcie sesji (nazwa
> logiczna w `dstBranch`, `message`, klucz `teamcity:branchSpec`, krok bez `git`). Sesja przebiegła
> INCREMENTALNIE (najpierw wersje błędne, potem poprawki PUT — pliki 10, 14, 15, 16, 17, 20 to
> te poprawki); kompletny przebieg od zera na ostatecznych plikach NIE został powtórzony.

### 1.3 Show DSL i kompilacja

```bash
python3 scripts/tc_live.py show-dsl CascadeDemo out.zip
```

Kompilacja własnego `settings.kts` względem repo serwera (kontener Mavena, `--network host`):

```bash
cd .teamcity
docker run --rm --network host -v "$PWD":/work -w /work maven:3.9-eclipse-temurin-21 mvn -B -ntp compile
```

Wynik (prawdziwy, ostatnia wersja pliku, cache Mavena ciepły):

```
[INFO] --- teamcity-configs:2025.07:generate (generate-teamcity-config) @ cascade-merge-dsl ---
[INFO] Generate TeamCity configs in /work/target/generated-configs, format kotlin, dslDir: /work
[INFO] BUILD SUCCESS
[INFO] Total time:  37.965 s
```

Uwaga: kontener działa jako root, więc `target/` w zamontowanym katalogu będzie należał do roota.
Kompiluj kopię katalogu (u mnie `/tmp`), nie katalog repo.

### 1.4 Prawdziwy merge: repo Git + agent

Repo demo powstało lokalnie (`git init -b main`, commit `base`, `git branch integration`,
gałąź `feature/x` z jednym commitem, `git clone --bare`), potem skopiowane DO KONTENERÓW
(serwer musi mieć możliwość pushu, agent — odczytu):

```bash
docker run -d --name tc-p13-agent --network host -e SERVER_URL=http://localhost:8111 -e AGENT_NAME=agent1 jetbrains/teamcity-agent:2025.07
docker exec -u 0 tc-p13 mkdir -p /srv
docker cp demo.git tc-p13:/srv/demo.git
docker exec -u 0 tc-p13 chown -R tcuser /srv/demo.git
docker exec -u 0 tc-p13 git config --system --add safe.directory '*'
```

(to samo dla agenta, bez `chown`). Agent po pierwszym połączeniu sam się aktualizuje (ok. minuta),
potem `PUT /app/rest/agents/id:1/authorized` z ciałem `true`. Ostatecznie VCS root wskazuje
`file:///srv/demo.git`, build type ma `checkoutMode = ON_SERVER` (agent nie musi widzieć repo, ale
wtedy w katalogu builda NIE MA `.git` — mój pierwszy krok `git log` padł z kodem 128) i VCS trigger
z `branchFilter = +:*` (`rest/19-vcs-trigger.xml`).

---

## Część 2: dosłowne wyniki

### 2.1 Show DSL: dwa `merge{}` wracają jako dwa bloki

```kotlin
    features {
        merge {
            branchFilter = "+:feature/*"
            destinationBranch = "integration"
            commitMessage = "Auto-merge: %teamcity.build.branch% (build #%build.number%)"
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

Pierwszy blok nie ma `mergePolicy`/`mergeCondition`/`runPolicy`: ustawione tam wartości
(`alwaysCreateMergeCommit`, `successful`, `runAfterBuildFinish`) są domyślne i generator je pomija.

### 2.2 Efekt w repo (serwer, po całej sesji)

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

### 2.3 Dziennik serwera (`teamcity-server.log`), wybrane linie

```
WARN ... AutoMergeFinishBuildListener: java.lang.IllegalArgumentException: Argument for @NotNull parameter 'value' of jetbrains/buildServer/serverSide/impl/LazyValueResolver.resolve must not be null
   (feature bez teamcity.automerge.message — merge nie nastąpił, build nadal SUCCESS)

INFO PreTestedMergePredicate - VCS merge is skipped for build #3 ... Reason: branch filter "+:integration" does not accept build branch "feature/x"
WARN AutoMergeFinishBuildListener - Error while merging sources of the build #3
VcsException: Automatic merge failed: Cannot find destination branch to merge into: no VCS branch maps to the 'refs/heads/integration' logical branch name according to the VCS root branch specification
   (build #3 zakończył się FAILURE)

INFO PreTestedMergePredicate - VCS merge is skipped for build #5 ... Reason: build has other build problems except failed tests
   (etap 2, noNewTests: build #5 padł na kroku, więc nie było merge do main)

INFO PreTestedMergePredicate - VCS merge is skipped for build #6 ... Reason: branch filter "+:feature/*" does not accept build branch "integration"
   (build #6 na integration: etap 1 pominięty, etap 2 wykonany: main = 84df7f3)
```

### 2.4 Cloud profile i agent pool — to, czego DSL nie opisuje

`kubernetesCloudProfile` + `kubernetesCloudImage` (wersja z pliku `settings.kts`) skompilowały się
(`BUILD SUCCESS`) i wygenerowały `CloudProfile`/`CloudImage` w `project-config.xml`
(`generated-sample/`). Te same obiekty dodane przez REST (`rest/06`, `rest/07`) wróciły w Show DSL
jako identyczna składnia — z jedną różnicą: serwer przepisał `id` profilu na `kube-1`.
Agent pool (`rest/08`, `rest/09`) w Show DSL nie pojawia się wcale; w `CloudImage` jest tylko
`agentPoolId` (liczba).

---

## Co NIE zostało zweryfikowane

- Cloud profile nie połączył się z żadnym klastrem Kubernetes (adres `.invalid`), nie uruchomił żadnego poda.
- Skrypt `tc_live.py` po usunięciu wartości domyślnej hasła (zmienna `TC_ADMIN_PASSWORD`) sprawdzono tylko kompilacją składni.
- Brak powtórzenia całej sesji od zera na ostatecznych plikach `rest/` (zob. uwaga w 1.2).
- Merge na GitHubie/GitLabie (tu lokalne repo `file://`), polityka `FAST_FORWARD` z konfliktem, konflikt merge.
- Pusty `commitMessage` sprawdzony jedną próbą (build #8, wyzwolony triggerem; kontrola #9, wyzwolona ręcznie, z tekstem — zadziałała).
- `mergeCondition = successful` na etapie 2 i `AFTER_BUILD_FINISH` vs `BEFORE_BUILD_FINISH` — zachowanie nie porównywane.

## Sprzątanie po sesji

Usunięto: kontenery `tc-p13`, `tc-p13-agent`, obraz `jetbrains/teamcity-agent:2025.07` (pobrany przeze
mnie), katalogi `/tmp/tc-p13-*` oraz 14 anonimowych wolumenów Dockera zostawionych przez
`docker rm -f` (bez `-v`) — wybrane po czasie utworzenia zgodnym z momentem startu moich kontenerów
(dwa starty serwera + agent). Uwaga na przyszłość: używaj `docker rm -fv`. NIE usunięto obrazów `jetbrains/teamcity-server:2025.07` i
`maven:3.9-eclipse-temurin-21` — były na maszynie przed sesją.
