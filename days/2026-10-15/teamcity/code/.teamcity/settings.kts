import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildSteps.script

/*
Wydanie #22: zaleznosci ARTEFAKTOWE w lancuchu buildow (uzupelnienie snapshot z #15).

    Compile ── (snapshot + artefakt) ──> Test       (sameChainOrLastFinished: artefakt Z TEGO lancucha)
       │
       └──────── (snapshot + artefakt) ──> TestLast  (lastSuccessful: artefakt Z NAJNOWSZEGO udanego Compile)

Compile publikuje out/app.txt jako artefakt (artifactRules). Test i TestLast pobieraja go do katalogu in/.
TestLast celowo uzywa zwyklego snapshot(Compile) { } bez opcji, zeby zmierzyc jego domyslna reakcje na pad.
*/

version = "2025.07"

project {
    buildType(Compile)
    buildType(Test)
    buildType(TestLast)
}

object Compile : BuildType({
    id("Compile")
    name = "Compile"

    // wszystko z out/ trafia do artefaktow builda (w serwerze: sciezka build-out/...)
    artifactRules = "out/** => build-out"

    steps {
        script {
            name = "Compile"
            scriptContent = """
                set -e
                test ! -f /tmp/fail-compile
                mkdir -p out
                echo "compiled by Compile #%build.number% (build id %teamcity.build.id%)" > out/app.txt
                cat out/app.txt
            """.trimIndent()
        }
    }
})

object Test : BuildType({
    id("Test")
    name = "Test"

    dependencies {
        snapshot(Compile) {
            onDependencyFailure = FailureAction.FAIL_TO_START
        }
        artifacts(Compile) {
            buildRule = sameChainOrLastFinished()
            artifactRules = "build-out/** => in"
        }
    }

    steps {
        script {
            name = "Test"
            scriptContent = """
                echo "ja: Test #%build.number%, zaleznosc Compile #%dep.ArtDemo_Compile.build.number%"
                echo "artefakt mowi:"
                cat in/app.txt
                # status builda widoczny w REST (statusText) - nie trzeba pobierac logu
                echo "##teamcity[buildStatus text='Test #%build.number%, snapshot Compile #%dep.ArtDemo_Compile.build.number%, artefakt: $(cat in/app.txt)']"
            """.trimIndent()
        }
    }
})

object TestLast : BuildType({
    id("TestLast")
    name = "TestLast"

    dependencies {
        // zwykly snapshot, bez opcji: domyslne zachowanie przy padzie do zmierzenia
        snapshot(Compile) {
        }
        artifacts(Compile) {
            buildRule = lastSuccessful()
            artifactRules = "build-out/** => in"
        }
    }

    steps {
        script {
            name = "TestLast"
            scriptContent = """
                echo "ja: TestLast #%build.number%, snapshot wskazuje Compile #%dep.ArtDemo_Compile.build.number%"
                echo "artefakt mowi:"
                cat in/app.txt
                echo "##teamcity[buildStatus text='TestLast #%build.number%, snapshot Compile #%dep.ArtDemo_Compile.build.number%, artefakt: $(cat in/app.txt)']"
            """.trimIndent()
        }
    }
})
