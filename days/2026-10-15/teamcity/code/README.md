# Kod do wydania #22 — TeamCity: zależności artefaktowe w łańcuchu (`artifacts { }` + `buildRule`)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> `snapshot(X)` ustala kolejność i rewizję, `artifacts(X)` wybiera build, z którego idą pliki, i robi to
> niezależnie. Zmierzone na TeamCity 2025.07: przy buildzie przypiętym do `Compile #1` zależność
> z `sameChainOrLastFinished()` pobrała artefakt z `#1`, a z `lastSuccessful()` z `#2`. Przy padniętym `Compile`
> zwykły `snapshot(X) { }` (domyślnie `RUN_ADD_PROBLEM`) uruchomił krok i przeczytał artefakt sprzed padu;
> `FAIL_TO_START` w ogóle nie uruchomił kroku.

## Struktura

```
code/
├── .teamcity/settings.kts          # Compile (artifactRules) + Test + TestLast (artifacts z dwoma buildRule)
├── .teamcity/pom.xml               # pom do LOKALNEJ kompilacji (wzorzec z #13/#15)
├── tc_live.py                      # kreator pierwszego startu (RSA), REST, builds, getj, poll (kopia z #15)
├── rest/                           # dosłowne ciała żądań REST (kolejność = numer)
├── generated-sample-Test.xml       # XML z realnego BUILD SUCCESS (wersja v1 settings.kts)
└── generated-sample-Compile.xml
```

Wymagania: Docker, Python 3, obrazy `jetbrains/teamcity-server:2025.07` (~4 GB), `jetbrains/teamcity-agent:2025.07`,
`maven:3.9-eclipse-temurin-21`. Czas: ok. 30 minut. Hasło admina efemerycznego serwera wymyśl sam i zapisz w pliku
`work/password.txt` obok `tc_live.py` (jest w `.gitignore`; albo `TC_ADMIN_PASSWORD` / `TC_ADMIN_PASSWORD_FILE`).

## 1. Serwer i agent

```bash
docker run -d --name tc-p22 -p 8111:8111 jetbrains/teamcity-server:2025.07
python3 tc_live.py wizard      # jeśli pierwsze połączenie zostanie zresetowane, serwer jeszcze startuje: powtórz
docker run -d --name tc-p22-agent --network host -e SERVER_URL=http://localhost:8111 -e AGENT_NAME=agent1 jetbrains/teamcity-agent:2025.07
```

Agent po pierwszym połączeniu aktualizuje się (ok. minuta; do tego czasu `PUT` daje 404). Autoryzacja:

```bash
python3 tc_live.py rest PUT /app/rest/agents/id:1/authorized rest/04-true.txt text/plain
```

Uwaga: plik `rest/04-true.txt` musi zawierać `true` **bez znaku nowej linii**. Z newline serwer zwraca `200 false`
i agent zostaje nieautoryzowany.

## 2. Kompilacja DSL (serwer musi stać pod `localhost:8111`)

```bash
docker run --rm --user 1001:1001 --network host -v "$PWD/.teamcity":/work -w /work maven:3.9-eclipse-temurin-21 mvn -B -ntp -Dmaven.repo.local=/tmp/m2 compile
```

(`--user` ustaw na swój uid, żeby `target/` nie należał do roota.) Wynik (prawdziwy, wersja v1 pliku, zimny cache):

```
[INFO] --- teamcity-configs:2025.07:generate (generate-teamcity-config) @ artifact-deps-dsl ---
[INFO] Generate TeamCity configs in /work/target/generated-configs, format kotlin, dslDir: /work
[INFO] BUILD SUCCESS
[INFO] Total time:  03:55 min
```

W standalone kompilacji id to `RootProjectId_*`; na serwerze projekt `ArtDemo` daje `ArtDemo_Compile` itd. —
stąd `%dep.ArtDemo_Compile.build.number%` w skrypcie.

## 3. Repo ustawień i projekt

```bash
docker exec tc-p22 git init --bare -b main /tmp/settings.git
docker exec tc-p22 git clone /tmp/settings.git /tmp/w
docker exec -w /tmp/w tc-p22 git -c user.name=dev -c user.email=dev@example.invalid commit --allow-empty -m init
docker exec -w /tmp/w tc-p22 git push origin main
python3 tc_live.py rest POST /app/rest/projects  rest/01-project.xml
python3 tc_live.py rest POST /app/rest/vcs-roots rest/02-vcsroot.xml
python3 tc_live.py rest PUT  /app/rest/projects/id:ArtDemo/versionedSettings/config rest/03-versioned-settings-enable.json application/json
```

Po ok. minucie serwer zacommituje `.teamcity/settings.kts` i `pom.xml`:

```bash
docker exec -w /tmp/w tc-p22 git pull origin main
docker cp .teamcity/settings.kts tc-p22:/tmp/w/.teamcity/settings.kts
docker exec -w /tmp/w tc-p22 git -c user.name=dev -c user.email=dev@example.invalid commit -am artifacts
docker exec -w /tmp/w tc-p22 git push origin main
python3 tc_live.py poll /app/rest/projects/id:ArtDemo/buildTypes ArtDemo_TestLast 400
```

Zmierzone: `po 87 s: 200 {"count":3,"buildType":[...` (trzy build type'y).

## 4. Eksperymenty

```bash
python3 tc_live.py rest POST /app/rest/buildQueue rest/06-queue-test.xml          # łańcuch Compile -> Test
python3 tc_live.py rest POST /app/rest/buildQueue rest/05-queue-compile.xml       # Compile #2
python3 tc_live.py rest POST /app/rest/buildQueue rest/08-queue-test-pinned.xml   # Test przypięty do Compile id 1
python3 tc_live.py rest POST /app/rest/buildQueue rest/09-queue-testlast-pinned.xml
docker exec tc-p22-agent touch /tmp/fail-compile
python3 tc_live.py rest POST /app/rest/buildQueue rest/05-queue-compile.xml       # Compile pada
python3 tc_live.py rest POST /app/rest/buildQueue rest/07-queue-testlast.xml
python3 tc_live.py rest POST /app/rest/buildQueue rest/06-queue-test.xml
python3 tc_live.py builds
```

`rest/08` i `rest/09` wskazują `<build id="1"/>` — to id mojego `Compile #1`; w Twojej sesji sprawdź je w `builds`.
Log builda pobierany przez `/downloadBuildLog.html` był odrzucany przez system uprawnień sesji, dlatego kroki
wypisują wynik przez `##teamcity[buildStatus ...]` (widoczne jako `statusText` w REST).

## 5. Dosłowne wyniki (`tc_live.py builds`, czas serwera UTC)

```
1 ArtDemo_Compile #1 finished SUCCESS | Success | 20261015T012835+0000 20261015T012845+0000
2 ArtDemo_Test #1 finished SUCCESS | Success | 20261015T012846+0000 20261015T012851+0000
4 ArtDemo_Test #2 finished SUCCESS | Test #2, snapshot Compile #1, artefakt: compiled by Compile #1 (build id 1) | 20261015T013009+0000 20261015T013014+0000
5 ArtDemo_Compile #2 finished SUCCESS | Success | 20261015T013023+0000 20261015T013029+0000
7 ArtDemo_Test #3 finished SUCCESS | Test #3, snapshot Compile #1, artefakt: compiled by Compile #1 (build id 1) | 20261015T013033+0000 20261015T013038+0000
9 ArtDemo_TestLast #1 finished SUCCESS | TestLast #1, snapshot Compile #1, artefakt: compiled by Compile #2 (build id 5) | 20261015T013038+0000 20261015T013043+0000
11 ArtDemo_TestLast #2 finished SUCCESS | TestLast #2, snapshot Compile #2, artefakt: compiled by Compile #2 (build id 5) | 20261015T013050+0000 20261015T013054+0000
13 ArtDemo_Test #4 finished SUCCESS | Test #4, snapshot Compile #2, artefakt: compiled by Compile #2 (build id 5) | 20261015T013054+0000 20261015T013059+0000
14 ArtDemo_Compile #3 finished SUCCESS | Success | 20261015T013110+0000 20261015T013115+0000
15 ArtDemo_Compile #4 finished FAILURE | Exit code 1 (Step: Compile (Command Line)) (new) | 20261015T013229+0000 20261015T013234+0000
16 ArtDemo_Compile #5 finished FAILURE | Exit code 1 (Step: Compile (Command Line)) | 20261015T013240+0000 20261015T013245+0000
17 ArtDemo_TestLast #3 finished FAILURE | TestLast #3, snapshot Compile #5, artefakt: compiled by Compile #3 (build id 14) | 20261015T013245+0000 20261015T013249+0000
18 ArtDemo_Compile #6 finished FAILURE | Exit code 1 (Step: Compile (Command Line)) | 20261015T013249+0000 20261015T013255+0000
19 ArtDemo_Test #N/A finished FAILURE | Snapshot dependency failed: ... Compile | 20261015T013255+0000 20261015T013255+0000
```

Jak czytać: `Compile #3` (id 14) powstał, gdy blokady `/tmp/fail-compile` jeszcze nie było w działającej wersji skryptu —
pierwsza wersja kroku nie miała `set -e`, więc plik-blokada nie powodował padu; po dodaniu `set -e` (commit `set-e`)
`Compile #4`–`#6` padają zgodnie z oczekiwaniem. Ids bez wiersza (3, 6, 8, 10, 12) to kopie w kolejce zastąpione
buildami do ponownego użycia.

Zależności z REST żywego serwera (`TestLast`):

```
snapshot:  run-build-if-dependency-failed = RUN_ADD_PROBLEM, take-successful-builds-only = true
artifact:  pathRules = build-out/** => in, revisionName = lastSuccessful, revisionValue = latest.lastSuccessful
```

## Co NIE zostało zweryfikowane

- `mvn compile` na końcowej wersji `settings.kts` (kompilowana była v1; do końcowej doszły: `set -e`, komunikat statusu, nazwa parametru). Końcową wersję wczytał i uruchomił serwer.
- Dwa agenty, brak artefaktu (zła ścieżka), `buildNumber`/`tag`, `cleanDestination = true`, `runOnSameAgent`, artefakt bez snapshot.
- Pełny przebieg od zera na finalnych plikach (sesja szła przyrostowo).
- `generated-sample-*.xml` pochodzą z v1 (z `%dep.Compile.build.number%`, które w końcowej wersji jest poprawione).

## Sprzątanie po sesji

`docker rm -fv tc-p22-agent tc-p22`, `docker rmi jetbrains/teamcity-agent:2025.07` (pobrany przeze mnie), `target/` i
katalog `work/` z hasłem usunięte. Po sesji `docker ps -a` pokazuje tylko dwa kontenery, które istniały wcześniej.
Obrazy `jetbrains/teamcity-server:2025.07` i `maven:3.9-eclipse-temurin-21` były na maszynie przed sesją.
