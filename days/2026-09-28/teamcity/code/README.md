# Kod do wydania #5 — TeamCity: matrix, parallel tests, docker registry login + push

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> **Matrix build feature** z jednej konfiguracji `Test` robi trzy wirtualne przebiegi —
> po jednym na każdą wartość parametru `env.SDK_VERSION` (`8.0`, `9.0`, `10.0`) — bez
> kopiowania build type'u trzy razy. **Parallel tests** dzieli listę testów JEDNEGO
> takiego przebiegu na kilka "paczek" wykonywanych równolegle na wolnych agentach.
> Wreszcie `DockerImage` przestaje się kończyć na samym `docker build` (jak w #4) —
> feature `dockerSupport` loguje agenta do rejestru obrazów (connection `dockerRegistry`
> zdefiniowany na poziomie projektu), a drugi krok `dockerCommand` robi realny
> `docker push`.

## Struktura

```
code/.teamcity/
├── settings.kts   # Compile -> Test (matrix + parallelTests) -> DockerImage (login+push) -> Release
├── pom.xml        # Maven z teamcity-configs-maven-plugin (offline weryfikacja DSL)
└── .gitignore     # target/
```

Zakładane repo aplikacji: rozwiązanie .NET w katalogu głównym i `Dockerfile`.

## Jak sprawdzić kompilację DSL od zera

Wymagania: JDK 21, Maven 3.9+, dostęp do sieci (`download.jetbrains.com/teamcity-repository`
i Maven Central).

```bash
cd .teamcity
mvn -Dmaven.repo.local=/tmp/m2repo compile
```

Oczekiwany wynik: `BUILD SUCCESS` i XML-e w `target/teamcity-generated/`, albo błąd
Kotlina z numerem linii w `settings.kts` — w takim wypadku zacznij od miejsc oznaczonych
`[?]` (nowe w tym wydaniu: `matrix`, `parallelTests`, `dockerRegistry`, `dockerSupport`).

## Stan weryfikacji: NIEZWERYFIKOWANE (4. próba z rzędu, nowy powód)

To już czwarte wydanie tej rubryki (#1, #3, #4, #5), w którym `mvn compile` na tym
`pom.xml` NIE został realnie uruchomiony. Tym razem powód jest **inny** niż wcześniej —
i to jest właściwa treść tej sekcji, nie tylko powtórzenie "niezweryfikowane".

### Co dokładnie sprawdzono w tej sesji

Priorytetem przed pisaniem tego wydania było spróbowanie naprawić problem z poprzednich
trzech wydań (JDK 17 zamiast wymaganego przez wtyczkę JDK 21) przez pobranie
przenośnego JDK 21 (Eclipse Temurin) do `/tmp`, bez roota i bez instalacji systemowej.
Przebieg prób, w kolejności:

1. `echo test` — **zadziałało**. Bash w tej sesji nie jest całkowicie zablokowany
   (w przeciwieństwie do wydania #4, gdzie każde polecenie odrzucało środowisko).
2. `java -version` — **odrzucone przez system uprawnień** (komunikat: "Permission to
   use Bash has been denied because Claude Code is running in don't ask mode"). Ważne:
   to nie jest błąd wykonania (jak "command not found") — to twarda odmowa PRZED
   uruchomieniem, wywołana najwyraźniej samą obecnością słowa `java` w poleceniu.
   Potwierdzone powtórnie (ten sam wynik za drugim razem) oraz przez `env | grep -i java`
   (samo `grep -i java`, bez uruchamiania jakiegokolwiek javowego binarki, też zostało
   odrzucone) — więc to blokada na poziomie treści polecenia, nie na poziomie
   rzeczywistego uruchomienia procesu.
3. `mvn -version` — wykonało się (bez odmowy), ale zwróciło `mvn: command not found`
   (exit 127). Maven więc nie jest zainstalowany, ale przynajmniej próba wykonania nie
   została zablokowana przez system uprawnień — inaczej niż w przypadku `java`.
4. Próba pobrania przenośnego JDK 21: `curl -sI
   https://api.adoptium.net/v3/binary/latest/21/ga/linux/x64/jdk/hotspot/normal/eclipse
   --max-time 15` — **odrzucone przez system uprawnień**, ten sam komunikat co przy
   `java`. Sieć (co najmniej przez `curl`) jest zablokowana dla tej sesji, więc ścieżka
   "pobierz JDK 21 jako tar.gz do /tmp" opisana w zadaniu okazała się niewykonalna, i to
   zanim doszło do sprawdzenia miejsca na dysku.
5. Dodatkowo: dostęp do ścieżek spoza katalogów roboczych (np. `ls /usr/lib`, `ls /opt`,
   sam `ls /tmp` bez podkatalogu) też jest odrzucany — sandbox tej sesji ogranicza Bash
   do `/tmp/prasowka-devops-LwidrH` i jego podkatalogów. `df -h /tmp` zadziałało (to
   odczyt metadanych systemu plików, nie listowanie katalogu), więc miejsce na dysku
   teoretycznie by starczyło (44G wolne), ale to bez znaczenia, skoro pobranie i tak
   jest zablokowane.

### Wniosek

W tej sesji **nie da się** ani uruchomić `java`/`mvn` z realnym JDK 21, ani pobrać
takiego JDK z internetu — niezależnie od tego, czy JDK 21 istnieje już gdzieś na tej
maszynie (nie sposób tego nawet sprawdzić, skoro samo polecenie zawierające `java`
jest odrzucane). To NIE jest ten sam problem co w #1/#3 (JDK 17 zamiast 21) ani ten sam
co w #4 (cały Bash zablokowany) — to nowy, trzeci różny powód niepowodzenia w czterech
próbach. Zgodnie z zasadą "zero fikcji" z `TOPICS.md`: **nie wklejam żadnego outputu
kompilacji, bo go nie mam.** Kod (`settings.kts`) pozostaje więc opisem składni z
dokumentacji/pamięci, z `[?]` przy miejscach najmniej pewnych.

### Sprzątanie

Zgodnie z zadaniem, po próbach z JDK 21 sprawdzono, czy zostały jakiekolwiek pliki
tymczasowe do posprzątania w `/tmp`: żaden plik nie został pobrany ani utworzony poza
katalogiem tego wydania (JDK 21 nigdy nie trafił na dysk, bo pobranie zostało odrzucone
na starcie) — nie było więc czego usuwać. Nie utworzono `/tmp/jdk21`.

### Jak sprawdzić samemu

Na maszynie z realnym dostępem do sieci i JDK 21:

```bash
cd .teamcity
JAVA_HOME=/ścieżka/do/jdk-21 mvn compile
```

Błąd kompilatora Kotlina wskaże dokładną linię — zacznij od miejsc oznaczonych `[?]`
w `settings.kts` (`matrix`, `parallelTests`, `dockerRegistry`, `dockerSupport`).
Najpewniejszy sposób potwierdzenia dokładnej składni: skonfiguruj każdy z tych
feature'ów ręcznie w UI TeamCity, a potem *Versioned Settings → Show DSL* — serwer sam
wygeneruje poprawny Kotlin.
