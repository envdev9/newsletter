# Kod do wydania #3 — pipeline .NET w TeamCity (templates, parametry, dependencies)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> **Szablon** (`Template`) wygląda jak build configuration, ale nie da się go
> uruchomić - to wzorzec z VCS rootem, parametrami i wymaganiami, który potomkowie
> dziedziczą przez `templates(...)` i mogą nadpisać (override). **Parametry** mają
> prefiksy: brak (konfiguracyjny), `env.` (zmienna środowiskowa), `system.`
> (właściwość builda); typ `password` maskuje wartość, a w repo trzyma tylko
> odwołanie `credentialsJSON:<uuid>`. **Snapshot dependency** pilnuje kolejności i
> tej samej rewizji kodu (tworzy łańcuch buildów), **artifact dependency** przenosi
> pliki (artifact rules `lewa => prawa`). Trigger VCS stoi tylko na ostatnim ogniwie
> (`Pack`), a snapshoty ściągają przed nim `Test` i `Build`.

## Struktura

```
code/.teamcity/
├── settings.kts   # szablon DotnetStage + Build -> Test -> Pack (snapshot + artifacts)
├── pom.xml        # Maven z teamcity-configs-maven-plugin (offline weryfikacja DSL)
└── .gitignore     # target/
```

Zakładany układ repo aplikacji: rozwiązanie `.sln` (lub jeden projekt) w katalogu
głównym, z projektami testowymi; `dotnet restore/build/test/pack` są wołane bez
argumentu ścieżki. Dostosuj do własnego repo.

## Jak sprawdzić kompilację DSL

Wymagania: **JDK 21** (wtyczka ma `requiredJavaVersion=21`), Maven 3.9+, dostęp do
`download.jetbrains.com/teamcity-repository` i Maven Central, kilkaset MB miejsca
na zależności (w wydaniu #1 pobrano ok. 211 MB).

```bash
cd .teamcity
mvn -Dmaven.repo.local=/tmp/m2repo compile
```

Wynik: `BUILD SUCCESS` i wygenerowane XML-e w `target/teamcity-generated/`, albo
błąd kompilacji Kotlina wskazujący linię w `settings.kts`.

## Stan weryfikacji w tym wydaniu: NIEZWERYFIKOWANE

Co zrobiono:

- sprawdzono środowisko: `mvn` niedostępny, `java` w wersji 17 (za stary dla
  wtyczki), wolne miejsce na dysku ok. 46 GB;
- utworzono pusty katalog roboczy `/tmp/tc-verify`;
- próbowano pobrać `curl`-em przenośny JDK 21 (Temurin, `api.adoptium.net`) oraz
  Apache Maven 3.9.9 (`archive.apache.org`) do tego katalogu - **oba polecenia
  zostały odrzucone przez środowisko**. Po odrzuceniu nie próbowano obejść
  blokady; następne polecenia powłoki też zostały odrzucone.

Skutki:

- `mvn compile` / `teamcity-configs:generate` **nie zostały uruchomione**,
- **nie ma** prawdziwego wygenerowanego XML-a (i żadnego nie zmyślamy),
- `settings.kts` z wydania #1 **nie został** zweryfikowany retroaktywnie,
- `settings.kts` z tego wydania jest napisany według dokumentacji Kotlin DSL, ale
  **nie był kompilowany** - traktuj składnię (zwłaszcza `password(label=, display=)`,
  `sameChainOrLastFinished()`, `requirements { contains(...) }`) jako do
  potwierdzenia.

Sprzątanie: po sesji został pusty katalog `/tmp/tc-verify` (nie udało się go usunąć
z powodu odrzucenia poleceń powłoki; nic w nim nie ma). Nie utworzono `~/.m2`,
JDK ani Maven, więc nie było czego więcej sprzątać.
