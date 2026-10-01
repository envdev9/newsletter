import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildFeatures.AutoMerge
import jetbrains.buildServer.configs.kotlin.buildFeatures.PullRequests
import jetbrains.buildServer.configs.kotlin.buildFeatures.commitStatusPublisher
import jetbrains.buildServer.configs.kotlin.buildFeatures.dockerSupport
import jetbrains.buildServer.configs.kotlin.matrix
import jetbrains.buildServer.configs.kotlin.buildFeatures.merge
import jetbrains.buildServer.configs.kotlin.buildFeatures.parallelTests
import jetbrains.buildServer.configs.kotlin.buildFeatures.perfmon
import jetbrains.buildServer.configs.kotlin.buildFeatures.pullRequests
import jetbrains.buildServer.configs.kotlin.buildFeatures.swabra
import jetbrains.buildServer.configs.kotlin.buildSteps.ScriptBuildStep
import jetbrains.buildServer.configs.kotlin.buildSteps.dockerCommand
import jetbrains.buildServer.configs.kotlin.buildSteps.script
import jetbrains.buildServer.configs.kotlin.failureConditions.BuildFailureOnMetric
import jetbrains.buildServer.configs.kotlin.failureConditions.BuildFailureOnText
import jetbrains.buildServer.configs.kotlin.failureConditions.failOnMetricChange
import jetbrains.buildServer.configs.kotlin.failureConditions.failOnText
import jetbrains.buildServer.configs.kotlin.projectFeatures.dockerRegistry
import jetbrains.buildServer.configs.kotlin.triggers.vcs
import jetbrains.buildServer.configs.kotlin.vcs.GitVcsRoot

// ===========================================================================
// TEN PLIK TO DOSŁOWNA, NIEZMIENIONA KOPIA TEGO, CO DAŁO PRAWDZIWY
// "BUILD SUCCESS" W TEJ SESJI (wydanie #8, 2026-10-01) - PIERWSZY RAZ W 8
// WYDANIACH TEJ RUBRYKI, ŻE CAŁY ŁAŃCUCH (5 build type'ów, wszystkie
// buildFeatures/triggers/steps z edycji #3-#8) REALNIE SKOMPILOWAŁ SIĘ
// przez "teamcity-configs-maven-plugin" - przeciw PRAWDZIWYM, per-pluginowym
// klasom DSL serwowanym przez ŻYWY serwer TeamCity (jetbrains/teamcity-server
// :2025.07 w Dockerze), nie przez publiczny generyczny szkielet.
//
// Różnice względem idiomatycznego "../../.teamcity/settings.kts" (ten sam
// projekt, ale pisany jako "wzorcowy, pełny przykład" dla czytelnika):
//   1. version = "2025.07" (nie "2026.1") - serwer odrzuca nieznaną wersję.
//   2. BRAK "versionedSettings{}" - JEDYNA rzecz z całego pliku, która mimo
//      poprawnej składni NIE PRZECHODZI w trybie standalone/offline tego
//      narzędzia ("Versioned settings project feature cannot be used in
//      relative project hierarchy" - błąd walidacji runtime, nie kompilacji;
//      na żywym serwerze, z prawdziwym projektem w drzewie, działa bez
//      problemu - potwierdzone REST-em w code/README.md, sekcja 2/3).
//   3. 4 poprawki błędów, które były NIEWIDOCZNE w #5/#6/#7 (bo tam kod
//      nigdy nie dotarł do etapu, w którym kompilator mógłby je zgłosić):
//      - "matrix" jest w pakiecie jetbrains.buildServer.configs.kotlin
//        (NIE .buildFeatures) - zły import od co najmniej #5.
//      - "ScriptBuildStep" (używane jako ScriptBuildStep.ImagePlatform.Linux)
//        wymaga WŁASNEGO importu - nigdy nie był importowany.
//      - "VersionedSettings" (klasa, nie tylko funkcja "versionedSettings")
//        wymaga WŁASNEGO importu dla VersionedSettings.Mode/.Format/...
//      - MatrixFeature.param(name, List<String>) NIE ISTNIEJE - prawdziwa
//        sygnatura to param(name, List<MatrixFeature.Value>), Value przez
//        helper value(label, value).
//
// Pełny log komend (docker pull/run teamcity-server, RSA/PKCS1 logowanie,
// REST API, maven:3.9-eclipse-temurin-21 --network host + prawdziwy log
// "BUILD SUCCESS"): code/README.md, sekcja 2 i 3.
// ===========================================================================

version = "2025.07"

project {
    vcsRoot(PrasowkaVcs)

    features {
        dockerRegistry {
            id = "PROJECT_EXT_10"
            name = "Docker Hub - prasówka"
            userName = "prasowkabot"
            password = "credentialsJSON:11111111-1111-1111-1111-111111111111"
        }

        // versionedSettings{} USUNIĘTE w tym pliku - zob. komentarz na górze
        // i ARTICLE.md. To JEDYNA rzecz z całego configu, która nie przechodzi
        // walidacji w trybie standalone (nie z powodu braku klas).
    }

    buildType(Compile)
    buildType(Test)
    buildType(IntegrationTest)
    buildType(DockerImage)
    buildType(Release)
}

object PrasowkaVcs : GitVcsRoot({
    name = "Prasówka (GitHub)"
    url = "https://github.com/envdev9/newsletter.git"
    branch = "refs/heads/main"
    branchSpec = """
        +:refs/heads/*
        +:refs/pull/*/head
    """.trimIndent()
})

object Compile : BuildType({
    name = "1. Compile (w kontenerze SDK)"

    vcs {
        root(PrasowkaVcs)
        branchFilter = """
            +:*
            -:<default>
        """.trimIndent()
    }

    steps {
        script {
            name = "dotnet build w obrazie SDK"
            scriptContent = "dotnet build -c Release"
            dockerImage = "mcr.microsoft.com/dotnet/sdk:9.0"
            dockerImagePlatform = ScriptBuildStep.ImagePlatform.Linux
            dockerPull = true
        }
    }

    triggers {
        vcs {
            branchFilter = """
                +:<default>
                +:refs/pull/*/head
            """.trimIndent()
        }
    }

    features {
        swabra {
            forceCleanCheckout = true
        }
        perfmon { }

        pullRequests {
            vcsRootExtId = "${PrasowkaVcs.id}"
            provider = github {
                authType = token {
                    token = "credentialsJSON:22222222-2222-2222-2222-222222222222"
                }
                filterAuthorRole = PullRequests.GitHubRoleFilter.MEMBER
                filterTargetBranch = "+:refs/heads/main"
                ignoreDrafts = true
            }
        }

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

object Test : BuildType({
    name = "2. Test"

    vcs { root(PrasowkaVcs) }

    steps {
        script {
            name = "dotnet test"
            scriptContent = "dotnet test -c Release --logger trx"
            dockerImage = "mcr.microsoft.com/dotnet/sdk:%env.SDK_VERSION%"
            dockerImagePlatform = ScriptBuildStep.ImagePlatform.Linux
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
        matrix {
            // Prawdziwa sygnatura MatrixFeature.param (potwierdzona javap-em):
            // param(name: String, values: List<MatrixFeature.Value>).
            param("env.SDK_VERSION", listOf(value("8.0", "8.0"), value("9.0", "9.0"), value("10.0", "10.0")))
        }

        parallelTests {
            numberOfBatches = 3
        }

        swabra { }
    }
})

object IntegrationTest : BuildType({
    name = "3. Integration Test (docker-compose)"

    vcs { root(PrasowkaVcs) }

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

    failureConditions {
        executionTimeoutMin = 15
    }

    features {
        swabra { }
    }
})

object DockerImage : BuildType({
    name = "4. Obraz Docker (build + push)"

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
        snapshot(IntegrationTest) {
            onDependencyFailure = FailureAction.FAIL_TO_START
        }
    }

    features {
        dockerSupport {
            loginToRegistry = on {
                dockerRegistryId = "PROJECT_EXT_10"
            }
        }
    }
})

object Release : BuildType({
    name = "5. Release (composite)"
    type = BuildTypeSettings.Type.COMPOSITE

    vcs {
        root(PrasowkaVcs)
        branchFilter = """
            +:*
            -:<default>
        """.trimIndent()
    }

    dependencies {
        snapshot(DockerImage) {
            onDependencyFailure = FailureAction.FAIL_TO_START
        }
    }

    triggers {
        vcs {
            branchFilter = """
                +:<default>
                +:refs/pull/*/head
            """.trimIndent()
        }
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

        merge {
            branchFilter = "+:refs/pull/*/head"
            destinationBranch = "refs/heads/main"
            mergePolicy = AutoMerge.MergePolicy.FAST_FORWARD
            mergeCondition = "noNewTests"
            runPolicy = AutoMerge.RunPolicy.BEFORE_BUILD_FINISH
        }
    }
})
