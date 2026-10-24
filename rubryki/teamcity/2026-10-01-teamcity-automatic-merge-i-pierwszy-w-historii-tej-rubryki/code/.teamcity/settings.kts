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
import jetbrains.buildServer.configs.kotlin.projectFeatures.VersionedSettings
import jetbrains.buildServer.configs.kotlin.projectFeatures.dockerRegistry
import jetbrains.buildServer.configs.kotlin.projectFeatures.versionedSettings
import jetbrains.buildServer.configs.kotlin.triggers.vcs
import jetbrains.buildServer.configs.kotlin.vcs.GitVcsRoot

// UWAGA (wydanie #8, 2026-10-01): status kompilacji TEGO PLIKU wzgledem #7 NIE ZMIENIL
// SIE co do WYNIKU dla sciezki "offline, przez teamcity-configs-maven-plugin + publiczny
// artefakt configs-dsl-kotlin-latest:2026.3-dsl6" - wciaz BUILD FAILURE, z tych samych
// powodow co w #7 (ten jar to tylko recznie pisany szkielet, zero klas pluginowych).
//
// ALE dzis osiagnieto NASTEPNY, NAJGLEBSZY jak dotad poziom weryfikacji - zamiast
// wnioskowac z NIEOBECNOSCI klas w jarze (#7), postawiono i faktycznie uruchomiono
// PRAWDZIWY serwer TeamCity (obraz "jetbrains/teamcity-server:2025.07" w Dockerze),
// przeszedl przez caly jego kreator pierwszego startu (w tym recznie
// zaimplementowane w Pythonie szyfrowanie RSA/PKCS1 hasla administratora - serwer
// wymaga tego do przyjecia hasla, zob. code/README.md sekcja 2), stworzono projekt +
// VCS root + build type + REALNY build feature "AutoMergeFeature" przez REST API, i
// user'em "Admin -> Versioned Settings -> Download settings in Kotlin format..."
// (prawdziwy mechanizm "Show DSL") POBRANO Z SERWERA prawdziwy, wygenerowany plik
// .kt dla tego build type - zawiera DOKLADNIE klase "AutoMerge" i funkcje "merge{}"
// uzyte nizej, 1:1. To POTWIERDZA hipoteze z #7 w sposob, ktory nie wymaga juz zadnych
// domyslen: serwer generuje te klasy Z (a) swoich 95 wbudowanych pluginow + (b) ich
// deklaratywnych opisow XML (np. "kotlin-dsl/buildFeatures/AutoMerge.xml" - znaleziony
// dzis NIEZALEZNIE rowniez w lokalnym, juz istniejacym cache'u ~/.m2, w jarze
// "server-core-2026.3-DSL-eap2-SNAPSHOT.jar"), i NIGDY nie publikuje ich do zwyklego
// Maven Central / download.jetbrains.com jako czesci "configs-dsl-kotlin-latest" -
// zamiast tego serwer wystawia WLASNE, efemeryczne repozytorium Maven
// ("http://localhost:8111/app/dsl-plugins-repository", widoczne w pom.xml generowanym
// przez "Show DSL") z dodatkowym artefaktem "configs-dsl-kotlin-plugins-latest" -
// DOKLADNIE ten "nieznaleziony dotad w publicznym repo" element, o ktorym mowil
// STATE.md jako "nastepny krok". Pelny log calej sesji (REST, RSA, zawartosc ZIP-a z
// "Show DSL"): code/README.md, sekcja 2.
//
// NOWOSC #8 (temat merytoryczny): build feature "Automatic Merge" (merge{}) na
// "Release" - patrz sekcja 2 nizej. "mergeCondition" i "commitMessage" to typ String
// (NIE enum, mimo ze klasa AutoMerge deklaruje enum AutoMerge.MergeCondition!),
// "mergePolicy"/"runPolicy" to typowane enumy - potwierdzone trzema zrodlami (XML
// descriptor, Dokka docs, i TEN KONKRETNY wygenerowany przez zywy serwer plik .kt).
// Dodatkowo odkryto: generator "Show DSL" POMIJA jawne przypisanie wlasciwosci, gdy
// jej wartosc rowna sie DOMYSLNEJ (sprawdzone empirycznie - zob. ARTICLE.md).

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

        // UWAGA #8: to JEDYNY fragment całego pliku, który kompiluje się (importy/typy
        // sie zgadzaja), ALE nie przechodzi walidacji w trybie STANDALONE
        // (teamcity-configs-maven-plugin poza żywym serwerem) - błąd runtime "Versioned
        // settings project feature cannot be used in relative project hierarchy".
        // Potwierdzone dzis na żywym serwerze (code/README.md, sekcja 2/3): DOKŁADNIE
        // TEN SAM feature, dodany przez REST API na prawdziwym projekcie (a nie
        // wygenerowany z izolowanego pliku .kts bez prawdziwego rodzica w drzewie
        // projektów), działa bez żadnego błędu - to ograniczenie samego trybu
        // offline/standalone tego narzędzia, NIE błąd w składni poniżej.
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
    buildType(IntegrationTest)
    buildType(DockerImage)
    buildType(Release)
}

// ---------------------------------------------------------------------------
// VCS root: bez zmian względem #7 - branchSpec z "+:refs/pull/*/head".
// ---------------------------------------------------------------------------
object PrasowkaVcs : GitVcsRoot({
    name = "Prasówka (GitHub)"
    url = "https://github.com/envdev9/newsletter.git"
    branch = "refs/heads/main"
    branchSpec = """
        +:refs/heads/*
        +:refs/pull/*/head
    """.trimIndent()
})

// ---------------------------------------------------------------------------
// 1. Compile: bez zmian względem #7 - PR detection (pullRequests) +
//    commitStatusPublisher na najwcześniejszym kroku łańcucha.
// ---------------------------------------------------------------------------
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
            dockerImagePlatform = ScriptBuildStep.ImagePlatform.Linux   // POTWIERDZONE #8 (javap, zob. README.md) - nie [?] jak w #5-#7
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

// ---------------------------------------------------------------------------
// 2. Test: bez zmian względem wydania #5/#6/#7.
// ---------------------------------------------------------------------------
object Test : BuildType({
    name = "2. Test"

    vcs { root(PrasowkaVcs) }

    steps {
        script {
            name = "dotnet test"
            scriptContent = "dotnet test -c Release --logger trx"
            dockerImage = "mcr.microsoft.com/dotnet/sdk:%env.SDK_VERSION%"
            dockerImagePlatform = ScriptBuildStep.ImagePlatform.Linux   // POTWIERDZONE #8 (javap, zob. README.md) - nie [?] jak w #5-#7
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
            // NAPRAWIONE #8: "param(name, List<String>)" NIE ISTNIEJE - realna sygnatura
            // (potwierdzona dzis przez javap na prawdziwym jarze, zob. code/README.md) to
            // "param(name: String, values: List<MatrixFeature.Value>)", gdzie "Value" sie
            // tworzy przez helper "value(label, value)". W #5/#6/#7 ten kod wygladal
            // "poprawnie" tylko dlatego, ze NIGDY nie dotarl do etapu, w ktorym kompilator
            // mogl to sprawdzic (caly import byl Unresolved).
            param("env.SDK_VERSION", listOf(value("8.0", "8.0"), value("9.0", "9.0"), value("10.0", "10.0")))
        }

        parallelTests {
            numberOfBatches = 3
        }

        swabra { }
    }
})

// ---------------------------------------------------------------------------
// 3. IntegrationTest: bez zmian względem wydania #6/#7.
// ---------------------------------------------------------------------------
object IntegrationTest : BuildType({
    name = "3. Integration Test (docker-compose)"

    vcs { root(PrasowkaVcs) }

    steps {
        step {
            name = "docker-compose up (integration tests)"
            type = "DockerCompose"                                        // [?]
            param("dockerCompose.file", "docker-compose.integration.yml") // [?]
            param("dockerCompose.forcePull", "true")                      // [?]
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

// ---------------------------------------------------------------------------
// 4. DockerImage: bez zmian względem wydania #5/#6/#7.
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// 5. Release: composite, agreguje cały łańcuch. GŁÓWNY TEMAT #8: dołożono
//    "branchFilter" na vcs{}/trigger (mirror wzorca z "Compile" w #7), BO
//    Automatic Merge ma sens tylko na build type, który faktycznie widzi i
//    buduje gałęzie PR-ów - nie tylko "main". Bez tego rozszerzenia "merge{}"
//    nigdy nie dostałby builda z gałęzi PR-a, na którym mógłby zadziałać.
// ---------------------------------------------------------------------------
object Release : BuildType({
    name = "5. Release (composite)"
    type = BuildTypeSettings.Type.COMPOSITE

    vcs {
        root(PrasowkaVcs)

        // NOWOSC #8: bez tego Release "widzialby" tylko commity do "main" -
        // tak jak w #4-#7 - i nigdy nie zbudowalby sie na galezi PR-a, przez
        // co "merge{}" nizej nigdy nie mialby czego mergowac.
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
            // NOWOSC #8: rozszerzone o galezie PR-ow, analogicznie do "Compile"
            // w #7 - "Release" (koniec calego lancucha) musi widziec PR-y, zeby
            // feature "merge" mial kiedykolwiek szanse zadzialac.
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

        // ===================================================================
        // GLOWNY TEMAT #8: build feature "Automatic Merge".
        // ===================================================================
        // [dsl-doc]: jetbrains.buildServer.configs.kotlin.buildFeatures.AutoMerge,
        // pobrane dzis z teamcity.jetbrains.com/app/dsl-documentation/buildFeatures/
        // auto-merge/index.html (TeamCity Kotlin DSL 2026.2.1) - ZNALEZIONE poprzez
        // najpierw stronę jetbrains.com/help/teamcity/pull-requests.html (gdzie jest
        // wspomniane jako "Pro Tip" razem z feature'em Pull Requests, tak jak
        // zasygnalizowano w #7), potem jej link "automatic-merge.html", potem
        // dopiero (bo DSL-owa strona NIE jest linkowana z user-docs) przeszukanie
        // indeksu "buildFeatures/index.html" po słowie "merge" -> "auto-merge".
        // Opis z user-docs (jetbrains.com/help/teamcity/automatic-merge.html),
        // zacytowany doslownie: "The Automatic Merge build feature tracks builds
        // in branches matched by the configured filter and merges them into a
        // specified destination branch if the build satisfies the condition
        // configured (for example, the build is successful)."
        merge {
            // branchFilter: ktore (logiczne) galezie sa OBSERWOWANE jako zrodlo
            // do mergowania - tu wylacznie galezie PR-ow (widoczne dzieki
            // VcsRoot.branchSpec + rozszerzonym branchFilter powyzej).
            branchFilter = "+:refs/pull/*/head"

            // destinationBranch: logiczna nazwa galezi docelowej - musi byc
            // obecna w repo i w Branch Specification VCS roota (tak jak main
            // juz jest, przez "branch = refs/heads/main").
            destinationBranch = "refs/heads/main"

            // mergePolicy: TYPOWANY enum AutoMerge.MergePolicy - FAST_FORWARD
            // = preferuj fast-forward (brak zbednego commita mergujacego), gdy
            // to mozliwe; ALWAYS_MERGE = zawsze twórz commit mergujący.
            mergePolicy = AutoMerge.MergePolicy.FAST_FORWARD

            // mergeCondition: UWAGA - to pole jest typu String (NIE typowanym
            // enumem AutoMerge.MergeCondition, mimo że klasa AutoMerge deklaruje
            // taki enum!). Potwierdzone TRZEMA niezaleznymi zrodlami dzis: (1)
            // zrodlowy deskryptor XML (kotlin-dsl/buildFeatures/AutoMerge.xml,
            // wewnatrz server-core-2026.3-DSL-eap2-SNAPSHOT.jar z lokalnego
            // cache'u ~/.m2 - param "teamcity.automerge.buildStatusCondition"
            // NIE ma atrybutu "type", w odroznieniu od "mergePolicy"/"runPolicy",
            // ktore MAJA type="MergePolicy"/type="RunPolicy"); (2) strona Dokka
            // (przyklad uzywa doslownie "noNewTests"); (3) NAJSILNIEJSZE: realny
            // serwer TeamCity (jetbrains/teamcity-server:2025.07 w Dockerze,
            // zob. code/README.md sekcja 2) - projekt+buildType+feature
            // "AutoMergeFeature" zrobiony przez REST API, potem realne
            // "Admin -> Versioned Settings -> Download settings in Kotlin
            // format" ZWROCILO doslownie "mergeCondition = "noNewTests"" (string,
            // nie enum) dla param "teamcity.automerge.buildStatusCondition" =
            // "noNewTests". Dozwolone surowe wartosci (z XML): "successful"
            // (SUCCESSFUL_BUILD) albo "noNewTests" (NO_NEW_FAILED_TESTS).
            mergeCondition = "noNewTests"

            // runPolicy: TYPOWANY enum AutoMerge.RunPolicy - potwierdzone tym
            // samym testem na zywym serwerze (param "teamcity.automerge.run.policy"
            // = "runBeforeBuildFinish" -> wygenerowany Kotlin:
            // "runPolicy = AutoMerge.RunPolicy.BEFORE_BUILD_FINISH"). WAZNA
            // DODATKOWA OBSERWACJA z tego samego testu: gdy ustawiono WARTOSCI
            // DOMYSLNE (buildStatusCondition="successful", run.policy=
            // "runAfterBuildFinish"), generator "Show DSL" CALKOWICIE POMIJA te
            // dwie linie w wygenerowanym Kotlinie (zamiast wypisac je jawnie) -
            // czyli "domyslne" wartosci tego build feature'u to WLASNIE
            // SUCCESSFUL_BUILD i AFTER_BUILD_FINISH, i serwer generuje kod
            // "idiomatycznie" (bez zaśmiecania jawnymi domyślnymi wartosciami).
            // Tu uzyto NIEdomyslnej wartosci (BEFORE_BUILD_FINISH) wylacznie
            // zeby pokazac pole w akcji - w praktyce dla "Release" (koniec
            // łańcucha, nikt nie czeka na merge) domyślne AFTER_BUILD_FINISH
            // jest lepszym wyborem.
            runPolicy = AutoMerge.RunPolicy.BEFORE_BUILD_FINISH
        }
    }
})
