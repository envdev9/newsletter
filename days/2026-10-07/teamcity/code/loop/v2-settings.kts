import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildSteps.script

version = "2025.07"

project {

    buildType(Hello)
    buildType(Bye)
}

object Hello : BuildType({
    name = "Hello"

    params {
        param("greeting", "hallo")
    }

    steps {
        script {
            name = "Greet"
            scriptContent = "echo hello-v2 %greeting%"
        }
    }
})

// Nowy build type, ktorego nie bylo na serwerze: powstaje WYLACZNIE z pushu do repo.
object Bye : BuildType({
    name = "Bye"

    steps {
        script {
            name = "Farewell"
            scriptContent = "echo bye-from-vcs"
        }
    }
})
