import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildFeatures.commitStatusPublisher
import jetbrains.buildServer.configs.kotlin.buildFeatures.perfmon
import jetbrains.buildServer.configs.kotlin.buildFeatures.swabra
import jetbrains.buildServer.configs.kotlin.buildSteps.dockerCommand
import jetbrains.buildServer.configs.kotlin.buildSteps.script
import jetbrains.buildServer.configs.kotlin.failureConditions.BuildFailureOnMetric
import jetbrains.buildServer.configs.kotlin.failureConditions.BuildFailureOnText
import jetbrains.buildServer.configs.kotlin.failureConditions.failOnMetricChange
import jetbrains.buildServer.configs.kotlin.failureConditions.failOnText
import jetbrains.buildServer.configs.kotlin.projectFeatures.versionedSettings
import jetbrains.buildServer.configs.kotlin.triggers.vcs
import jetbrains.buildServer.configs.kotlin.vcs.GitVcsRoot

// UWAGA: ten plik NIE był kompilowany (brak dostępu do JDK 21 / Maven w środowisku
// autora). Składnia pochodzi z dokumentacji Kotlin DSL i pamięci; miejsca oznaczone
// "[?]" są tymi, których autor jest najmniej pewien. Patrz ARTICLE.md.

version = "2026.3"

project {
    vcsRoot(PrasowkaVcs)

    buildType(Compile)
    buildType(Test)
    buildType(DockerImage)
    buildType(Release)

    features {
        // Versioned settings: konfiguracja żyje w repo (.teamcity/), serwer ją czyta.
        // [?] dokładne nazwy enumów Mode/Format/BuildSettingsMode
        versionedSettings {
            id = "PROJECT_EXT_1"
            mode = VersionedSettings.Mode.ENABLED
            rootExtId = "${PrasowkaVcs.id}"
            showChanges = true
            settingsFormat = VersionedSettings.Format.KOTLIN
            buildSettingsMode = VersionedSettings.BuildSettingsMode.PREFER_SETTINGS_FROM_VCS
        }
    }
}

object PrasowkaVcs : GitVcsRoot({
    name = "Prasówka (GitHub)"
    url = "https://github.com/envdev9/newsletter.git"
    branch = "refs/heads/main"
})

// ---------------------------------------------------------------------------
// 1. Compile: krok skryptowy uruchomiony W KONTENERZE (Docker wrapper).
//    Agent nie potrzebuje zainstalowanego .NET SDK - tylko Dockera.
// ---------------------------------------------------------------------------
object Compile : BuildType({
    name = "1. Compile (w kontenerze SDK)"

    vcs { root(PrasowkaVcs) }

    steps {
        script {
            name = "dotnet build w obrazie SDK"
            scriptContent = "dotnet build -c Release"
            dockerImage = "mcr.microsoft.com/dotnet/sdk:9.0"
            dockerImagePlatform = ScriptBuildStep.ImagePlatform.Linux   // [?]
            dockerPull = true
        }
    }

    features {
        // Swabra: sprząta pliki, które build zostawił na agencie, i wykrywa
        // pliki niezwolnione przez proces (locked files).
        swabra {
            forceCleanCheckout = true
        }
        // Perfmon: wykresy CPU/RAM/dysk agenta w zakładce Performance Monitor.
        perfmon { }
    }
})

// ---------------------------------------------------------------------------
// 2. Test: failure conditions - kiedy build ma paść mimo "zielonych" kroków.
// ---------------------------------------------------------------------------
object Test : BuildType({
    name = "2. Test"

    vcs { root(PrasowkaVcs) }

    steps {
        script {
            name = "dotnet test"
            scriptContent = "dotnet test -c Release --logger trx"
            dockerImage = "mcr.microsoft.com/dotnet/sdk:9.0"
            dockerImagePlatform = ScriptBuildStep.ImagePlatform.Linux   // [?]
        }
    }

    dependencies {
        snapshot(Compile) {
            onDependencyFailure = FailureAction.FAIL_TO_START
        }
    }

    failureConditions {
        // twardy limit czasu: zawieszony test nie blokuje agenta w nieskończoność
        executionTimeoutMin = 20

        // build pada, gdy liczba testów SPADNIE o więcej niż 5 względem ostatniego
        // udanego builda (ktoś "przypadkiem" wyłączył pół projektu testowego)
        // [?] dokładne nazwy pól: threshold / units / comparison / compareTo
        failOnMetricChange {
            metric = BuildFailureOnMetric.MetricType.TEST_COUNT
            threshold = 5
            units = BuildFailureOnMetric.MetricUnit.DEFAULT_UNIT
            comparison = BuildFailureOnMetric.MetricComparison.LESS
            compareTo = build {
                buildRule = lastSuccessful()
            }
        }

        // build pada, gdy w logu pojawi się wzorzec, nawet przy exit code 0
        // [?] nazwy ConditionType / pola reverse
        failOnText {
            conditionType = BuildFailureOnText.ConditionType.CONTAINS
            pattern = "warning NU1903"
            failureMessage = "Podatna paczka NuGet (NU1903)"
            reverse = false
        }
    }
})

// ---------------------------------------------------------------------------
// 3. DockerImage: dedykowany krok dockerCommand (build obrazu z Dockerfile).
//    Wymaga Dockerfile w repo aplikacji.
// ---------------------------------------------------------------------------
object DockerImage : BuildType({
    name = "3. Obraz Docker"

    vcs { root(PrasowkaVcs) }

    steps {
        dockerCommand {
            name = "docker build"
            commandType = build {
                source = file {
                    path = "Dockerfile"
                }
                namesAndTags = "prasowka/app:%build.number%"
            }
        }
    }

    dependencies {
        snapshot(Test) {
            onDependencyFailure = FailureAction.FAIL_TO_START
        }
    }
})

// ---------------------------------------------------------------------------
// 4. Release: COMPOSITE build - nie ma kroków ani własnego agenta. To "parasol",
//    który agreguje wynik całego łańcucha w JEDEN status (np. na commicie).
// ---------------------------------------------------------------------------
object Release : BuildType({
    name = "4. Release (composite)"
    type = BuildTypeSettings.Type.COMPOSITE

    vcs { root(PrasowkaVcs) }

    dependencies {
        snapshot(DockerImage) {
            onDependencyFailure = FailureAction.FAIL_TO_START
        }
    }

    triggers {
        vcs { }
    }

    features {
        // Jeden zielony/czerwony znaczek na commicie w GitHubie - z całego łańcucha.
        // Token to odwołanie do sekretu na serwerze (UUID fikcyjny).
        // [?] kształt bloku publisher = github { authType = personalToken { ... } }
        commitStatusPublisher {
            vcsRootExtId = "${PrasowkaVcs.id}"
            publisher = github {
                githubUrl = "https://api.github.com"
                authType = personalToken {
                    token = "credentialsJSON:00000000-0000-0000-0000-000000000000"
                }
            }
        }
    }
})
