import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildSteps.script

version = "2025.07"

project {

    buildType(Hello)
    buildType(Bye)
}

// Rozwiazanie konfliktu: zmiany z patcha serwera (greeting = czesc) wniesione RECZNIE do settings.kts,
// patch patches/buildTypes/Hello.kts usuniety (git rm), skrypt kroku zmieniony na v4.
object Hello : BuildType({
    name = "Hello"

    params {
        param("greeting", "czesc")
    }

    steps {
        script {
            name = "Greet"
            scriptContent = "echo hello-v4 %greeting%"
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
