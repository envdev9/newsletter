# Kod do wydania #15 — TeamCity: łańcuch buildów z `sequential { }` / `parallel { }`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> `sequential { }` i `parallel { }` to makra Kotlin DSL, które generują zależności snapshot (Show DSL żywego
> serwera zwraca je jako zwykłe `snapshot(...)`). Zmierzone na serwerze TeamCity 2025.07 z dwoma agentami:
> `parallel` oznacza tylko brak zależności (z jednym agentem `Test` i `Lint` biegną po kolei); `reuseBuilds = NO`
> wymusza nowe `Test`/`Lint`, a `Compile` zostaje użyty ponownie; `FAIL_TO_START` daje build `failedToStart`;
> `IGNORE` pozwala etapowi biec po nieudanym poprzedniku; a domyślna reakcja `sequential` (`RUN_ADD_PROBLEM`)
> uruchamia etap po padniętym poprzedniku i kończy go FAILURE. Show DSL pokazuje ją jako pusty blok `{ }`.

## Struktura

```
code/
├── .teamcity/
│   ├── settings.kts       # DSL: sequential + parallel + options (to wczytuje serwer i kompiluje Maven)
│   └── pom.xml            # pom do LOKALNEJ kompilacji (wzorzec z #13); w repo serwera zostaje pom wygenerowany przez serwer
├── scripts/tc_live.py     # kreator pierwszego startu (RSA), REST, builds (tabela), getj, show-dsl, poll
├── rest/                  # dosłowne ciała żądań REST (kolejność = numer)
├── generated-sample/      # XML z realnego BUILD SUCCESS (Package, Summary, Test)
└── show-dsl-sample/       # Kotlin zwrócony przez serwer (Show DSL) po wczytaniu settings.kts
```

Wymagania: Docker, Python 3, obrazy `jetbrains/teamcity-server:2025.07` (~4 GB), `jetbrains/teamcity-agent:2025.07`,
`maven:3.9-eclipse-temurin-21`. Czas: ok. 30 minut. Hasło admina efemerycznego serwera wymyśl sam i zapisz w pliku
poza repo (`TC_ADMIN_PASSWORD` albo `TC_ADMIN_PASSWORD_FILE`; domyślna ścieżka jest w nagłówku `tc_live.py`).

## 1. Kompilacja DSL (bez serwera nie zadziała: pom bierze pluginowe jary z jego repo)

Serwer musi stać pod `localhost:8111` (kroki 2.1–2.2). Kompiluj kopię katalogu, bo kontener działa jako root i
zostawi w `target/` pliki roota.

```bash
docker run --rm --network host -v "$PWD/.teamcity":/work -w /work maven:3.9-eclipse-temurin-21 mvn -B -ntp compile
```

Wynik (prawdziwy, ostatnia wersja pliku, cache Mavena ciepły):

```
[INFO] --- teamcity-configs:2025.07:generate (generate-teamcity-config) @ build-chain-dsl ---
[INFO] Generate TeamCity configs in /work/target/generated-configs, format kotlin, dslDir: /work
[INFO] BUILD SUCCESS
[INFO] Total time:  01:06 min
```

(pierwszy przebieg z zimnym cache: 3 min 25 s). Wynik w `target/generated-configs/` — zob. `generated-sample/`:
`Package` z `FAIL_TO_START` i `reuseBuilds = NO` nie ma żadnych `<option>` (to wartości domyślne XML),
a `Test` i `Summary` mają `run-build-if-dependency-failed` = `RUN_ADD_PROBLEM` / `RUN`.

## 2. Odtworzenie na żywym serwerze

### 2.1 Serwer, agenty

```bash
docker run -d --name tc-p15 -p 8111:8111 jetbrains/teamcity-server:2025.07
python3 scripts/tc_live.py wizard
docker run -d --name tc-p15-agent  --network host -e SERVER_URL=http://localhost:8111 -e AGENT_NAME=agent1 jetbrains/teamcity-agent:2025.07
docker run -d --name tc-p15-agent2 --network host -e SERVER_URL=http://localhost:8111 -e AGENT_NAME=agent2 -e AGENT_OWN_PORT=9091 jetbrains/teamcity-agent:2025.07
```

Agent po pierwszym połączeniu aktualizuje się (ok. minuta). Potem autoryzacja:

```bash
python3 scripts/tc_live.py rest PUT /app/rest/agents/id:1/authorized rest/04-true.txt text/plain
python3 scripts/tc_live.py rest PUT /app/rest/agents/id:2/authorized rest/04-true.txt text/plain
```

Drugi agent (`agent2`) był użyty dopiero od drugiego uruchomienia (do pomiaru równoległości); pierwszy przebieg
łańcucha szedł na jednym agencie. `AGENT_OWN_PORT` ustawiłem na wszelki wypadek (obie instancje dzielą sieć hosta);
nie sprawdzałem, czy bez niego agent2 też by się połączył.

### 2.2 Repo ustawień i projekt

Repo ustawień leży w kontenerze serwera w `/tmp` (zapis jako użytkownik serwera; w tym środowisku `docker exec -u 0`
był odrzucony, więc nie użyłem `/srv` jak w #14):

```bash
docker exec tc-p15 git init --bare -b main /tmp/settings.git
docker exec tc-p15 git clone /tmp/settings.git /tmp/w
docker exec -w /tmp/w tc-p15 git -c user.name=dev -c user.email=dev@example.invalid commit --allow-empty -m init
docker exec -w /tmp/w tc-p15 git push origin main
python3 scripts/tc_live.py rest POST /app/rest/projects  rest/01-project.xml
python3 scripts/tc_live.py rest POST /app/rest/vcs-roots rest/02-vcsroot.xml
python3 scripts/tc_live.py rest PUT  /app/rest/projects/id:ChainDemo/versionedSettings/config rest/03-versioned-settings-enable.json application/json
```

Po ok. minucie serwer sam zacommitował `.teamcity/settings.kts` (pusty `project { }`) i `pom.xml`. Wtedy:

```bash
docker exec -w /tmp/w tc-p15 git pull origin main
docker cp .teamcity/settings.kts tc-p15:/tmp/w/.teamcity/settings.kts
docker exec -w /tmp/w tc-p15 git -c user.name=dev -c user.email=dev@example.invalid commit -am "chain"
docker exec -w /tmp/w tc-p15 git push origin main
python3 scripts/tc_live.py poll /app/rest/projects/id:ChainDemo/buildTypes ChainDemo_Summary 400
```

Zmierzone: `po 41 s: 200 {"count":5,"buildType":[...` — pięć build type'ów wczytanych z repo.
Zależności z REST: `GET .../buildTypes/id:ChainDemo_Package/snapshot-dependencies` pokazuje
`run-build-if-dependency-failed = MAKE_FAILED_TO_START` i `take-started-build-with-same-revisions = false` (czyli
FAIL_TO_START i `ReuseBuilds.NO`), a `ChainDemo_Summary` → `RUN` (IGNORE).

### 2.3 Eksperymenty

```bash
python3 scripts/tc_live.py rest POST /app/rest/buildQueue rest/05-queue-summary.xml      # cały łańcuch
python3 scripts/tc_live.py rest POST /app/rest/buildQueue rest/05-queue-summary.xml      # drugi raz: ponowne użycie
python3 scripts/tc_live.py rest POST /app/rest/buildQueue rest/06-queue-package.xml      # reuseBuilds = NO
docker exec tc-p15-agent  touch /tmp/fail-lint
docker exec tc-p15-agent2 touch /tmp/fail-lint
python3 scripts/tc_live.py rest POST /app/rest/buildQueue rest/06-queue-package.xml      # Lint pada, Package failedToStart
python3 scripts/tc_live.py rest POST /app/rest/buildQueue rest/07-queue-summary-on-failed-package.xml   # IGNORE
python3 scripts/tc_live.py builds
```

Dla ostatniego eksperymentu (domyślna reakcja na padnięty poprzednik) zmieniłem komendę `Compile` na
`echo compiling && test ! -f /tmp/fail-compile` (v2 w repo, ta wersja jest w `settings.kts`), po czym:

```bash
docker exec tc-p15-agent  touch /tmp/fail-compile
docker exec tc-p15-agent2 touch /tmp/fail-compile
python3 scripts/tc_live.py rest POST /app/rest/buildQueue rest/08-queue-compile.xml
python3 scripts/tc_live.py rest POST /app/rest/buildQueue rest/09-queue-test-on-failed-compile.xml
```

`rest/07` i `rest/09` wskazują jawnie `<snapshot-dependencies><build id="..."/>` — numery buildów (18 i 24) pochodzą
z mojej sesji, w Twojej będą inne.

## 3. Dosłowne wyniki (`tc_live.py builds`, czas serwera UTC)

```
1 ChainDemo_Compile #1 finished SUCCESS | Success | 20261008T012653+0000 20261008T012701+0000
2 ChainDemo_Test #1 finished SUCCESS | Success | 20261008T012712+0000 20261008T012721+0000
3 ChainDemo_Lint #1 finished SUCCESS | Success | 20261008T012701+0000 20261008T012711+0000
4 ChainDemo_Package #1 finished SUCCESS | Success | 20261008T012722+0000 20261008T012726+0000
5 ChainDemo_Summary #1 finished SUCCESS | Success | 20261008T012727+0000 20261008T012731+0000
10 ChainDemo_Summary #2 finished SUCCESS | Success | 20261008T012803+0000 20261008T012807+0000
12 ChainDemo_Test #2 finished SUCCESS | Success | 20261008T012908+0000 20261008T012918+0000
13 ChainDemo_Lint #2 finished SUCCESS | Success | 20261008T012908+0000 20261008T012921+0000
14 ChainDemo_Package #2 finished SUCCESS | Success | 20261008T012921+0000 20261008T012926+0000
16 ChainDemo_Test #3 finished SUCCESS | Success | 20261008T012944+0000 20261008T012954+0000
17 ChainDemo_Lint #3 finished FAILURE | Exit code 1 (Step: Lint (Command Line)) (new) | 20261008T012944+0000 20261008T012954+0000
18 ChainDemo_Package #N/A finished FAILURE | Snapshot dependency failed: ... Lint | 20261008T012954+0000 20261008T012954+0000
23 ChainDemo_Summary #3 finished SUCCESS | Success | 20261008T013013+0000 20261008T013018+0000
24 ChainDemo_Compile #2 finished FAILURE | Exit code 1 (Step: Compile (Command Line)) (new) | 20261008T013224+0000 20261008T013229+0000
26 ChainDemo_Test #4 finished FAILURE | Snapshot dependency failed: ... Compile (new) | 20261008T013241+0000 20261008T013250+0000
```

Jak to czytać: ids 6–9 i 11, 15, 19–22, 25 to kopie w kolejce, które serwer zastąpił buildami do ponownego użycia lub usunął
(nie ma ich w historii). `Summary #2` (id 10) zależy od `Package #1` (id 4) — potwierdzone w
`GET /app/rest/builds/id:10` (`snapshot-dependencies` → build 4). `Package` id 18 ma `failedToStart: true`.
`Test #4` ma numer i trwał 9 s, czyli krok się wykonał.

## Show DSL (fragment, `show-dsl-sample/ChainDemo_Test.kt`)

```kotlin
dependencies {
    snapshot(ChainDemo_Compile) {
    }
}
```

## Co NIE zostało zweryfikowane

- Czy zwykłe `snapshot(X) { }` (poza `sequential`) ma ten sam domyślny `RUN_ADD_PROBLEM`; sprawdzone tylko to, co wygenerował `sequential`.
- Kontrola dla `Summary` bez `IGNORE` (nie uruchamiałem wersji bez opcji).
- `onDependencyCancel`, `ReuseBuilds.ANY`, `runOnSameAgent`, zależności artefaktowe, zagnieżdżone `parallel`.
- Buildy z prawdziwym VCS (synchronizacja rewizji między etapami) — etapy nie mają VCS roota.
- Powód brakujących numerów buildów w historii (ids kopii w kolejce) wnioskuję z obserwacji, nie z logu serwera.
- Skrypt `tc_live.py`: podkomenda `gett` (GET z odpowiedzią tekstową) została dopisana, ale nie była uruchomiona (żądanie logu builda było odrzucone przez system uprawnień sesji).
- Komplet kroków 2.1–2.3 od zera na finalnych plikach nie był powtórzony (sesja szła przyrostowo; `settings.kts` miał dwie wersje: v1 i v2 różniące się komendą `Compile`).

## Sprzątanie po sesji

`docker rm -fv tc-p15-agent2 tc-p15-agent tc-p15` (razem z anonimowymi wolumenami), `docker rmi jetbrains/teamcity-agent:2025.07`
(pobrany przeze mnie), katalog roboczy z hasłem i cache Mavena (pliki roota usunięte jednorazowym kontenerem Mavena z `rm -rf`).
Obrazy `jetbrains/teamcity-server:2025.07` i `maven:3.9-eclipse-temurin-21` były na maszynie przed sesją i zostały.
