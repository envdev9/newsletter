import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildSteps.script

/*
Wydanie #15: lancuch buildow zbudowany DSL-owymi sequential { } / parallel { }.

      Compile ──┬── Test ──┬── Package ── Summary
                └── Lint ──┘

Kazda strzalka to zaleznosc snapshot, ktora DSL dodaje sam (nie piszemy zadnego snapshot(...)).
*/

version = "2025.07"

project {

    val chain = sequential {
        buildType(Stage("Compile", "echo compiling && test ! -f /tmp/fail-compile"))
        parallel {
            buildType(Stage("Test", "echo testing && sleep 5"))
            buildType(Stage("Lint", "echo linting && sleep 5 && test ! -f /tmp/fail-lint"))
        }
        buildType(Stage("Package", "echo packaging"), options = {
            reuseBuilds = ReuseBuilds.NO
            onDependencyFailure = FailureAction.FAIL_TO_START
        })
        buildType(Stage("Summary", "echo summary"), options = {
            onDependencyFailure = FailureAction.IGNORE
            onDependencyCancel = FailureAction.IGNORE
        })
    }

    chain.buildTypes().forEach { buildType(it) }
}

class Stage(stageName: String, command: String) : BuildType({
    id(stageName)
    name = stageName

    steps {
        script {
            name = stageName
            scriptContent = command
        }
    }
})
