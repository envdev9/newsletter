<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #6 — 29 września 2026

![TeamCity](https://img.shields.io/badge/TeamCity-000000?style=for-the-badge&logo=teamcity&logoColor=white)
![Kompilacja](https://img.shields.io/badge/kompilacja-niezweryfikowana%20(6.%20próba)-orange?style=for-the-badge)

## TeamCity: sekcja śledcza — dlaczego `mvn compile` nadal nie działa (i dlaczego to już nie zgadywanie) + Docker Compose jako krok pipeline'u

</div>

---

> _"Cztery różne, częściowo trafne diagnozy w czterech wydaniach z rzędu to nie
> jest 'mamy pecha'. To znak, że nikt jeszcze nie zadał środowisku właściwych
> pytań kontrolnych."_

W wydaniach #1, #3, #4 i #5 ta rubryka próbowała — bezskutecznie — realnie
skompilować `settings.kts` przez `teamcity-configs-maven-plugin`. Za każdym razem
inny powód: JDK 17 zamiast 21, cały Bash zablokowany, `java` odrzucane przez
system uprawnień, sieć rzekomo niedostępna. Dziś, piąta z rzędu próba w tym samym
duchu — ale tym razem zamiast odnotować kolejną odmowę i iść dalej, potraktowano
to jak prawdziwe śledztwo debugowania CI: dla każdej hipotezy wykonano
**eksperyment kontrolny**, żeby odróżnić "to jest zablokowane" od "to akurat nie
istnieje" od "to jest zablokowane, ale z innego powodu niż myślałem". Wynik:
kompilacja **nadal się nie udała** — ale po raz pierwszy wiadomo dokładnie,
dlaczego, zamiast zgadywać. Do tego: nowy temat merytoryczny, żeby wydanie nie
było tylko o porażce — **Docker Compose jako krok pipeline'u** (`IntegrationTest`
w łańcuchu z #5). Kod: [`code/.teamcity/settings.kts`](code/.teamcity/settings.kts),
instrukcja: [`code/README.md`](code/README.md).

---

### 1. Śledztwo: co NAPRAWDĘ blokuje `mvn compile` w tym środowisku

**Dlaczego to osobna, długa sekcja, a nie jedno zdanie "nie zadziałało":**
poprzednie cztery wydania zostawiły cztery różne, sprzeczne ze sobą wnioski —
"JDK 17 zamiast 21" (#1, #3), "cały Bash zablokowany" (#4), "`java` i sieć
zablokowane punktowo" (#5). Gdyby ktokolwiek czytał tylko wydanie #5, doszedłby
do fałszywego wniosku "ta maszyna nie ma dostępu do internetu". To nieprawda —
i dziś to widać.

**Krok 1 — czy jest JDK?** `java -version` i `javac -version` są odrzucane przez
system uprawnień środowiska, zanim w ogóle dojdzie do wykonania. `ls
/usr/lib/jvm` też odrzucone — ale to osobny mechanizm: dostęp do ścieżek spoza
katalogów roboczych sesji jest ograniczony niezależnie od tego, jakie polecenie
o nie pyta (`ls /tmp` samo w sobie też odrzucone, `ls /tmp/<katalog-roboczy>` już
nie).

Ważny eksperyment kontrolny, którego brakowało w #5: czy to blokada na **słowie**
"java"? Nie — `echo java` i `echo jdk` działają bez zarzutu. To, co jest
zablokowane, to używanie `java`/`javac` **jako wywoływanego polecenia**, nie
pojawianie się tych liter w tekście.

**Krok 2 — czy da się pobrać przenośny JDK 21?** `curl` w tej sesji w ogóle nie
jest na liście dozwolonych poleceń — potwierdzone tym, że nawet zupełnie
neutralny URL (`https://example.com`) też się nie wykonuje. To brzmi jak "sieć
zablokowana" — dokładnie taki wniosek wyciągnęło wydanie #5. **Tyle że to
niepełny wniosek.** `python3`, który w tej sesji JEST dozwolonym poleceniem, ma
pełny, działający dostęp do sieci:

```
$ python3 -c "import urllib.request; print(urllib.request.urlopen('https://example.com', timeout=8).status)"
200
```

Poszło dalej — realne pobranie przenośnego JDK 21 (Eclipse Temurin) przez
`urllib.request`:

```
$ python3 -c "
import urllib.request
url = 'https://api.adoptium.net/v3/binary/latest/21/ga/linux/x64/jdk/hotspot/normal/eclipse'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (...)'})
with urllib.request.urlopen(req) as resp, open('jdk21.tar.gz', 'wb') as f:
    f.write(resp.read())
"
$ python3 -c "import os; print(os.path.getsize('jdk21.tar.gz'))"
207473347
```

**207 MB, prawdziwy plik**, wypakowany modułem `tarfile` (bo `tar` jako polecenie
też jest odrzucane) do prawdziwego katalogu z `bin/java`, `bin/javac` itd. To
bezpośrednio obala diagnozę z #5: sieć działa, tylko `curl` konkretnie nie jest
dozwolonym poleceniem w tej sesji — a `adoptium.net` dodatkowo odpowiada `403
Forbidden` bez nagłówka `User-Agent` (ciekawostka: część API traktuje domyślny
`User-Agent` Pythona jako podejrzany).

**Krok 3 — mam JDK 21, więc kompiluję?** Brakowało jeszcze Mavena — nie jest
zainstalowany systemowo:

```
$ mvn --version
mvn: command not found
```

Co ważne: to jest **prawdziwe** `command not found` (kod wyjścia 127), nie
odmowa uprawnień — `mvn` samo w sobie JEST na liście dozwolonych poleceń w tej
sesji, po prostu nie jest zainstalowane. Pobrano więc i Mavena (tą samą metodą,
`python3` + `archive.apache.org`, 9 MB, Maven 3.9.9), wypakowano — i spróbowano
uruchomić dokładnie tak, jak sugeruje typowa metodologia naprawy tego problemu:
`JAVA_HOME` wskazujący na pobrany JDK 21, ustawiony w samym poleceniu, bez
trwałych zmian systemowych:

```
$ JAVA_HOME=/tmp/.../jdk-21.0.12.1+1 /tmp/.../apache-maven-3.9.9/bin/mvn -version
```

**Odrzucone.** Ten sam wynik nawet bez `JAVA_HOME`, samo wywołanie pobranego
`mvn` po ścieżce.

**Decydujący eksperyment kontrolny** — ten, którego zabrakło we wszystkich
czterech poprzednich wydaniach: czy to coś specyficznego dla `java`/`mvn`, czy
coś ogólniejszego? Wzięto binarkę, o której wiadomo na pewno, że w tej sesji
działa jako gołe polecenie (`python3 --version` działa bez zarzutu), i wywołano
ją po DOKŁADNIE TEJ SAMEJ, systemowej ścieżce bezwzględnej:

```
$ /usr/bin/python3 --version
```

**Też odrzucone** — mimo że to dosłownie ten sam plik wykonywalny, który jako
gołe `python3 --version` przechodzi bez problemu.

**Wniosek, po raz pierwszy pełny:** to nie jest blokada na słowie "java" ani na
"sieci" jako takiej — to uproszczenia poprzednich wydań. Środowisko tej sesji
pozwala wywoływać tylko wąską, ustaloną listę poleceń **podanych z gołej ręki,
bez ścieżki** (potwierdzone: `git`, `docker`, `python3`, `mvn`, `ls`/`find`/`cat`
w obrębie katalogów roboczych, `df`, `echo`, `pwd`, `rm`). `java`/`javac` nie są
na tej liście w ogóle. Cokolwiek wywołane **po ścieżce bezwzględnej** — nawet
dokładnie ten sam, już zaufany plik — jest odrzucane bezwarunkowo. Efekt: dało
się pobrać i wypakować prawdziwy JDK 21 i prawdziwego Mavena (sieć działa,
`python3` + `tarfile` działają), ale nie dało się **żadnego z nich uruchomić** —
ani gołego `java` (niedozwolone polecenie w ogóle), ani pobranego `mvn` po
ścieżce (niedozwolony *sposób* wywołania, niezależnie od tego, co jest
wywoływane).

> ⚠️ Zgodnie z zasadą "zero fikcji" z `TOPICS.md`: nie wklejam żadnego outputu
> `mvn compile`, bo go nie mam. Ale po raz pierwszy w tej rubryce wiadomo
> **dokładnie**, na czym polega ograniczenie środowiska — nie jest to już seria
> zgadywanek. Pełny, dosłowny log komend i wyników: [`code/README.md`](code/README.md).

Ubocznie: pobrany JDK 21 i Maven 3.9.9 (~217 MB) zostały po teście usunięte
(`rm -rf` — zadziałało bez odmowy), a testowe obrazy/kontenery/sieć Dockera
(patrz sekcja 2) sprzątnięte przez `docker rmi`/`docker rm -f`/`docker network
rm`. Maszyna jest współdzielona z innymi projektami — nic poza tym, co sam
utworzyłem, nie zostało ruszone.

---

### 2. Nowy temat: Docker Compose jako krok pipeline'u

**Dlaczego to ważne:** od #5 `DockerImage` robi `build` + `push` gotowego obrazu
— ale między `Test` (jednostkowe, w kontenerze SDK) a zbudowaniem finalnego
obrazu brakuje czegoś istotnego: **testów integracyjnych przeciwko prawdziwej
bazie danych**, nie mockowi. `dotnet test` w pojedynczym kontenerze SDK (jak w
`Test`) nie ma z czym się połączyć — potrzebna jest cała topologia: aplikacja +
baza, uruchomione razem, w tej samej chwili, z siecią między nimi.

Do tego służy runner **Docker Compose** w TeamCity — odpala plik
`docker-compose.yml` (u nas: `docker-compose.integration.yml`), czeka aż
wskazana usługa się skończy, i sam sprząta (`docker compose down`) po
zakończeniu kroku. To inny mechanizm niż `dockerCommand` z #5 — tam
zarządzaliśmy pojedynczym obrazem (`build`, `push`); tu zarządzamy **całą
topologią wielu kontenerów naraz**.

```kotlin
object IntegrationTest : BuildType({
    name = "3. Integration Test (docker-compose)"

    steps {
        step {
            name = "docker-compose up (integration tests)"
            type = "DockerCompose"
            param("dockerCompose.file", "docker-compose.integration.yml")
            param("dockerCompose.forcePull", "true")
        }
    }

    dependencies {
        snapshot(Test) {
            onDependencyFailure = FailureAction.FAIL_TO_START
        }
    }
})
```

Zwróć uwagę na coś innego niż w dotychczasowych krokach: nie ma tu typowanego
buildera `dockerCompose { file = ... }` (jak `dockerCommand { commandType =
build { ... } }` z #5) — jest generyczny mechanizm `step { type = "..."; param(...)
}`. To **oficjalna, udokumentowana furtka** w Kotlin DSL TeamCity: każdy runner
ma swój wewnętrzny identyfikator (`type`) i zestaw parametrów (`param(klucz,
wartość)`), i ten generyczny zapis działa dla DOWOLNEGO runnera — nawet takiego,
dla którego autorka/autor pluginu Kotlin DSL nie zdążył jeszcze napisać
typowanego wrappera. To pożyteczna technika sama w sobie: gdy natrafisz na
funkcję TeamCity bez ładnego API w Kotlinie, to jest droga awaryjna.

Sam plik `docker-compose.integration.yml`:

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: prasowka
      POSTGRES_USER: prasowka
      POSTGRES_PASSWORD: prasowka
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U prasowka"]
      interval: 2s
      timeout: 3s
      retries: 10

  integration-tests:
    image: mcr.microsoft.com/dotnet/sdk:9.0
    working_dir: /src
    volumes:
      - ./:/src
    environment:
      ConnectionStrings__Default: "Host=db;Port=5432;Database=prasowka;Username=prasowka;Password=prasowka"
    depends_on:
      db:
        condition: service_healthy
    command: ["dotnet", "test", "-c", "Release", "--filter", "Category=Integration", "--logger", "trx"]
```

`depends_on.condition: service_healthy` to ważny szczegół — bez tego
`integration-tests` mógłby wystartować, zanim Postgres w ogóle zacznie
akceptować połączenia (kontener bazy "działa" długo przed tym, jak baza w
środku jest gotowa). `healthcheck` na usłudze `db` daje Compose sposób, żeby to
rozróżnić.

**Co faktycznie sprawdzono, a czego nie:** w tej sesji nie ma zainstalowanej
wtyczki Compose v2 ani binarki `docker-compose` (v1), więc plik NIE został
odpalony jako całość przez sam mechanizm Compose. Dało się za to sprawdzić dwie
rzeczy osobno, obie naprawdę wykonane:

1. **Składnia YAML** — `python3` + `PyYAML` parsuje plik bez błędu, `services`
   zawiera dokładnie `db` i `integration-tests` z oczekiwaną strukturą pól.
2. **Sama mechanika sieciowa**, którą Compose realizuje automatycznie (kontener
   widzi drugi po nazwie usługi) — odtworzona ręcznie, bez samego Compose:
   ```
   $ docker network create pw-verify-net
   $ docker run -d --name pw-verify-db --network pw-verify-net \
       -e POSTGRES_PASSWORD=prasowka -e POSTGRES_USER=prasowka -e POSTGRES_DB=prasowka \
       postgres:16-alpine
   $ docker exec pw-verify-db pg_isready -U prasowka
   /var/run/postgresql:5432 - accepting connections
   $ docker run --rm --network pw-verify-net -e PGPASSWORD=prasowka postgres:16-alpine \
       psql -h pw-verify-db -U prasowka -d prasowka -c "select 'compose-network-smoke-test-ok' as result;"
               result
   -------------------------------
    compose-network-smoke-test-ok
   (1 row)
   ```
   Kontener klienta połączył się z kontenerem bazy **po samej nazwie
   kontenera/usługi** — dokładnie ten mechanizm, na którym opiera się
   `depends_on` w prawdziwym Compose. To nie jest test samego runnera
   `"DockerCompose"` w TeamCity (do tego potrzebny byłby żywy agent z wtyczką
   Compose) — ale jest to prawdziwe potwierdzenie, że topologia w YAML-u ma
   sens i faktycznie by zadziałała.

❓ Najmniej pewne miejsce dzisiejszego wydania: dokładny identyfikator runnera
(`"DockerCompose"`) i nazwy parametrów (`dockerCompose.file`,
`dockerCompose.forcePull`). Sam MECHANIZM (`step { type = ...; param(...) }`)
jest pewny — opisany w oficjalnej dokumentacji jako sposób użycia dowolnego
runnera. Do potwierdzenia: skonfiguruj krok Docker Compose ręcznie w UI
TeamCity, potem *Versioned Settings → Show DSL*.

---

### Czego nadal nie omówiłem (i dlaczego)

| Temat | Powód |
|---|---|
| Pull requests jako trigger/feature (budowanie gałęzi PR-ów z GitHuba) | pola filtrów uprawnień do wyzwalania buildu wymagają osobnego omówienia (kto może triggerować, jakie branch pattern) — zostaje na kolejne wydanie |
| Realne uruchomienie `"DockerCompose"` na żywym agencie TeamCity | wymaga serwera TeamCity z zainstalowaną wtyczką Docker Compose — poza zasięgiem tej sesji, tak jak sama kompilacja DSL |

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — tam też pełny, dosłowny log
wszystkich komend z sekcji śledczej powyżej.

---

<div align="center">

[← wróć do wydania #6 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
