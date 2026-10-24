import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildFeatures.PullRequests
import jetbrains.buildServer.configs.kotlin.buildFeatures.commitStatusPublisher
import jetbrains.buildServer.configs.kotlin.buildFeatures.dockerSupport
import jetbrains.buildServer.configs.kotlin.buildFeatures.matrix
import jetbrains.buildServer.configs.kotlin.buildFeatures.parallelTests
import jetbrains.buildServer.configs.kotlin.buildFeatures.perfmon
import jetbrains.buildServer.configs.kotlin.buildFeatures.pullRequests
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

// UWAGA (wydanie #7, 2026-09-30): ten plik dalej NIE zostal skompilowany w calosci przez
// teamcity-configs-maven-plugin - to siodma proba z rzedu (#1, #3, #4, #5, #6, #7) - ALE
// dzisiaj po raz pierwszy w historii tej rubryki: (a) srodowisko sesji NAPRAWDE uruchomilo
// realny "mvn compile" z realnym JDK 21 i realnym Mavenem (obejscie ograniczen z #6 - zob.
// ARTICLE.md sekcja 1), (b) dzieki temu ustalono NOWA, precyzyjna przyczyne, dla ktorej TEN
// KONKRETNY plik (i wszystkie poprzednie, #1-#6) i tak by sie nie skompilowal, nawet z
// dzialajacym JDK 21 + Mavenem + siecia: publicznie pobieralny artefakt
// "configs-dsl-kotlin-latest:2026.3-dsl6" z download.jetbrains.com zawiera WYLACZNIE
// generyczny szkielet DSL (Project, BuildType, Dependencies, bazowe klasy VcsRoot/
// Trigger/BuildFeature, i - z wyjatku - wbudowany "matrix") - NIE zawiera konkretnych,
// kontrybuowanych przez poszczegolne pluginy funkcji/klas uzywanych ponizej: GitVcsRoot,
// vcs{} (trigger), script/dockerCommand (kroki), swabra/perfmon/commitStatusPublisher/
// dockerRegistry/dockerSupport/versionedSettings/parallelTests/pullRequests (feature'y).
// Dowod: zrzut listy klas .class wewnatrz pobranego .jar (zob. code/README.md) pokazuje
// zero plikow w pakietach "buildFeatures"/"buildSteps"/"triggers"/"vcs"/"projectFeatures" -
// tylko plaski pakiet "jetbrains.buildServer.configs.kotlin" z klasami bazowymi. Realna
// proba "mvn compile" na TYM pliku konczy sie seria "Unresolved reference: buildFeatures"
// juz na liniach z importami (2-17) - pelny log w code/README.md. Skladnia ponizej jest
// mimo to WIARYGODNA nie z pamieci/zgadywania, tylko z live'owej, aktualnej (2026.2.1)
// dokumentacji Kotlin DSL pobranej dzis z teamcity.jetbrains.com/app/dsl-documentation/
// (patrz przypisy [dsl-doc] przy kazdym nowym fragmencie) - to najsilniejsze zrodlo, jakie
// ta rubryka miala w 7 wydaniach. Osobny, MINIMALNY plik (code/compile-proof/.teamcity/
// settings.kts), zbudowany WYLACZNIE z klas bazowych faktycznie obecnych w jarze, zostal
// dzis skompilowany z sukcesem (BUILD SUCCESS + realny wygenerowany XML) - to pierwszy
// prawdziwy "zielony" kompil w calej historii tej rubryki. Zob. ARTICLE.md sekcja 1.

version = "2026.1"

project {
    vcsRoot(PrasowkaVcs)

    features {
        dockerRegistry {
            id = "PROJECT_EXT_10"
            name = "Docker Hub - prasówka"
            userName = "prasowkabot"
            password = "credentialsJSON:11111111-1111-1111-1111-111111111111"
        }

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
// VCS root: NOWOSC #7 - "branchSpec" z "+:refs/pull/*/head". Bez tego wpisu
// gałęzie pull requestów w ogóle nie są widoczne dla TeamCity - "branchSpec"
// VCS roota to WARSTWA NIZSZA niz feature "Pull Requests": decyduje, KTORE
// galezie serwer w ogole widzi i sledzi; dopiero pozniej "Pull Requests" (na
// buildzie) i "branchFilter" (na triggerze/vcs-settings buildu) decyduja, ktore
// z widocznych galezi sa "obserwowane" jako PR-y i ktore z nich faktycznie
// odpalaja build. Trzy rozne warstwy filtrowania, celowo w tej kolejnosci:
//   1. VcsRoot.branchSpec       - co serwer w ogole WIDZI (ta sekcja)
//   2. BuildFeatures.pullRequests + jego filterAuthorRole/filterTargetBranch
//                               - ktore widoczne galezie sa "pull requestem"
//                                 i przechodza test zaufania (autor, branch)
//   3. Triggers.vcs.branchFilter (albo VcsSettings.branchFilter na buildzie)
//                               - ktore z NICH faktycznie odpalaja nowy build
// [dsl-doc]: sekcja "Interaction with VCS Roots" w oficjalnej dokumentacji
// (jetbrains.com/help/teamcity/pull-requests.html, pobrane dzis) pokazuje
// dokladnie ten wzorzec "branchSpec" na VcsRoot.
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
// 1. Compile: rdzen bez zmian wzgledem #4/#5/#6 (krok w kontenerze SDK) - ALE
//    to tutaj, na NAJWCZESNIEJSZYM etapie łańcucha, dolozono dzis feature'y
//    zwiazane z pull requestami. Sens: PR chcemy odrzucic/zaakceptowac jak
//    najszybciej i jak najtaniej - Compile jest pierwszym i najszybszym
//    krokiem, wiec to naturalne miejsce na "bramkę" PR-owa, zanim cokolwiek
//    droższego (Test/IntegrationTest/DockerImage) w ogóle wystartuje.
// ---------------------------------------------------------------------------
object Compile : BuildType({
    name = "1. Compile (w kontenerze SDK)"

    vcs {
        root(PrasowkaVcs)

        // branchFilter NA POZIOMIE VCS-SETTINGS buildu (nie triggera!) -
        // "-:<default>" wyklucza galaz domyslna (main) z tego, co ten build
        // "widzi" jako zmiane do zbudowania w kontekscie PR-owym, "+:*"
        // dopuszcza wszystko inne (w tym refs/pull/*/head widoczne dzieki
        // branchSpec VcsRoot-a powyzej). To NIE steruje, kiedy build sie
        // odpala (to robi trigger, patrz nizej) - steruje tym, jakie galezie
        // w ogole pojawiaja sie na liscie galezi tej konfiguracji buildu.
        // [dsl-doc]: VcsSettings.branchFilter, potwierdzone jako WLASNOSC
        // KLASY BAZOWEJ "VcsSettings" - jedyny fragment ponizej faktycznie
        // obecny w publicznym jarze "configs-dsl-kotlin-latest" (zob.
        // code/README.md, sekcja "Co naprawde jest w jarze").
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
            dockerImagePlatform = ScriptBuildStep.ImagePlatform.Linux   // [?]
            dockerPull = true
        }
    }

    triggers {
        // Trigger VCS z branchFilter ograniczonym do galezi main + PR-y -
        // to jest KROK, ktorego brakowalo w #4/#5/#6 (tam trigger byl tylko
        // na koncu lancucha, na "Release", i patrzyl wylacznie na commity do
        // "main"). Bez tego triggera feature "pullRequests" ponizej TYLKO
        // wyswietla informacje o PR-ach w UI - nie odpala zadnego builda
        // automatycznie (patrz cytat z dokumentacji w ARTICLE.md: "Pull
        // Requests feature does not automatically trigger new builds").
        // [dsl-doc]: VcsTrigger.branchFilter, klasa
        // jetbrains.buildServer.configs.kotlin.triggers.VcsTrigger -
        // przyklad "Trigger a build on every commit in the default branch
        // or a branch which name starts with 'release/'" z dzisiejszej
        // dokumentacji uzywa DOKLADNIE tej samej skladni "+:<default>".
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

        // ===================================================================
        // GLOWNY TEMAT #7: build feature "Pull Requests".
        // ===================================================================
        // [dsl-doc]: jetbrains.buildServer.configs.kotlin.buildFeatures.PullRequests,
        // pobrane dzis z teamcity.jetbrains.com/app/dsl-documentation/buildFeatures/
        // pull-requests/index.html (TeamCity Kotlin DSL 2026.2.1) - klasa, funkcja
        // "pullRequests(...)" i WSZYSTKIE nazwy pol ponizej (vcsRootExtId, provider,
        // github{}, authType, token{}/vcsRoot(), filterSourceBranch, filterTargetBranch,
        // filterAuthorRole, ignoreDrafts, discoveryMode) sa przepisane 1:1 z realnych
        // przykladow w tej dokumentacji, NIE z pamieci - jedyny [?] w tym bloku to
        // dokladne nazwy pozostalych dwoch wartosci enuma GitHubRoleFilter (patrz nizej).
        pullRequests {
            // Pusty string = "wez pierwszy dolaczony VCS root typu git" - tu podany
            // jawnie dla czytelnosci, bo build ma tylko jeden root.
            vcsRootExtId = "${PrasowkaVcs.id}"

            provider = github {
                // Jesli VCS root laczy sie przez HTTPS z tokenem/uzytkownikiem, mozna
                // uzyc "authType = vcsRoot()" i w ogole nie trzymac osobnego sekretu
                // dla tego feature'u - TeamCity wyciaga dane logowania z samego roota.
                // Tutaj pokazany osobny token (typowe, gdy VCS root laczy sie anonimowo
                // albo przez SSH - wtedy "vcsRoot()" nie zadziala, patrz dokumentacja).
                authType = token {
                    token = "credentialsJSON:22222222-2222-2222-2222-222222222222"
                }

                // Filtr autora: kto MOZE w ogole wyzwolic PR, ktory TeamCity zauwazy.
                // "MEMBER" = tylko czlonkowie tej samej organizacji GitHub co
                // repozytorium - odrzuca PR-y z forkow zewnetrznych kontrybutorow.
                // To jest odpowiedz na "kto moze triggerowac build z PR" z tematu
                // dzisiejszego wydania: BEZ tego filtra (albo z "EVERYBODY") dowolny
                // uzytkownik internetu moze wyslac PR i - jesli trigger jest
                // nieostrozny - sprawic, ze TeamCity wykona kod z jego brancha na
                // WLASNYM agencie (patrz ostrzezenie w ARTICLE.md, sekcja 3).
                filterAuthorRole = PullRequests.GitHubRoleFilter.MEMBER   // [dsl-doc] potwierdzone doslownie

                // Dodatkowe filtry brancha (oba opcjonalne, tu pokazane dla
                // kompletnosci przykladu) - ograniczaja obserwowane PR-y do tych,
                // ktore CELUJA w main, niezaleznie od tego, skad pochodza.
                filterTargetBranch = "+:refs/heads/main"

                // "Ignoruj draft PR-y" - draft to sygnal "jeszcze nie proszę o
                // review", wiec czesto tez "jeszcze nie proszę o build".
                ignoreDrafts = true
            }
        }

        // Commit Status Publisher NA TYM SAMYM build type co "pullRequests" -
        // to jest para, o ktorej mowi zadanie: "integracja z VCS hostingiem
        // (build feature pullRequests + commitStatusPublisher razem, zeby
        // status buildu wracal do PR)". "pullRequests" tylko CZYTA informacje
        // o PR-ach (i steruje, ktore sa "widoczne") - to "commitStatusPublisher"
        // faktycznie WYSYLA status buildu z powrotem do GitHuba (widoczny jako
        // "check" na stronie PR-a: w trakcie / sukces / porazka).
        // [dsl-doc]: jetbrains.buildServer.configs.kotlin.buildFeatures.CommitStatusPublisher,
        // pobrane dzis z jetbrains.com/help/teamcity/commit-status-publisher.html,
        // sekcja "Kotlin DSL" - sygnatura identyczna do tej uzytej juz w #6 na
        // "Release" (tam - koncowy status calego lancucha; tu - szybki status
        // z samego Compile, widoczny na PR-ze juz po pierwszym, najtanszym kroku).
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
// 2. Test: bez zmian względem wydania #5/#6 - matrix (SDK 8/9/10) + parallelTests.
// ---------------------------------------------------------------------------
object Test : BuildType({
    name = "2. Test"

    vcs { root(PrasowkaVcs) }

    steps {
        script {
            name = "dotnet test"
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
        matrix {
            param("env.SDK_VERSION", listOf("8.0", "9.0", "10.0"))
        }

        parallelTests {
            numberOfBatches = 3
        }

        swabra { }
    }
})

// ---------------------------------------------------------------------------
// 3. IntegrationTest: bez zmian względem wydania #6 - runner "DockerCompose".
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
// 4. DockerImage: bez zmian względem wydania #5/#6.
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
// 5. Release: bez zmian względem #4/#5/#6 - composite, agreguje cały łańcuch,
//    commitStatusPublisher tutaj raportuje KONCOWY status calego chainu
//    (Compile wyzej raportuje wczesny, czastkowy status samego PR-a).
// ---------------------------------------------------------------------------
object Release : BuildType({
    name = "5. Release (composite)"
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
