# Kod do wydania #4 — TeamCity: build features, failure conditions, Docker, composite

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> **Build feature** zmienia zachowanie *wokół* builda (commit status publisher, swabra,
> perfmon), a **failure conditions** pozwalają uznać build za nieudany mimo exit code 0
> (timeout, spadek liczby testów, wzorzec w logu). Krok `script` z `dockerImage` działa
> w kontenerze (agent bez .NET SDK), a `dockerCommand` zarządza `docker build`.
> **Composite build** (`Type.COMPOSITE`) nie ma kroków - agreguje łańcuch w jeden
> status i to on dostaje trigger oraz commit status publisher. **Versioned settings**
> trzymają konfigurację w repo (`.teamcity/`).

## Struktura

```
code/.teamcity/
├── settings.kts   # Compile -> Test -> DockerImage -> Release (composite)
├── pom.xml        # Maven z teamcity-configs-maven-plugin (offline weryfikacja DSL)
└── .gitignore     # target/
```

Zakładane repo aplikacji: rozwiązanie .NET w katalogu głównym i `Dockerfile`.

## Jak sprawdzić kompilację DSL

Wymagania: JDK 21, Maven 3.9+, dostęp do `download.jetbrains.com/teamcity-repository`
i Maven Central.

```bash
cd .teamcity
mvn -Dmaven.repo.local=/tmp/m2repo compile
```

Oczekiwany wynik: `BUILD SUCCESS` i XML-e w `target/teamcity-generated/` albo błąd
Kotlina z numerem linii w `settings.kts`.

## Stan weryfikacji: NIEZWERYFIKOWANE

W tej sesji każde polecenie powłoki zostało odrzucone przez środowisko, więc nie
sprawdzono nawet dostępności JDK/Mavena i nie podjęto próby pobrania. Kod nie był
kompilowany. Linie oznaczone w `settings.kts` komentarzem `[?]` to miejsca największej
niepewności składni (`versionedSettings`, `failOnMetricChange`, `failOnText`,
`commitStatusPublisher` z `github`/`personalToken`, `dockerImagePlatform`). Nie
utworzono żadnych plików poza katalogiem wydania, więc nie było co sprzątać.
