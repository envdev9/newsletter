import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildSteps.script
import jetbrains.buildServer.configs.kotlin.triggers.vcs
import jetbrains.buildServer.configs.kotlin.vcs.GitVcsRoot

version = "2026.3"

project {
    vcsRoot(PrasowkaVcs)
    buildType(Build)
}

object PrasowkaVcs : GitVcsRoot({
    name = "Prasówka (GitHub)"
    url = "https://github.com/envdev9/newsletter.git"
    branch = "refs/heads/main"
})

object Build : BuildType({
    name = "Build i testy"

    vcs {
        root(PrasowkaVcs)
    }

    steps {
        script {
            name = "Powiedz cześć"
            scriptContent = "echo 'Buduję prasówkę...'"
        }
    }

    triggers {
        vcs {
        }
    }
})
