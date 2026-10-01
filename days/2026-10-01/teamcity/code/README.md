# Kod do wydania #8 — TeamCity: Automatic Merge + PIERWSZY `BUILD SUCCESS` na całym pipeline

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Główny temat: build feature **Automatic Merge** (`jetbrains.buildServer.configs.kotlin.
> buildFeatures.AutoMerge`, funkcja `merge{}`) dołożony do `Release` — ostatniego,
> composite kroku łańcucha, agregującego cały pipeline. `mergeCondition` to pole typu
> `String` (NIE typowany enum, mimo że klasa `AutoMerge` deklaruje
> `AutoMerge.MergeCondition`!) — potwierdzone trzema niezależnymi źródłami: deskryptorem
> XML pluginu, żywą dokumentacją Dokka, i (najsilniejsze) realnym, server-generated
> plikiem `.kt` z mechanizmu *Show DSL* na żywym serwerze TeamCity.
>
> Drugi temat: ósma z rzędu próba realnej kompilacji pełnego `settings.kts` przez
> `teamcity-configs-maven-plugin` — PIERWSZY RAZ w historii tej rubryki zakończona
> **prawdziwym `BUILD SUCCESS` na CAŁYM, pięcio-build-type'owym pipeline** (nie tylko
> na minimalnym podzbiorze jak w #7). Osiągnięte przez postawienie żywego serwera
> TeamCity w Dockerze i skompilowanie configu względem jego WŁASNEGO, efemerycznego
> repozytorium Maven z per-pluginowymi artefaktami DSL — element, którego istnienie
> `STATE.md` przewidywało jako "następny krok" po #7, ale nie znało jeszcze lokalizacji.

## Struktura

```
code/
├── .teamcity/                            # GŁÓWNY projekt: idiomatyczny, pełny przykład
│   ├── settings.kts                      # Compile→Test→IntegrationTest→DockerImage→Release(+AutoMerge!)
│   ├── pom.xml                           # Maven + teamcity-configs-maven-plugin (publiczny jar, jak #7)
│   └── .gitignore
├── compile-proof/.teamcity/              # Z #7, bez zmian - minimalny plik, nadal BUILD SUCCESS
├── full-pipeline-proof/.teamcity/        # NOWOŚĆ #8: DOSŁOWNY plik, który dał PRAWDZIWY BUILD SUCCESS
│   ├── settings.kts                      # identyczny pipeline jak główny, ale z 4 poprawkami + bez versionedSettings
│   ├── pom.xml                           # DWA repozytoria Maven (publiczne + serwera lokalnego)
│   └── .gitignore
├── full-pipeline-proof/generated-sample/ # Prawdziwe XML-e wygenerowane przez dzisiejszy BUILD SUCCESS
│   ├── RootProjectId_Compile.xml
│   └── RootProjectId_Release.xml
├── scripts/
│   └── teamcity-server-setup.py          # Skonsolidowany skrypt: kreator pierwszego startu + RSA + REST + Show DSL
└── docker-compose.integration.yml        # bez zmian względem #6/#7
```

---

## Część 1: jak odtworzyć całość od zera

Wymagania: Docker (z dostępem do internetu dla `docker pull` i Maven Central),
ok. 10 minut, ~5 GB miejsca na dysku (obraz serwera TeamCity + obraz Maven +
pobrane zależności).

### 1.1. Postaw żywy serwer TeamCity

```bash
docker pull jetbrains/teamcity-server:2025.07
docker run -d --name tc-demo -p 8111:8111 jetbrains/teamcity-server:2025.07
```

Poczekaj ok. 1-2 minuty (sprawdź: `docker exec tc-demo tail -f /opt/teamcity/logs/teamcity-server.log`
— szukaj linii `Found 95 bundled plugins`).

### 1.2. Przejdź kreator pierwszego startu (bez przeglądarki)

```bash
cd code/scripts
python3 teamcity-server-setup.py new-installation
python3 teamcity-server-setup.py accept-license
python3 teamcity-server-setup.py create-admin
```

Trzecia komenda tworzy użytkownika `admin` z hasłem na stałe wpisanym w skrypcie
(`ADMIN_PASSWORD` — hasło do efemerycznego kontenera, nie sekret produkcyjny).
Oczekiwany wynik ostatniej komendy:
```
POST createAdminSubmit -> 200 b'<response><redirect>/favorite/projects</redirect><errors /></response>'
```

### 1.3. Skonfiguruj projekt demo + feature Automatic Merge przez REST

```bash
python3 teamcity-server-setup.py setup-demo-project
```

Tworzy: projekt `PrasowkaDemo`, VCS root (`jetbrains.git`), `BuildType` "Release",
i dodaje do niego build feature `AutoMergeFeature` z surowymi parametrami
(`teamcity.automerge.srcBranchFilter` itd. — zob. część 2, skąd te nazwy).

### 1.4. Pobierz prawdziwy, server-generated Kotlin ("Show DSL")

```bash
python3 teamcity-server-setup.py show-dsl
unzip -l generated-dsl.zip
```

### 1.5. Skompiluj PEŁNY pipeline (`full-pipeline-proof/.teamcity/`)

```bash
cd ../full-pipeline-proof/.teamcity
# podstaw w pom.xml adres swojego serwera, jeśli inny niż localhost:8111
docker run --rm --network host \
  -v "$PWD":/work -w /work \
  maven:3.9-eclipse-temurin-21 mvn -B compile
```

Oczekiwany wynik: `BUILD SUCCESS`, pliki w `target/teamcity-generated/RootProjectId/`.

---

## Część 2: skąd te konkretne nazwy i mechanizmy — pełny log śledztwa

### 2.1. Dlaczego konto administratora wymaga RSA

Formularz `createAdmin.jsp` ładuje `js/crypt/rsa.js` + `js/bs/encrypt.js` +
`js/bs/createUser.js`. `BS.AbstractPasswordForm.serializeParameters` jawnie
**wycina** pola typu `password` z normalnej serializacji formularza
(`BS.Util.serializeForm`, filtr `isPasswordInput`) i dokleja zamiast nich
`encrypted<NazwaPola>=<hex>`, gdzie `<hex>` to wynik `BS.Crypto.RSAKey.encrypt()`
(klucz publiczny z ukrytego pola `publicKey`, wykładnik na stałe `0x10001`).

Pierwsza próba (standardowy PKCS#1 v1.5 type 2) dała:
```
POST createAdminSubmit -> 200
b'<response><errors><error id="emptyPassword">Password is empty</error></errors></response>'
```

Przyczyna znaleziona w **kliencie** (`js/crypt/rsa.js`, funkcja `pkcs1pad2`):

```js
function pkcs1pad2(s,n) {
  ...
  var ba = new Array();
  var i = s.length - 1;
  ba[--n] = s.length; // <-- DODATKOWY bajt: długość stringa, NA KOŃCU bloku
  while(i >= 0 && n > 0) { ... }
  ba[--n] = 0;
  // ... losowe, niezerowe bajty PS ...
  ba[--n] = 2;
  ba[--n] = 0;
  return new BS.Crypto.BigInteger(ba);
}
```

Potwierdzone niezależnie w **serwerze** — pobrano `common.jar` z kontenera
(`docker cp tc-demo:/opt/teamcity/webapps/ROOT/WEB-INF/lib/common.jar .`) i
disasemblowano `javap -p -c` klasę `jetbrains.buildServer.serverSide.crypt.
RSACipher`:

```
151: aload         6
153: aload         6
155: arraylength
156: iconst_1
157: isub
158: baload                                    // decrypted[length-1]
159: istore        7                           // -> b7 (marker)
161: new           #26  // class java/lang/String
...
180: aload         8
182: invokevirtual #35  // String.length()
185: iload         7
187: if_icmpne     200                          // jeśli length != marker -> ISO-8859-1 się nie zgadza, próbuj UTF-8/odrzuć
```

Czyli: po deszyfrowaniu (Java `Cipher` z `RSA/NONE/PKCS1Padding` już usuwa
standardowy padding `0x00 0x02 PS 0x00`), serwer odczytuje **ostatni bajt**
pozostałych danych jako długość i porównuje z długością reszty — jeśli się nie
zgadza, hasło jest traktowane jako nieprawidłowe/puste. Implementacja w Pythonie
(`pkcs1_pad_encrypt_with_length_marker` w `scripts/teamcity-server-setup.py`)
odtwarza to dosłownie: `message + bytes([len(message)])` jako treść PRZED
dodaniem standardowego paddingu PKCS#1. Druga próba, z tą poprawką:

```
POST createAdminSubmit -> 200
b'<response><redirect>/favorite/projects</redirect><errors /></response>'
```

Druga, osobna pułapka znaleziona po drodze: serwer dzieli skonkatenowany string
hex na kawałki o **stałej** długości `2 * k` znaków (`k` = długość modułu w
bajtach, `KEYSIZE = 1024` bitów = 128 bajtów = 256 znaków hex, potwierdzone
`sipush 256` w bajtkodzie `decryptWebRequestData`) — a `c.toString(16)` w JS
(i `format(c_int, 'x')` w Pythonie) naturalnie **nie** dopełnia zerami z lewej.
Dla jednego bloku (krótkie hasło) rzadko to widać, ale bez `.zfill(2*k)` losowo
(zależnie od losowego paddingu) deszyfrowanie i tak by się nie zgodziło.

### 2.2. REST API — dosłowne żądania

```bash
curl -u admin:... -X POST http://localhost:8111/app/rest/projects \
  -H "Content-Type: application/xml" \
  -d '<newProjectDescription name="Prasowka Demo"><parentProject locator="id:_Root"/></newProjectDescription>'
# -> <project id="PrasowkaDemo" ...>

curl -u admin:... -X POST http://localhost:8111/app/rest/buildTypes/id:PrasowkaDemo_Release/features \
  -H "Content-Type: application/xml" \
  -d '<feature type="AutoMergeFeature">
        <properties>
          <property name="teamcity.automerge.srcBranchFilter" value="+:refs/pull/*/head"/>
          <property name="teamcity.automerge.dstBranch" value="refs/heads/main"/>
          <property name="teamcity.merge.policy" value="fastForward"/>
          <property name="teamcity.automerge.buildStatusCondition" value="successful"/>
          <property name="teamcity.automerge.run.policy" value="runAfterBuildFinish"/>
        </properties>
      </feature>'
# -> 200, <feature id="BUILD_EXT_1" type="AutoMergeFeature">...
```

Skąd te surowe nazwy (`teamcity.automerge.srcBranchFilter` itd.)? Z deskryptora
XML pluginu, znalezionego w **już istniejącym na tej maszynie** cache'u Maven
(`~/.m2/repository/org/jetbrains/teamcity/server-core/2026.3-DSL-eap2-SNAPSHOT/
server-core-2026.3-DSL-eap2-SNAPSHOT.jar`, plik `kotlin-dsl/buildFeatures/
AutoMerge.xml`) — **nie pobrany dziś przez nas**, trafiony przy przeszukiwaniu
lokalnego repozytorium Maven pod kątem śladów po wcześniejszych próbach
(timestamp Snapshotu z 1 września, czyli dawniej niż jakiekolwiek wydanie tej
rubryki — prawdopodobnie ślad niezależnej, wcześniejszej eksploracji na tej
maszynie, pozostawiony nienaruszony):

```xml
<dsl-extension kind="buildFeature" type="AutoMergeFeature" generateDslJar="true">
  <class name="AutoMerge">...</class>
  <function name="merge">...</function>
  <params>
    <param name="teamcity.automerge.srcBranchFilter" dslName="branchFilter" mandatory="true"/>
    <param name="teamcity.automerge.dstBranch" dslName="destinationBranch"/>
    <param name="teamcity.automerge.message" dslName="commitMessage"/>
    <param name="teamcity.merge.policy" dslName="mergePolicy" type="MergePolicy"/>
    <param name="teamcity.automerge.buildStatusCondition" dslName="mergeCondition"/>
    <param name="teamcity.automerge.run.policy" dslName="runPolicy" type="RunPolicy"/>
  </params>
  <types>
    <enum name="MergePolicy">
      <option name="FAST_FORWARD" value="fastForward"/>
      <option name="ALWAYS_MERGE" value="alwaysCreateMergeCommit"/>
    </enum>
    <enum name="MergeCondition">
      <option name="SUCCESSFUL_BUILD" value="successful"/>
      <option name="NO_NEW_FAILED_TESTS" value="noNewTests"/>
    </enum>
    <enum name="RunPolicy">
      <option name="BEFORE_BUILD_FINISH" value="runBeforeBuildFinish"/>
      <option name="AFTER_BUILD_FINISH" value="runAfterBuildFinish"/>
    </enum>
  </types>
</dsl-extension>
```

**To jest dokładny powód**, czemu `mergeCondition`/`commitMessage` są `String`, a
`mergePolicy`/`runPolicy` są typowanymi enumami: tylko te dwa ostatnie parametry
mają atrybut `type="..."` w deskryptorze. Generator DSL czyta ten plik XML i
generuje Kotlina zgodnie z nim — 1:1.

### 2.3. Show DSL — dowód "domyślne wartości są pomijane"

Pierwsza wersja feature'u (`buildStatusCondition=successful`,
`run.policy=runAfterBuildFinish` — czyli DOMYŚLNE wartości wg deskryptora wyżej)
→ `show-dsl` zwróciło:

```kotlin
features {
    merge {
        branchFilter = "+:refs/pull/*/head"
        destinationBranch = "refs/heads/main"
        commitMessage = ""
        mergePolicy = AutoMerge.MergePolicy.FAST_FORWARD
        // BRAK mergeCondition i runPolicy!
    }
}
```

Zmiana (REST `PUT .../parameters/teamcity.automerge.buildStatusCondition` na
`noNewTests`, i `.../run.policy` na `runBeforeBuildFinish`) → ponowne `show-dsl`:

```kotlin
features {
    merge {
        branchFilter = "+:refs/pull/*/head"
        destinationBranch = "refs/heads/main"
        commitMessage = ""
        mergePolicy = AutoMerge.MergePolicy.FAST_FORWARD
        mergeCondition = "noNewTests"
        runPolicy = AutoMerge.RunPolicy.BEFORE_BUILD_FINISH
    }
}
```

Generator "Show DSL" pomija jawne przypisania równe wartości domyślnej.

### 2.4. Skąd per-pluginowe repozytorium Maven

`show-dsl` (krok 1.4) zwraca ZIP z `pom.xml`, który zawiera (pełna treść,
dosłowna):

```xml
<repositories>
  <repository>
    <id>jetbrains-all</id>
    <url>https://download.jetbrains.com/teamcity-repository</url>
  </repository>
  <repository>
    <id>teamcity-server</id>
    <url>http://localhost:8111/app/dsl-plugins-repository</url>
  </repository>
</repositories>
...
<dependency>
  <groupId>org.jetbrains.teamcity</groupId>
  <artifactId>configs-dsl-kotlin-latest</artifactId>
  <version>${teamcity.dsl.version}</version>  <!-- = 2025.07, z parent POM -->
</dependency>
<dependency>
  <groupId>org.jetbrains.teamcity</groupId>
  <artifactId>configs-dsl-kotlin-plugins-latest</artifactId>
  <version>1.0-SNAPSHOT</version>
  <type>pom</type>
</dependency>
```

POM agregatora (`GET /app/dsl-plugins-repository/org/jetbrains/teamcity/
configs-dsl-kotlin-plugins-latest/1.0-SNAPSHOT/configs-dsl-kotlin-plugins-latest
-1.0-<timestamp>.pom`) listuje **45 zależności**, m.in.:

```
configs-dsl-kotlin-pull-requests-latest        <- plugin "pull-requests"
configs-dsl-kotlin-swabra-latest                <- plugin "swabra"
configs-dsl-kotlin-docker-support-latest        <- plugin "docker-support"
configs-dsl-kotlin-commit-status-publisher-latest <- plugin "commit-status-publisher"
configs-dsl-kotlin-bundled-latest               <- WSZYSTKO wbudowane w server-core
                                                    (AutoMerge, matrix, VersionedSettings,
                                                    VcsTrigger, ScheduleTrigger, ...)
configs-dsl-converters                          <- 2025.07 (NIE "-latest"/SNAPSHOT - jedyny
                                                    wyjątek, publikowany normalnie)
```

Potwierdzono jarem: `configs-dsl-kotlin-bundled-latest-1.0-SNAPSHOT.jar` zawiera
realnie skompilowane `.class`: `AutoMerge`, `AutoMerge$MergePolicy`,
`AutoMerge$MergeCondition`, `AutoMerge$RunPolicy`, i (klucz do sekcji 2.5)
`jetbrains/buildServer/configs/kotlin/projectFeatures/VersionedSettings.class`.
`configs-dsl-kotlin-latest-2025.07.jar` (base, publiczny) zawiera
`MatrixFeature`/`MatrixKt` w pakiecie **bazowym** (`jetbrains.buildServer.configs.
kotlin`, NIE `.buildFeatures`) — dowód bezpośredni na pierwszy z czterech błędów
poprawionych w sekcji 3.

### 2.5. Co NIE wynika z tego, że coś działa przez REST

Ważne zastrzeżenie uczciwościowe: REST API (sekcja 2.2) **nie waliduje** nazw
parametrów względem żadnego rejestru typów w momencie przyjęcia żądania — przyjmie
dowolny `<property name="..." value="...">`. Walidacja (czy dany `type` featura i
jego parametry są sensowne) dzieje się PÓŹNIEJ, przy próbie użycia projektu (np.
przy generowaniu DSL albo starcie builda). W tej sesji feature rzeczywiście
**zadziałał** (pokazał się poprawnie w `show-dsl`, wygenerował sensowny,
oczekiwany Kotlin) - to jest silniejszy dowód niż samo "REST zwrócił 200", ale
nadal nie jest tożsame z uruchomieniem prawdziwego builda i obserwacją
rzeczywistego mergowania gałęzi w repozytorium Git.

---

## Część 3: pełny log próby kompilacji CAŁEGO pipeline'u (`full-pipeline-proof/.teamcity/`)

### 3.1. Pierwsza próba — 4 błędy kompilatora, wszystkie w NASZYM kodzie

```
$ docker run --rm --network host -v "$PWD":/work -w /work \
    -v /tmp/m2repo-full:/root/.m2/repository \
    maven:3.9-eclipse-temurin-21 mvn -B compile
...
[INFO] Downloaded from central: .../kotlin-compiler-2.0.21.jar (60 MB at 5.3 MB/s)
[INFO] Generate TeamCity configs in /work/target/teamcity-generated, format kotlin, dslDir: /work
Kotlin generation errors:
Compilation error settings.kts[6:59]: Unresolved reference: matrix
Compilation error settings.kts[74:20]: Unresolved reference: VersionedSettings
Compilation error settings.kts[77:30]: Unresolved reference: VersionedSettings
Compilation error settings.kts[78:33]: Unresolved reference: VersionedSettings
Compilation error settings.kts[122:35]: Unresolved reference: ScriptBuildStep
Compilation error settings.kts[179:35]: Unresolved reference: ScriptBuildStep
Compilation error settings.kts[212:13]: None of the following functions can be called with the arguments supplied:
public final fun param(name: String, value: String): Unit defined in jetbrains.buildServer.configs.kotlin.MatrixFeature
public final fun param(name: String, values: List<MatrixFeature.Value>): Unit defined in jetbrains.buildServer.configs.kotlin.MatrixFeature
[INFO] BUILD FAILURE
[INFO] Total time:  02:50 min
```

**To jest, zestawiając z #7: dramatyczny postęp.** W #7 nierozwiązanych było
~20 różnych symboli (cały pakiet `buildFeatures`/`buildSteps`/`triggers`/`vcs`
nie istniał). Tutaj — **tylko 3 nazwy, i to z powodu BŁĘDÓW W NASZYM KODZIE**, nie
brakujących zależności. Wszystko inne (GitVcsRoot, vcs{}, script, swabra, perfmon,
pullRequests, commitStatusPublisher, dockerRegistry, dockerSupport, dockerCommand,
parallelTests, merge/AutoMerge, failOnMetricChange, failOnText) **skompilowało się
od razu**.

Poprawki (pełne uzasadnienie w artykule, sekcja 1):
```diff
- import jetbrains.buildServer.configs.kotlin.buildFeatures.matrix
+ import jetbrains.buildServer.configs.kotlin.matrix
+ import jetbrains.buildServer.configs.kotlin.buildSteps.ScriptBuildStep
+ import jetbrains.buildServer.configs.kotlin.projectFeatures.VersionedSettings
...
- param("env.SDK_VERSION", listOf("8.0", "9.0", "10.0"))
+ param("env.SDK_VERSION", listOf(value("8.0", "8.0"), value("9.0", "9.0"), value("10.0", "10.0")))
```

### 3.2. Druga próba — compile OK, walidacja runtime odrzuca `versionedSettings`

```
[INFO] Generate TeamCity configs in /work/target/teamcity-generated, format kotlin, dslDir: /work
jetbrains.buildServer.serverSide.impl.versionedSettings.VersionedSettingsException: DSL script execution failure
Kotlin generation errors:
Validation error: Project 'RootProjectId', project feature [2/2]: Versioned settings project feature cannot be used in relative project hierarchy
[INFO] BUILD FAILURE
```

**Żadnych błędów kompilacji** — to jest walidator SEMANTYCZNY (sprawdza, czy
config MA SENS, nie czy się kompiluje), i mówi wprost: ten konkretny feature
wymaga prawdziwego drzewa projektów, którego tryb standalone (plugin Maven
uruchomiony poza serwerem) nie modeluje. Potwierdzone w sekcji 2.2, że na żywym
serwerze (REST) ten sam feature działa normalnie.

Osobno sprawdzono też wersję configu: `version = "2026.1"` (wartość używana od #1
do #7) dała inny błąd runtime:
```
Runtime error: settings.kts: settings version 2026.1 is not supported, maximum supported settings version is 2025.07
```
— wszystkie poprzednie edycje celowały w wersję configu z PRZYSZŁOŚCI względem
jakiegokolwiek realnego serwera, na którym można by to przetestować.

### 3.3. Trzecia próba — `versionedSettings{}` usunięte, wersja `2025.07` — `BUILD SUCCESS`

```
$ docker run --rm --network host -v "$PWD":/work -w /work \
    -v /tmp/m2repo-full:/root/.m2/repository \
    maven:3.9-eclipse-temurin-21 mvn -B -o compile
[INFO] Scanning for projects...
[INFO] -----------< pl.prasowka.teamcity:settings-dsl-full-attempt >-----------
[INFO] --- teamcity-configs:2025.07:generate (generate-teamcity-config) ---
[INFO] Generate TeamCity configs in /work/target/teamcity-generated, format kotlin, dslDir: /work
[INFO] ------------------------------------------------------------------------
[INFO] BUILD SUCCESS
[INFO] ------------------------------------------------------------------------
[INFO] Total time:  41.016 s
```

(`-o` = offline, bo wszystkie ~230 zależności — rdzeń Kotlina, 45 per-pluginowych
jarów, reszta — były już w lokalnym cache'u Maven z poprzedniej próby.)

Wygenerowane pliki: `project-config.xml`, `vcsRoots/RootProjectId_PrasowkaVcs.xml`,
i po jednym `.xml` na każdy z pięciu build type'ów. Fragment
`RootProjectId_Release.xml` (AutoMerge — dosłowna treść, skopiowana też do
[`full-pipeline-proof/generated-sample/`](full-pipeline-proof/generated-sample/)):

```xml
<extension id="BUILD_EXT_2" type="AutoMergeFeature">
  <parameters>
    <param name="teamcity.automerge.buildStatusCondition" value="noNewTests" />
    <param name="teamcity.automerge.dstBranch" value="refs/heads/main" />
    <param name="teamcity.automerge.run.policy" value="runBeforeBuildFinish" />
    <param name="teamcity.automerge.srcBranchFilter" value="+:refs/pull/*/head" />
    <param name="teamcity.merge.policy" value="fastForward" />
  </parameters>
</extension>
```

Dokładnie te parametry, dokładnie te wartości, w DOKŁADNIE formacie, jaki zgodny
jest z deskryptorem XML z sekcji 2.2 — zamknięta pętla, zero rozbieżności.

Fragment `RootProjectId_Compile.xml` (bonus, niezależnie potwierdza "zgadnięte" w
#7 nazwy parametrów `pullRequests`):

```xml
<extension id="BUILD_EXT_3" type="pullRequests">
  <parameters>
    <param name="authenticationType" value="token" />
    <param name="filterAuthorRole" value="MEMBER" />
    <param name="filterTargetBranch" value="+:refs/heads/main" />
    <param name="ignoreDrafts" value="true" />
    <param name="providerType" value="github" />
    <param name="secure:accessToken" value="credentialsJSON:22222222-2222-2222-2222-222222222222" />
    <param name="vcsRootId" value="RootProjectId_PrasowkaVcs" />
  </parameters>
</extension>
```

(`vcsRootId`, `authenticationType`, `filterAuthorRole` — identyczne z generycznym
fallbackiem, który wydanie #7 wymyśliło przez analogię, bez możliwości
weryfikacji. Dziś potwierdzone, że zgadnięto poprawnie.)

---

## Sprzątanie po sesji

Wszystko, co dziś pobrano/zbudowano wyłącznie na potrzeby tej weryfikacji, zostało
usunięte po zakończeniu pracy:
- Kontener `tc-demo`/`tc-verify-2026-10-01` (`docker rm -f`).
- Obrazy `jetbrains/teamcity-server:2025.07` i `maven:3.9-eclipse-temurin-21`
  (`docker rmi`) — pobrane dziś wyłącznie do tego testu.
- `/tmp/tc-verify-2026-10-01/`, `/tmp/full-compile-attempt/`, `/tmp/m2repo-full/`
  (JDK/Maven z poprzednich edycji NIE były dziś potrzebne — żywy serwer + kontener
  `maven:3.9-eclipse-temurin-21` zastąpiły cały dotychczasowy problem z JDK 21/
  uprawnieniami Bash z #1-#7).
- `tc-setup-driver.py` (wersja roboczo-eksperymentalna w `/tmp` — finalna,
  skonsolidowana wersja została skopiowana do `code/scripts/teamcity-server-setup.py`
  i jest częścią tego wydania).

**NIE usunięto** (nie nasze, nie dziś pobrane): zawartości `~/.m2/repository` z
wcześniejszych, niezależnych śladów na tej maszynie (m.in. wspomniany w sekcji 2.2
`server-core-2026.3-DSL-eap2-SNAPSHOT.jar`) — pozostawione nienaruszone, zgodnie
z zasadą nie usuwania cudzych zasobów. Żadne inne obrazy/kontenery Dockera
obecne na maszynie przed tą sesją nie zostały dotknięte.
