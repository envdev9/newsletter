import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildSteps.script
import jetbrains.buildServer.configs.kotlin.triggers.vcs
import jetbrains.buildServer.configs.kotlin.vcs.GitVcsRoot

version = "2026.3"

project {
    vcsRoot(PrasowkaVcs)

    // Szablon musi być zarejestrowany w projekcie, zanim ktokolwiek go użyje.
    template(DotnetStage)

    buildType(Build)
    buildType(Test)
    buildType(Pack)

    // Parametr na poziomie projektu: widoczny dla wszystkich build configurations
    // (i szablonów) w tym projekcie. Wszyscy dziedziczą go jako %version.prefix%.
    params {
        param("version.prefix", "1.0")
    }
}

object PrasowkaVcs : GitVcsRoot({
    name = "Prasówka (GitHub)"
    url = "https://github.com/envdev9/newsletter.git"
    branch = "refs/heads/main"
})

// ---------------------------------------------------------------------------
// SZABLON: wspólny szkielet dla każdego etapu pipeline'u .NET.
// Sam nic nie buduje (szablon nie jest build configuration, nie da się go
// uruchomić) - tylko przekazuje potomkom VCS, parametry i wspólne ustawienia.
// ---------------------------------------------------------------------------
object DotnetStage : Template({
    name = "Etap .NET (szablon)"

    vcs {
        root(PrasowkaVcs)
    }

    params {
        // parametr konfiguracyjny - dostępny w krokach jako %configuration%
        param("configuration", "Release")

        // parametr środowiskowy (env.) - trafia do zmiennych środowiskowych
        // procesu, więc dotnet CLI zobaczy go jako $DOTNET_CLI_TELEMETRY_OPTOUT
        param("env.DOTNET_CLI_TELEMETRY_OPTOUT", "1")
        param("env.DOTNET_NOLOGO", "1")

        // parametr systemowy (system.) - trafia do skryptów builda jako właściwość
        param("system.artifacts.dir", "artifacts")

        // parametr typu password: wartość nie pojawia się w logu ani w UI.
        // W repo trzyma się tylko odwołanie credentialsJSON:<uuid> do sekretu
        // zapisanego na serwerze (UUID poniżej jest fikcyjny).
        password(
            "env.NUGET_API_KEY",
            "credentialsJSON:00000000-0000-0000-0000-000000000000",
            label = "Klucz API NuGet",
            display = ParameterDisplay.HIDDEN
        )
    }

    requirements {
        // Wszystkie etapy wymagają agenta z Linuksem (jeden wspólny warunek w szablonie).
        contains("teamcity.agent.jvm.os.name", "Linux")
    }
})

// ---------------------------------------------------------------------------
// ETAP 1: build. Publikuje wynik do katalogu artifacts/build i wystawia go
// jako artefakt (artifact rules) - z niego korzystają kolejne etapy.
// ---------------------------------------------------------------------------
object Build : BuildType({
    templates(DotnetStage)
    name = "1. Build"

    // numer builda zbudowany z parametru projektu + licznika configuration
    buildNumberPattern = "%version.prefix%.%build.counter%"

    // "co zostaje po buildzie": lewa strona = ścieżka na agencie, prawa = ścieżka
    // wewnątrz artefaktu. Tu cała zawartość artifacts/build ląduje w katalogu build/.
    artifactRules = "%system.artifacts.dir%/build/** => build"

    steps {
        script {
            name = "Restore + build + publish"
            scriptContent = """
                dotnet restore
                dotnet build --no-restore -c %configuration% -p:Version=%build.number%
                dotnet publish --no-build -c %configuration% -o %system.artifacts.dir%/build
            """.trimIndent()
        }
    }
})

// ---------------------------------------------------------------------------
// ETAP 2: testy. Nie buduje od nowa - bierze gotowy wynik Builda.
// ---------------------------------------------------------------------------
object Test : BuildType({
    templates(DotnetStage)
    name = "2. Test"

    // OVERRIDE: nadpisujemy parametr odziedziczony z szablonu. Testy odpalamy
    // na Debug (pełniejsze asercje), reszta pipeline'u zostaje na Release.
    params {
        param("configuration", "Debug")
    }

    dependencies {
        // Snapshot dependency: "ten build ma sens tylko na tej samej rewizji kodu,
        // co wskazany Build". TeamCity uruchomi Build przed Testem (albo użyje
        // świeżego, jeśli istnieje build z tą samą rewizją).
        snapshot(Build) {
            onDependencyFailure = FailureAction.FAIL_TO_START
        }

        // Artifact dependency: fizycznie ściąga artefakty Builda na agenta Testu.
        artifacts(Build) {
            buildRule = sameChainOrLastFinished()
            artifactRules = "build/** => %system.artifacts.dir%/build"
        }
    }

    steps {
        script {
            name = "Testy"
            scriptContent = """
                dotnet test -c %configuration% --logger "trx;LogFileName=results.trx"
            """.trimIndent()
        }
    }
})

// ---------------------------------------------------------------------------
// ETAP 3: pack + publish. Ostatnie ogniwo łańcucha - dlatego to ono ma trigger.
// ---------------------------------------------------------------------------
object Pack : BuildType({
    templates(DotnetStage)
    name = "3. Pack i publish"

    buildNumberPattern = "%version.prefix%.%build.counter%"
    artifactRules = "%system.artifacts.dir%/nupkg/*.nupkg => nupkg"

    dependencies {
        // Pack czeka na Test, a Test (snapshotem) na Build - stąd cały łańcuch.
        snapshot(Test) {
            onDependencyFailure = FailureAction.FAIL_TO_START
        }
        artifacts(Build) {
            buildRule = sameChainOrLastFinished()
            artifactRules = "build/** => %system.artifacts.dir%/build"
        }
    }

    steps {
        script {
            name = "Pack"
            scriptContent = """
                dotnet pack -c %configuration% -p:Version=%build.number% -o %system.artifacts.dir%/nupkg
            """.trimIndent()
        }
        script {
            name = "Publish do NuGet"
            // %env.NUGET_API_KEY% jest zaszyfrowane; TeamCity maskuje je w logu.
            scriptContent = """
                dotnet nuget push "%system.artifacts.dir%/nupkg/*.nupkg" --api-key "%env.NUGET_API_KEY%" --source https://api.nuget.org/v3/index.json --skip-duplicate
            """.trimIndent()
        }
    }

    triggers {
        // Trigger tylko tutaj: push uruchamia Pack, a snapshot dependencies
        // ściągają za nim Test i Build.
        vcs {
        }
    }
})
