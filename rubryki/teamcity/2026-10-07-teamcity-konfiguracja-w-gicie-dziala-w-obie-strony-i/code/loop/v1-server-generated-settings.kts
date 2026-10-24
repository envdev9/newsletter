// Tak wyglada .teamcity/settings.kts zacommitowany przez SERWER (commit 5fe014a) tuz po wlaczeniu
// versioned settings w formacie Kotlin. Dlugi komentarz wstepny (ok. 20 linii, generowany przez
// TeamCity) pominieto; reszta dosłownie. Zwroc uwage: sam VCS root repo z ustawieniami NIE trafia do DSL.
import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildSteps.script

version = "2025.07"

project {

    buildType(Hello)
}

object Hello : BuildType({
    name = "Hello"

    steps {
        script {
            name = "Greet"
            scriptContent = "echo hello-v1"
        }
    }
})
