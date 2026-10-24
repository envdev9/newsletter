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
        param("greeting", "czesc")
    }

    steps {
        script {
            name = "Greet"
            // literowka: scriptContents zamiast scriptContent
            scriptContents = "echo hello-v5 %greeting%"
        }
    }
})

object Bye : BuildType({
    name = "Bye"

    steps {
        script {
            name = "Farewell"
            scriptContent = "echo bye-from-vcs"
        }
    }
})
