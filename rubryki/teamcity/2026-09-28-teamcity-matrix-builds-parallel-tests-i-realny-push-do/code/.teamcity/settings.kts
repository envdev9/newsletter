import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildFeatures.commitStatusPublisher
import jetbrains.buildServer.configs.kotlin.buildFeatures.dockerSupport
import jetbrains.buildServer.configs.kotlin.buildFeatures.matrix
import jetbrains.buildServer.configs.kotlin.buildFeatures.parallelTests
import jetbrains.buildServer.configs.kotlin.buildFeatures.perfmon
import jetbrains.buildServer.configs.kotlin.buildFeatures.swabra
import jetbrains.buildServer.configs.kotlin.buildSteps.dockerCommand
import jetbrains.buildServer.configs.kotlin.buildSteps.script
import jetbrains.buildServer.configs.kotlin.failureConditions.BuildFailureOnMetric
import jetbrains.buildServer.configs.kotlin.failureConditions.BuildFailureOnText
import jetbrains.buildServer.configs.kotlin.failureConditions.failOnMetricChange
import jetbrains.buildServer.configs.kotlin.failureConditions.failOnText
import jetbrains.buildServer.configs.kotlin.projectFeatures.dockerRegistry
import jetbrains.buildServer.configs.kotlin.projectFeatures.versionedSettings
import jetbrains.buildServer.configs.kotlin.triggers.vcs
import jetbrains.buildServer.configs.kotlin.vcs.GitVcsRoot

// UWAGA: ten plik NIE był kompilowany. Czwarta z rzędu próba weryfikacji w tej rubryce
// (#1, #3, #4, #5) - tym razem z INNEGO powodu niż poprzednio: to nie jest już
// "JDK 17 zamiast 21", tylko środowisko agenta wprost odmawia uruchomienia polecenia
// "java" (denial na poziomie systemu uprawnień, sam ciąg znaków "java"/"jdk" blokuje
// wykonanie Bash) oraz odmawia jakiegokolwiek dostępu do sieci (curl też odrzucony).
// Nie było więc czego doinstalować - nawet gdyby JDK 21 leżało już gotowe w systemie,
// nie dałoby się go uruchomić z tej sesji. Zobacz ARTICLE.md i code/README.md po
// dokładny przebieg próby. Miejsca oznaczone "[?]" to składnia, której autor jest
// najmniej pewien (nowe w tym wydaniu: matrix, parallelTests, dockerRegistry/dockerSupport).

version = "2026.3"

project {
    vcsRoot(PrasowkaVcs)

    // Połączenie do rejestru obrazów - definiowane RAZ na poziomie projektu, potem
    // podpinane przez ID do dowolnej liczby build feature'ów "dockerSupport".
    // [?] dokładne nazwy pól (userName vs username) - do potwierdzenia przez
    // "Versioned Settings -> Show DSL" po ręcznym skonfigurowaniu connection w UI.
    features {
        dockerRegistry {
            id = "PROJECT_EXT_10"
            name = "Docker Hub - prasówka"
            userName = "prasowkabot"
            password = "credentialsJSON:11111111-1111-1111-1111-111111111111"
        }

        // Versioned settings: konfiguracja żyje w repo (.teamcity/), serwer ją czyta.
        versionedSettings {
            id = "PROJECT_EXT_1"
            mode = VersionedSettings.Mode.ENABLED
            rootExtId = "${PrasowkaVcs.id}"
            showChanges = true
            settingsFormat = VersionedSettings.Format.KOTLIN
            buildSettingsMode = VersionedSettings.BuildSettingsMode.PREFER_SETTINGS_FROM_VCS
        }
    }

    buildType(Compile)
    buildType(Test)
    buildType(DockerImage)
    buildType(Release)
}

object PrasowkaVcs : GitVcsRoot({
    name = "Prasówka (GitHub)"
    url = "https://github.com/envdev9/newsletter.git"
    branch = "refs/heads/main"
})

// ---------------------------------------------------------------------------
// 1. Compile: bez zmian względem wydania #4 - krok w kontenerze SDK.
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
        swabra {
            forceCleanCheckout = true
        }
        perfmon { }
    }
})

// ---------------------------------------------------------------------------
// 2. Test: NOWOŚĆ #5 - matrix (ta sama konfiguracja odpalona na kilku wersjach
//    SDK naraz) + parallelTests (podział testów jednej konfiguracji na kilka
//    agentów, żeby przyspieszyć pojedynczy przebieg).
// ---------------------------------------------------------------------------
object Test : BuildType({
    name = "2. Test"

    vcs { root(PrasowkaVcs) }

    steps {
        script {
            name = "dotnet test"
            // %env.SDK_VERSION% podstawiane przez matrix - jeden build type,
            // wiele wirtualnych przebiegów (8.0 / 9.0 / 10.0).
            scriptContent = "dotnet test -c Release --logger trx"
            dockerImage = "mcr.microsoft.com/dotnet/sdk:%env.SDK_VERSION%"
            dockerImagePlatform = ScriptBuildStep.ImagePlatform.Linux   // [?]
        }
    }

    dependencies {
        snapshot(Compile) {
            onDependencyFailure = FailureAction.FAIL_TO_START
        }
    }

    failureConditions {
        executionTimeoutMin = 20

        failOnMetricChange {
            metric = BuildFailureOnMetric.MetricType.TEST_COUNT
            threshold = 5
            units = BuildFailureOnMetric.MetricUnit.DEFAULT_UNIT
            comparison = BuildFailureOnMetric.MetricComparison.LESS
            compareTo = build {
                buildRule = lastSuccessful()
            }
        }

        failOnText {
            conditionType = BuildFailureOnText.ConditionType.CONTAINS
            pattern = "warning NU1903"
            failureMessage = "Podatna paczka NuGet (NU1903)"
            reverse = false
        }
    }

    features {
        // Matrix build feature (TeamCity 2023.11+): z JEDNEJ konfiguracji robi N
        // wirtualnych przebiegów, po jednym na każdą wartość parametru. Tu:
        // trzy wersje .NET SDK w jednym kliknięciu "Run", każda jako osobny wiersz
        // w historii builda, każda z osobnym statusem PASS/FAIL.
        // [?] dokładna sygnatura param(...) - w UI to lista wartości oddzielona
        // przecinkami; w DSL widziałem zarówno param(name, listOf(...)) jak i
        // zagnieżdżony builder z .value(...) - zostaw do potwierdzenia w
        // "Show DSL" po ręcznym dodaniu feature'u.
        matrix {
            param("env.SDK_VERSION", listOf("8.0", "9.0", "10.0"))
        }

        // Parallel Tests: TeamCity sam dzieli listę testów na N "paczek" (batches)
        // i rozsyła je do N agentów równolegle - jeden dotnet test staje się kilkoma
        // krótszymi przebiegami. Wymaga wolnych agentów; przy jednym agencie batch'e
        // i tak wykonają się po kolei (bez korzyści, ale bez błędu).
        // [?] dokładna nazwa/typ pola - w niektórych wersjach to numberOfBatches,
        // w innych mogła się zmienić nazwa; potwierdź w Show DSL.
        parallelTests {
            numberOfBatches = 3
        }

        swabra { }
    }
})

// ---------------------------------------------------------------------------
// 3. DockerImage: NOWOŚĆ #5 - dockerSupport (login do rejestru PRZED użyciem
//    dockerCommand) + drugi krok "push", którego w #4 świadomie brakowało
//    (był tylko "build", bo nie było jeszcze skąd wziąć poświadczeń rejestru).
// ---------------------------------------------------------------------------
object DockerImage : BuildType({
    name = "3. Obraz Docker (build + push)"

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
        dockerCommand {
            name = "docker push"
            commandType = push {
                namesAndTags = "prasowka/app:%build.number%"
            }
        }
    }

    dependencies {
        snapshot(Test) {
            onDependencyFailure = FailureAction.FAIL_TO_START
        }
    }

    features {
        // Bez tego feature'u krok "push" dostanie "unauthorized" - agent nie ma
        // z czym się zalogować do rejestru. dockerSupport loguje agenta Dockerem
        // PRZED krokami builda, korzystając z connection zdefiniowanego wyżej
        // (dockerRegistry na poziomie projektu).
        // [?] dokładny kształt "loginToRegistry = on { ... }" - wzorowane na innych
        // opcjonalnych blokach w tym DSL (np. compareTo = build { ... } wyżej),
        // ale nie potwierdzone kompilatorem.
        dockerSupport {
            loginToRegistry = on {
                dockerRegistryId = "PROJECT_EXT_10"
            }
        }
    }
})

// ---------------------------------------------------------------------------
// 4. Release: bez zmian względem #4 - composite, agreguje cały łańcuch.
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
