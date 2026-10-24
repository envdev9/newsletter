# Kod do wydania #14 — TeamCity: versioned settings w pełnej pętli (serwer ↔ repo Git)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Versioned settings to nie "eksport konfiguracji do Gita", tylko pętla w obie strony. Zmierzone na żywym
> serwerze TeamCity 2025.07 z lokalnym repo `file://`: (1) włączenie synchronizacji w formacie Kotlin kończy się
> commitem serwera z `.teamcity/settings.kts` i `pom.xml`; (2) push dewelopera z nowym build type pojawia się na
> serwerze po ok. 1,5 minuty; (3) zmiana przez REST/UI NIE edytuje `settings.kts`, tylko dokłada plik-łatkę
> `.teamcity/patches/buildTypes/Hello.kts` z blokiem `expectSteps`; (4) gdy deweloper zmieni ten sam krok w
> `settings.kts`, łatka przestaje pasować i serwer odmawia przyjęcia rewizji, zostając przy ostatniej dobrej
> konfiguracji; (5) literówka w DSL daje `Compilation error` z numerem linii w `/versionedSettings/status`.

## Struktura

```
code/
├── scripts/tc_live.py      # kreator pierwszego startu (RSA) + dowolny REST + show-dsl + poll
├── rest/                   # dosłowne ciała żądań REST użyte w sesji (kolejność = numer)
└── loop/                   # kolejne wersje settings.kts (v1 z serwera, v2..v5 z pushy) + łatka serwera
```

Wymagania: Docker, Python 3, obraz `jetbrains/teamcity-server:2025.07` (~4 GB). Agent NIE jest potrzebny
(żaden build się tu nie wykonuje). Czas: ok. 25 minut, z czego większość to oczekiwanie na kompilację DSL
po stronie serwera (30–65 s przy każdej zmianie).

## Odtworzenie krok po kroku

Hasło admina efemerycznego serwera wymyśl sam i zapisz w pliku poza repo (skrypt czyta
`TC_ADMIN_PASSWORD` albo plik z `TC_ADMIN_PASSWORD_FILE`; domyślna ścieżka pliku jest w nagłówku `tc_live.py`).

```bash
# 1. Serwer + kreator (jeden proces, bo sesja HTTP musi przetrwać cały kreator)
docker run -d --name tc-p14 -p 8111:8111 jetbrains/teamcity-server:2025.07
python3 scripts/tc_live.py wizard

# 2. Repo na ustawienia — W KONTENERZE SERWERA (to serwer musi mieć prawo pushu)
docker exec -u 0 tc-p14 mkdir -p /srv
docker exec -u 0 tc-p14 git init --bare -b main /srv/settings.git
docker exec -u 0 tc-p14 git config --system --add safe.directory '*'
docker exec -u 0 tc-p14 chown -R tcuser /srv/settings.git
# jeden pusty commit "init" (puste repo bez gałęzi to zła baza):
docker exec tc-p14 git clone /srv/settings.git /tmp/w
docker exec -w /tmp/w tc-p14 git -c user.name=dev -c user.email=dev@example.invalid commit --allow-empty -m init
docker exec -w /tmp/w tc-p14 git push origin main

# 3. Projekt, VCS root, build type "Hello" (krok: echo hello-v1)
python3 scripts/tc_live.py rest POST /app/rest/projects   rest/01-project.xml
python3 scripts/tc_live.py rest POST /app/rest/vcs-roots  rest/02-vcsroot.xml
python3 scripts/tc_live.py rest POST /app/rest/buildTypes rest/03-buildtype.xml

# 4. Włączenie versioned settings (format kotlin) — serwer sam commituje
python3 scripts/tc_live.py rest PUT /app/rest/projects/id:LoopDemo/versionedSettings/config rest/04-versioned-settings-enable.json application/json
# po ok. minucie:
docker exec tc-p14 git --git-dir=/srv/settings.git log --stat --format=fuller
docker exec -w /tmp/w tc-p14 git pull origin main
```

### Pętla: push dewelopera → serwer

```bash
docker cp loop/v2-settings.kts tc-p14:/tmp/w/.teamcity/settings.kts
docker exec -w /tmp/w tc-p14 git -c user.name=dev -c user.email=dev@example.invalid commit -am "v2"
docker exec -w /tmp/w tc-p14 git push origin main
python3 scripts/tc_live.py poll /app/rest/projects/id:LoopDemo/buildTypes LoopDemo_Bye 400
```

Zmierzone: `po 82 s: 200 {"count":2,"buildType":[{"id":"LoopDemo_Bye",...` — wykrycie rewizji + ok. 63 s
generowania DSL (log: `Detected new revision` 01:30:07, `Settings from VCS are generated` 01:31:10).

### Pętla: zmiana w UI/REST → commit serwera (łatka)

```bash
python3 scripts/tc_live.py rest PUT /app/rest/buildTypes/id:LoopDemo_Hello/steps/RUNNER_1/parameters/script.content rest/05-ui-edit-script.txt text/plain
docker exec tc-p14 git --git-dir=/srv/settings.git log --stat --format=%h%x20%an%x20%s -3
```

Wynik: commit `eba27b2 admin New build step parameter added`, jedyny zmieniony plik:
`.teamcity/patches/buildTypes/Hello.kts | 26 +` (treść: `loop/server-patch-Hello.kts`). Po odczycie tego commita
przez serwer log mówi: `settings are up-to-date, skip reloading projects` (nic do przeładowania).

### Konflikt: ten sam krok w `settings.kts` i w łatce

```bash
docker exec -w /tmp/w tc-p14 git pull origin main
docker cp loop/v3-conflict-settings.kts tc-p14:/tmp/w/.teamcity/settings.kts
docker exec -w /tmp/w tc-p14 git -c user.name=dev -c user.email=dev@example.invalid commit -am "v3"
docker exec -w /tmp/w tc-p14 git push origin main
python3 scripts/tc_live.py rest GET /app/rest/projects/id:LoopDemo/versionedSettings/status - application/json
```

Dosłowna odpowiedź:

```json
{"message":"Failed to apply changes from VCS to project settings (revision 8e2891506a4bbb37c3a539b75487e6be49c1c1e8): DSL script execution failure. Please fix the errors in the script and make a new commit.","type":"warn","timestamp":"Wed Oct 07 01:34:57 GMT 2026","versionedSettingsError":[{"message":"Actual build step and build step expected by patch at position 0 are different, reason: Different values of parameter with name 'script.content': 'echo hello-v3 %greeting%' != 'echo hello-v2 %greeting%'","type":"UI changes error","file":"patches/buildTypes/Hello.kts"}]}
```

Konfiguracja na serwerze została przy ostatniej dobrej (`GET .../script.content` → `echo hello-from-rest %greeting%`).

### Edycja przez REST, gdy status jest błędny

`rest/06-edit-during-error.txt` (`PUT .../parameters/greeting` → `czesc`) został przyjęty (200), a serwer
zacommitował łatkę (`d93a614`) NA wierzch zepsutej rewizji `8e28915`. Status po przeładowaniu: znów ten sam błąd.

### Naprawa i literówka

```bash
docker exec -w /tmp/w tc-p14 git pull origin main
docker cp loop/v4-resolved-settings.kts tc-p14:/tmp/w/.teamcity/settings.kts
docker exec -w /tmp/w tc-p14 git rm -q .teamcity/patches/buildTypes/Hello.kts
docker exec -w /tmp/w tc-p14 git -c user.name=dev -c user.email=dev@example.invalid commit -am "v4"
docker exec -w /tmp/w tc-p14 git push origin main
```

Status: `Changes from VCS are applied to project settings, last change 'v4: ...', revision a728e0a..., time spent: 32s,897ms`;
krok = `echo hello-v4 %greeting%`, parametr `greeting` = `czesc`.

Potem `loop/v5-compile-error-settings.kts` (literówka `scriptContents`):

```json
{"message":"Failed to apply changes from VCS to project settings (revision 599e56564a1380871916ccf2a4a0de3c54a209be): Kotlin DSL compilation error. Please fix the errors in the script and make a new commit.","type":"warn","timestamp":"Wed Oct 07 01:45:15 GMT 2026","versionedSettingsError":[{"message":"Unresolved reference: scriptContents","type":"Compilation error","file":"settings.kts [23:13]"}]}
```

Serwer został przy v4 (`greeting` = `czesc`, krok `hello-v4`).

### Graf repo po sesji

```
599e565 dev   v5: literowka
a728e0a dev   v4: rozwiazanie konfliktu, patch usuniety
d93a614 admin Value of the parameter greeting changed
8e28915 dev   v3: zmiana kroku Greet obok patcha serwera
eba27b2 admin New build step parameter added
bde2ce6 dev   v2: greeting param + Bye build type
5fe014a admin Versioned settings configuration updated (TeamCity change in 'Loop Demo' project)
c788b60 dev   init
```

## Co NIE zostało zweryfikowane

- `buildSettingsMode` ≠ `alwaysUseCurrent` (czyli czy build bierze ustawienia z rewizji w VCS): nie było agenta, nie uruchomiłem żadnego builda.
- Blok `versionedSettings { }` w samym DSL (w tym wydaniu konfigurację włączyłem przez REST).
- Repo zdalne z uwierzytelnianiem (GitHub/GitLab), webhooki zamiast pollingu, wartości secure (`storeSecureValuesOutsideVcs`).
- Co się stanie, gdy serwer i deweloper równocześnie wypchną commit do tej samej gałęzi (rozjazd historii).
- Powód, dla którego VCS root repo z ustawieniami nie trafił do `settings.kts` (zaobserwowane, nie zbadane).
- Dokładny interwał pollingu repo (mierzyłem tylko całość push → zmiana widoczna w REST: 82 s dla v2 i 66 s dla v5; wykrycie i generowanie DSL osobno nie były zmierzone od momentu pushu).
- `showSettingsChanges: true` w moim żądaniu `PUT` — odpowiedź zwróciła `false` (nie sprawdzałem czemu).
- `poll` w `tc_live.py` prosi o JSON, więc nie działa na zasobach tylko-tekstowych (`.../parameters/<nazwa>`) — zwraca 406.

## Sprzątanie po sesji

`docker rm -fv tc-p14` (usuwa też anonimowe wolumeny tego kontenera), katalog roboczy z hasłem usunięty.
Obraz `jetbrains/teamcity-server:2025.07` był na maszynie przed sesją i został. Cudzych zasobów nie ruszałem.
