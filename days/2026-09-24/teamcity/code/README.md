# Kod do wydania #1 — `.teamcity/settings.kts` (Kotlin DSL, podstawy)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + dokładnie to,
co zweryfikowano w tej sesji, komendami i prawdziwym outputem — bez podkoloryzowania.

## Fragment prasówki, którego dotyczy ten kod

> `object PrasowkaVcs : GitVcsRoot({...})` to **VCS root**, `object Build :
> BuildType({...})` to **build configuration**, `steps { script { ... } }` to lista
> **build steps**, a `triggers { vcs { } }` to **trigger** — pusty blok `vcs {}`
> oznacza "odpal przy każdym pushu do gałęzi z VCS roota". To ta sama hierarchia co
> w UI TeamCity, tylko wyrażona jako Kotlin zamiast klikania.

## Struktura

```
code/.teamcity/
├── settings.kts   # sama konfiguracja projektu (VCS root, build configuration,
│                  # build step, trigger) — to jest plik, który realny TeamCity
│                  # Server czyta z repo przy Versioned Settings
├── pom.xml        # projekt Maven WYŁĄCZNIE do offline weryfikacji settings.kts
│                  # (nie jest częścią samego configu, to nasze narzędzie do
│                  # sprawdzenia, że się kompiluje)
└── .gitignore     # ignoruje target/ (artefakty builda Mavena)
```

## Mechanizm weryfikacji (bez żywego serwera TeamCity)

TeamCity oficjalnie udostępnia wtyczkę Maven
`org.jetbrains.teamcity:teamcity-configs-maven-plugin`, spiętą z zależnością
`org.jetbrains.teamcity:configs-dsl-kotlin-latest` — to dokładnie ten sam silnik,
który prawdziwy serwer TeamCity uruchamia przy każdym pushu do repo z
`.teamcity/`. `mvn compile` w katalogu `.teamcity/` ładuje `settings.kts` przez ten
silnik i próbuje zbudować z niego model projektu. To nasz odpowiednik
`dotnet build` dla tej rubryki — realna, a nie deklarowana, weryfikacja kompilacji.

## Co dokładnie zrobiłem w tej sesji (komendy + prawdziwy output)

### 0. Punkt startowy

Katalog `.teamcity/` zawierał już `settings.kts` i `pom.xml` z wcześniejszej,
przerwanej przez limit API sesji. Oceniłem oba pliki jako poprawnie zbudowane
(zgodne z prawdziwą strukturą TeamCity Kotlin DSL i prawdziwym mechanizmem
weryfikacji Maven) i użyłem ich bez zmian jako punktu startowego. Był tam też
katalog `target/` z **pustym** `inputFiles.lst` (ślad po przerwanym, niedokończonym
uruchomieniu) — usunąłem go, bo nie odzwierciedlał żadnego realnego wyniku
kompilacji z tej sesji.

### 1. Sprawdzenie środowiska

```bash
which mvn
# (brak wyjścia - mvn nie jest zainstalowany)

apt-get install -y maven
# E: Could not open lock file /var/lib/dpkg/lock-frontend - open (13: Permission denied)
# E: Unable to acquire the dpkg frontend lock (/var/lib/dpkg/lock-frontend), are you root?

sudo -n apt-get install -y maven
# sudo: a password is required

df -h /
# Filesystem     Size  Used Avail Use% Mounted on
# .../pve-vm      40G   37G  231M 100% /
```

Brak roota (sudo wymaga hasła) i prawie pełny dysk (231 MB wolnego na 40 GB) — oba
ograniczenia zgłoszone z góry w zadaniu, potwierdzone tutaj realnie.

### 2. Instalacja Maven bez roota (przenośna binarka do `/tmp`)

```bash
mkdir -p /tmp/mvn-install && cd /tmp/mvn-install
curl -sL -o maven.tar.gz \
  https://archive.apache.org/dist/maven/maven-3/3.9.9/binaries/apache-maven-3.9.9-bin.tar.gz
tar xzf maven.tar.gz && rm maven.tar.gz
# apache-maven-3.9.9/ -> 11 MB, disk: 231M -> 221M wolnego
```

(Pierwsza próba, z `dlcdn.apache.org`, zwróciła `404 Not Found` — ten mirror nie
miał już tej wersji. Zadziałał `archive.apache.org`.)

### 3. `mvn compile`, z lokalnym repo w `/tmp` (żeby nie zaśmiecać `~/.m2`)

```bash
export PATH=/tmp/mvn-install/apache-maven-3.9.9/bin:$PATH
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
cd ~/newsletter/days/2026-09-24/teamcity/code/.teamcity
mvn -Dmaven.repo.local=/tmp/m2repo compile
```

`mvn -v` na tej maszynie:

```
Apache Maven 3.9.9 (8e8579a9e76f7d015ee5ec7bfcdc97d260186937)
Maven home: /tmp/mvn-install/apache-maven-3.9.9
Java version: 17.0.19, vendor: Ubuntu, runtime: /usr/lib/jvm/java-17-openjdk-amd64
OS name: "linux", version: "6.8.12-33-pve", arch: "amd64", family: "unix"
```

Uruchomienie pobrało realnie **227 zależności JAR (~211 MB)** z
`download.jetbrains.com/teamcity-repository` i Maven Central — m.in.
`configs-dsl-kotlin-latest-2026.3-dsl6.jar`,
`teamcity-configs-maven-plugin-2026.3-dsl6.jar`, `kotlin-compiler-2.0.21.jar`,
`kotlin-stdlib`, `kotlin-reflect`, oraz duży zestaw prawdziwych klas serwera
TeamCity (`server-vcs-impl`, `versionedSettings`, `pipelines-server`, ...) — co
samo w sobie potwierdza, że współrzędne w `pom.xml` są poprawne i realnie
rozwiązywalne, nie zmyślone.

Wolne miejsce na dysku w trakcie tego pobierania spadło z **~198 MB do 596 KB**
(monitorowane co 5 s) — ekstremalnie ciasno, ale proces **zakończył się sam**,
zanim faktycznie zabrakło miejsca na kolejny zapis.

### 4. Prawdziwy wynik: `BUILD FAILURE`

```
[INFO] --- compiler:3.13.0:compile (default-compile) @ settings-dsl-verification ---
[INFO] No sources to compile
[INFO]
[INFO] --- teamcity-configs:2026.3-dsl6:generate (generate-teamcity-config) @ settings-dsl-verification ---
...
[INFO] ------------------------------------------------------------------------
[INFO] BUILD FAILURE
[INFO] ------------------------------------------------------------------------
[INFO] Total time:  29.124 s
[INFO] Finished at: 2026-09-25T06:36:36Z
[INFO] ------------------------------------------------------------------------
[ERROR] Failed to execute goal org.jetbrains.teamcity:teamcity-configs-maven-plugin:2026.3-dsl6:generate
(generate-teamcity-config) on project settings-dsl-verification: Execution generate-teamcity-config
of goal org.jetbrains.teamcity:teamcity-configs-maven-plugin:2026.3-dsl6:generate failed: An API
incompatibility was encountered while executing
org.jetbrains.teamcity:teamcity-configs-maven-plugin:2026.3-dsl6:generate:
java.lang.UnsupportedClassVersionError: jetbrains/buildServer/serverSide/impl/versionedSettings/VersionedSettingsException
has been compiled by a more recent version of the Java Runtime (class file version 65.0), this
version of the Java Runtime only recognizes class file versions up to 61.0
[ERROR] -----------------------------------------------------
[ERROR] realm =    plugin>org.jetbrains.teamcity:teamcity-configs-maven-plugin:2026.3-dsl6
[ERROR] strategy = org.codehaus.plexus.classworlds.strategy.SelfFirstStrategy
[ERROR] urls[0] = file:/tmp/m2repo/org/jetbrains/teamcity/teamcity-configs-maven-plugin/2026.3-dsl6/teamcity-configs-maven-plugin-2026.3-dsl6.jar
```

**Diagnoza**: class file version 65.0 = Java 21, wersja 61.0 = Java 17. Wtyczka
`teamcity-configs-maven-plugin:2026.3-dsl6` wymaga JDK 21 do uruchomienia. Na tej
maszynie jest zainstalowany tylko JDK 17:

```bash
ls /usr/lib/jvm/
# java-1.17.0-openjdk-amd64  java-17-openjdk-amd64  openjdk-17
update-alternatives --list java
# /usr/lib/jvm/java-17-openjdk-amd64/bin/java
```

Zainstalowanie JDK 21 wymagałoby `sudo` (niedostępny bez hasła) i dodatkowych
dziesiątek MB na dysku, którego praktycznie nie ma — więc **zatrzymałem się tutaj**.
To realne, potwierdzone ograniczenie środowiska, nie domysł.

### 5. Sprzątanie (natychmiast po błędzie)

```bash
du -sh /tmp/m2repo /tmp/mvn-install
# 211M  /tmp/m2repo
# 11M   /tmp/mvn-install
rm -rf /tmp/m2repo /tmp/mvn-install
df -h /
# Avail: 222M — z powrotem zbliżone do stanu sprzed weryfikacji (231M)
```

Usunięte zostały wyłącznie pliki utworzone w tej sesji, w `/tmp` — żaden inny
projekt na tej maszynie nie został ruszony.

## Co to oznacza dla czytelnika, który ma JDK 21 i trochę wolnego dysku

Ten sam `pom.xml` i `settings.kts` powinny dać się uruchomić do końca (`mvn compile`
→ `BUILD SUCCESS` albo prawdziwy błąd składni w `settings.kts`, jeśli taki tam jest)
na maszynie z:

- JDK 21 (`sdk install java 21-tem` albo `apt-get install openjdk-21-jdk`),
- ok. 300–400 MB wolnego miejsca na dysk (na zależności, patrz sekcja 3 powyżej).

Komenda jest identyczna:

```bash
cd .teamcity
mvn compile
```

Ta prasówka **nie zmyśla**, że to zadziałało — bo tego nie sprawdziliśmy do końca.
Zweryfikowaliśmy realnie tyle, ile pozwoliło środowisko, i opisaliśmy dokładnie,
gdzie i dlaczego weryfikacja się zatrzymała.
