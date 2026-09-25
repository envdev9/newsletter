<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #1 — 24 września 2026

![TeamCity](https://img.shields.io/badge/TeamCity-000000?style=for-the-badge&logo=teamcity&logoColor=white)

## Konfiguracja builda jako kod: pierwszy `.teamcity/settings.kts`

</div>

---

> _"Klikanie 'New build configuration' w UI jest fajne do pierwszego builda. Do
> setnego - już nie. Kotlin DSL sprawia, że konfiguracja TeamCity trafia do repo,
> obok kodu, który buduje - z historią, code review i możliwością cofnięcia commita."_

Dziś podstawy TeamCity dla kogoś, kto nigdy go nie widział: czym jest **VCS root**,
**build configuration**, **build step** i **trigger**, oraz jak to samo wyraża się
jako kod w `.teamcity/settings.kts` zamiast klikania w przeglądarce. Bez żywego
serwera TeamCity próbowaliśmy **naprawdę** zweryfikować kompilację tego pliku
oficjalnym mechanizmem JetBrains (Maven + `teamcity-configs-maven-plugin`) - i
trafiliśmy na realną ścianę, którą poniżej opisujemy uczciwie, z prawdziwym
komunikatem błędu. Szczegóły w [`code/README.md`](code/README.md).

---

### TeamCity w jednym zdaniu (dla kogoś z .NET)

TeamCity to serwer CI/CD od JetBrains - odpowiednik Azure DevOps Pipelines czy
GitHub Actions, tylko instalowany samodzielnie (on-prem albo w chmurze), z osobnym
"serwerem" (koordynuje wszystko, ma UI) i "agentami" (maszyny, które faktycznie
wykonują buildy). Zadanie jest to samo co wszędzie: ktoś robi `git push`, TeamCity
to zauważa, ściąga kod i wykonuje zdefiniowaną sekwencję kroków - kompilacja, testy,
publikacja artefaktu.

---

### Cztery pojęcia, bez których nic tu nie zrozumiesz

- **VCS root** - wskazuje TeamCity *skąd* brać kod: adres repozytorium (Git, SVN,
  Perforce...), branch, dane logowania. To osobny, nazwany obiekt - nie część
  build configuration - bo ten sam VCS root (to samo repo) często podpina się pod
  kilka różnych build configurations (np. "Build" i "Deploy" korzystają z tego
  samego repo, ale robią różne rzeczy).
- **Build configuration** - "przepis" na jeden konkretny rodzaj builda: jakie kroki
  wykonać, z jakiego VCS roota wziąć kod, czym się odpalić. Odpowiednik jednego
  `job` w GitHub Actions albo jednego pipeline'u w Azure DevOps. Projekt w TeamCity
  może mieć wiele build configurations (np. "Build i testy", "Publikacja NuGet",
  "Deploy na staging").
- **Build step** - pojedyncza czynność wewnątrz build configuration, wykonywana po
  kolei: "uruchom skrypt", "zbuduj rozwiązanie .NET", "uruchom testy jednostkowe".
  Odpowiednik jednego `step:` w joba GitHub Actions.
- **Trigger** - reguła "kiedy uruchomić ten build automatycznie", bez ręcznego
  klikania. Najpopularniejszy: VCS trigger - "odpal build przy każdym pushu do tego
  VCS roota". Odpowiednik `on: push` w GitHub Actions.

Czyli cała hierarchia: **projekt** zawiera **VCS roots** i **build configurations**,
każda build configuration ma listę **build steps** (co robić) i **triggers** (kiedy
zrobić to automatycznie).

---

### Dlaczego w ogóle "konfiguracja jako kod"

Domyślnie wszystko powyżej ustawia się klikając w UI TeamCity - i to działa, dopóki
masz jeden mały projekt. Problem pojawia się przy skali: konfiguracja klikana w UI
nie ma historii zmian widocznej jak `git log`, nie da się jej zrecenzować w pull
requeście, trudno ją skopiować między projektami. TeamCity rozwiązuje to opcją
**Versioned Settings**: cała konfiguracja projektu (VCS roots, build configurations,
steps, triggers) może żyć jako plik `.teamcity/settings.kts` - zwykły plik Kotlin,
w tym samym repo co kod, commitowany razem z nim. Serwer TeamCity przy każdym pushu
odczytuje ten plik i **odtwarza z niego model projektu** - dokładnie tak samo jak
`docker-compose.yml` opisuje kontenery albo plik `.csproj` opisuje projekt .NET.

---

### `settings.kts` - ta sama hierarchia, tylko jako kod

Plik w [`code/.teamcity/settings.kts`](code/.teamcity/settings.kts) (pochodzi z
wcześniejszej, przerwanej sesji nad tą rubryką - oceniłem go w tej sesji jako
poprawnie zbudowany i użyłem jako punkt startowy do weryfikacji):

```kotlin
version = "2026.3"

project {
    vcsRoot(PrasowkaVcs)
    buildType(Build)
}

object PrasowkaVcs : GitVcsRoot({
    name = "Prasówka (GitHub)"
    url = "https://github.com/envdev9/newsletter.git"
    branch = "refs/heads/main"
})

object Build : BuildType({
    name = "Build i testy"

    vcs {
        root(PrasowkaVcs)
    }

    steps {
        script {
            name = "Powiedz cześć"
            scriptContent = "echo 'Buduję prasówkę...'"
        }
    }

    triggers {
        vcs {
        }
    }
})
```

Mapowanie jeden do jednego na pojęcia z góry:

- `object PrasowkaVcs : GitVcsRoot({...})` - **VCS root**. `url` i `branch` to
  dokładnie to, co wpisałbyś w formularzu "Create VCS root" w UI.
- `object Build : BuildType({...})` - **build configuration**. `name` to etykieta
  widoczna na liście buildów.
- `vcs { root(PrasowkaVcs) }` wewnątrz `Build` - podpięcie tej konkretnej build
  configuration pod ten VCS root (relacja "wiele do wielu" wspomniana wyżej).
- `steps { script { ... } }` - lista **build steps**. Tu jeden krok typu `script`
  (dowolny skrypt powłoki) - najprostszy możliwy build step, celowo bez realnego
  builda .NET, żeby na start nie mieszać dwóch nowych rzeczy naraz (Kotlin DSL +
  konkretny runner .NET). To naturalny temat na kolejne wydanie tej rubryki.
- `triggers { vcs { } }` - jeden **trigger**: pusty blok `vcs {}` oznacza "domyślne
  ustawienia VCS triggera", czyli "odpal przy każdym pushu do gałęzi z VCS roota".

To wszystko - dosłownie ten sam model, co w UI, tylko jako Kotlin zamiast
klikania.

---

### Jak to naprawdę zweryfikowaliśmy bez żywego serwera TeamCity

Nie mamy tu działającego TeamCity Servera, więc "uruchomienie" tego configu nie
mogło oznaczać prawdziwego builda. Zamiast tego użyliśmy **realnego, udokumentowanego
przez JetBrains** mechanizmu offline: wtyczki Maven
`org.jetbrains.teamcity:teamcity-configs-maven-plugin`, która ładuje `settings.kts`
przez ten sam silnik Kotlina co prawdziwy serwer i próbuje zbudować z niego model
projektu. Jeśli w pliku jest błąd składni albo nieznana referencja, `mvn compile`
kończy się prawdziwym błędem kompilacji - to jest nasz odpowiednik `dotnet build`
dla tej rubryki. Cały setup jest w [`code/.teamcity/pom.xml`](code/.teamcity/pom.xml).

**Ograniczenie tej maszyny, zadeklarowane z góry**: dysk ma tylko ok. 230 MB wolnego
miejsca (40 GB dysku, 37 GB zajęte innymi projektami). Maven nie był zainstalowany
(`apt-get install maven` wymaga hasła do `sudo`, którego nie mamy) - więc ściągnęliśmy
przenośną binarkę Apache Maven 3.9.9 (9 MB) do `/tmp`, bez dotykania systemowych
pakietów.

Uruchomienie `mvn compile` **naprawdę pobrało 227 prawdziwych zależności** (~211 MB)
z publicznego repozytorium JetBrains (`download.jetbrains.com/teamcity-repository`)
i Maven Central - w tym `configs-dsl-kotlin-latest` (bazowy model DSL), kompilator
Kotlina (`kotlin-compiler-2.0.21.jar`, ~sam w sobie kilkadziesiąt MB) i klasy
prawdziwego serwera TeamCity potrzebne wtyczce do interpretacji configu. To już samo
w sobie potwierdza, że współrzędne zależności w `pom.xml` są poprawne i realnie
pobieralne - nie zmyślone nazwy paczek.

Zabrakło jednak miejsca na dysku na tyle mocno (wolne miejsce spadło z ~230 MB do
**596 KB** w trakcie pobierania), że musieliśmy to obserwować na żywo i natychmiast
posprzątać po sobie (`rm -rf` katalogu z pobranym Maven i lokalnym repo, oba w
`/tmp`, więc żadnego cudzego projektu nie ruszaliśmy) - dysk wrócił do stanu sprzed
weryfikacji, ok. 222 MB wolnego.

### Prawdziwy wynik: `BUILD FAILURE`, ale nie z powodu dysku

Mimo ekstremalnie ciasnego dysku, pobieranie zależności **zdążyło się zakończyć** i
`mvn compile` doszedł do właściwego kroku - uruchomienia wtyczki
`teamcity-configs-maven-plugin`. Tam dostaliśmy prawdziwy, odtwarzalny błąd:

```
[ERROR] Failed to execute goal org.jetbrains.teamcity:teamcity-configs-maven-plugin:2026.3-dsl6:generate
(generate-teamcity-config) on project settings-dsl-verification: Execution generate-teamcity-config
of goal ...generate failed: An API incompatibility was encountered while executing
...generate: java.lang.UnsupportedClassVersionError: jetbrains/buildServer/serverSide/impl/versionedSettings/VersionedSettingsException
has been compiled by a more recent version of the Java Runtime (class file version 65.0), this
version of the Java Runtime only recognizes class file versions up to 61.0
```

Odczyt: class file version **65.0 = Java 21**, a wersja **61.0 = Java 17**. Ta
konkretna wersja wtyczki (`2026.3-dsl6`) jest skompilowana pod JDK 21, a na tej
maszynie jest zainstalowany tylko **OpenJDK 17** (`openjdk-17-jdk`, sprawdzone
przez `java -version`). Zainstalowanie JDK 21 wymagałoby albo `sudo apt-get install
openjdk-21-jdk` (nie mamy hasła do `sudo`), albo kolejnych dziesiątek MB ściąganych
na dysk, którego już praktycznie nie ma - więc **zatrzymaliśmy się tutaj**, zgodnie z
zasadą "zero fikcji" tej prasówki, zamiast zmyślać, że kompilacja się powiodła.

To dokładnie ten scenariusz, który poprzednia (przerwana) sesja przewidziała w
komentarzu na górze `pom.xml` - tam była to hipoteza opisana z góry; w tej sesji
stała się **potwierdzonym, realnym błędem**, z prawdziwym stack trace'em.

---

### Co to oznacza - i czego NIE zweryfikowaliśmy

Zweryfikowaliśmy realnie: że mechanizm offline weryfikacji Kotlin DSL istnieje,
że zależności w `pom.xml` są prawdziwe i pobieralne, że wtyczka faktycznie próbuje
wystartować i wczytać `settings.kts` - oraz że blokerem na tej konkretnej maszynie
jest wersja JDK, a nie błąd w samym configu.

Czego **nie** zweryfikowaliśmy, i mówimy to wprost: czy `settings.kts` jest w 100%
poprawny składniowo i semantycznie - plugin padł na etapie własnego bootstrapu
(ładowanie klas serwera TeamCity), **zanim** doszedł do parsowania naszego pliku.
Gdyby ta sama komenda uruchomiła się na maszynie z JDK 21 i odrobiną więcej wolnego
miejsca na dysku, kolejny krok pokazałby albo `BUILD SUCCESS` z wygenerowanym
modelem projektu, albo prawdziwy błąd składni w `settings.kts` - i to jest
naturalny punkt startowy na kolejne wydanie tej rubryki.

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — dokładne komendy (łącznie z instalacją
Maven bez roota), pełny, nieprzycięty log z próby `mvn compile` i dokładne liczby
(ile pobrano, ile zajęło miejsca na dysku, gdzie i dlaczego się zatrzymało).

---

<div align="center">

[← wróć do wydania #1 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
