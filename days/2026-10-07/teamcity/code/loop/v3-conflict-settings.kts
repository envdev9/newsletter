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
            // zmiana TEGO SAMEGO kroku, ktory serwer juz "zalatal" patchem patches/buildTypes/Hello.kts
            scriptContent = "echo hello-v3 %greeting%"
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
