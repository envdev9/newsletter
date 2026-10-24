import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildFeatures.AutoMerge
import jetbrains.buildServer.configs.kotlin.buildFeatures.merge
import jetbrains.buildServer.configs.kotlin.buildSteps.script
import jetbrains.buildServer.configs.kotlin.vcs.GitVcsRoot

// Wydanie #13: cascading merge  feature -> integration -> main
// oraz cloud profile Kubernetes (jedyny "agentowy" artefakt, ktory DSL umie opisac).
// Skladnia zweryfikowana kompilacja wzgledem configs-dsl-kotlin-latest:2025.07
// + repo pluginow zywego serwera TeamCity 2025.07 (zob. ../README.md).
//
// PULAPKA (zmierzona): w KOTLINIE blokowe komentarze SA ZAGNIEZDZANE. Sekwencja
// slash-gwiazdka w srodku komentarza blokowego (np. w nazwie galezi feature/gwiazdka)
// otwiera drugi poziom i reszta pliku zostaje "w komentarzu". Skutek: brak bledu
// kompilacji, ale runtime: "project definition is not found". Dlatego tu komentarze liniowe.

version = "2025.07"

project {

    vcsRoot(CascadeRoot)
    buildType(Verify)

    // --- Cloud profile (Kubernetes) + obraz. DSL opisuje PROFIL i OBRAZ,
    // --- ale NIE opisuje agent pooli: obraz odwoluje sie do puli tylko po ID.
    features {
        kubernetesCloudProfile {
            id = "k8s-demo"
            name = "K8s demo"
            serverURL = "http://teamcity.example.invalid:8111"
            terminateIdleMinutes = 15
            apiServerURL = "https://k8s.example.invalid:6443"
            namespace = "ci"
            authStrategy = token {
                token = "credentialsJSON:00000000-0000-0000-0000-000000000000"
            }
        }
        kubernetesCloudImage {
            id = "k8s-demo-image"
            profileId = "k8s-demo"
            agentPoolId = "-2"            // -2 = "Default" pool; inna pula = jej numeryczne ID z serwera
            agentNamePrefix = "k8s-agent"
            maxInstancesCount = 3
            podSpecification = runContainer {
                dockerImage = "jetbrains/teamcity-agent:2025.07"
            }
        }
    }
}

object CascadeRoot : GitVcsRoot({
    name = "Cascade Root"
    url = "https://example.invalid/demo/newsletter.git"
    branch = "refs/heads/main"
    // Widocznosc gałezi: bez integration i feature/* merge nie ma co budowac.
    branchSpec = """
        +:refs/heads/(feature/*)
        +:refs/heads/(integration)
        +:refs/heads/(main)
    """.trimIndent()
})

object Verify : BuildType({
    name = "Verify"

    vcs { root(CascadeRoot) }

    steps {
        script {
            name = "Test"
            scriptContent = "echo ok"
        }
    }

    features {
        // Etap 1: feature/* -> integration. Build zielony => merge commit (domyslna polityka).
        merge {
            branchFilter = "+:feature/*"
            destinationBranch = "integration"        // NAZWA LOGICZNA wg branchSpec (nawiasy), nie refs/heads/...
            commitMessage = "Auto-merge: %teamcity.build.branch% (build #%build.number%)"
            mergePolicy = AutoMerge.MergePolicy.ALWAYS_MERGE
            mergeCondition = "successful"
            runPolicy = AutoMerge.RunPolicy.AFTER_BUILD_FINISH
        }
        // Etap 2: integration -> main. Wymaga zielonego builda NA integration.
        merge {
            branchFilter = "+:integration"
            destinationBranch = "main"
            commitMessage = "Auto-merge: %teamcity.build.branch% (build #%build.number%)"
            mergePolicy = AutoMerge.MergePolicy.FAST_FORWARD
            mergeCondition = "noNewTests"
            runPolicy = AutoMerge.RunPolicy.BEFORE_BUILD_FINISH
        }
    }
})
