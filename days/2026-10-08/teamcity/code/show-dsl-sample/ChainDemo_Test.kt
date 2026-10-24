package ChainDemo.buildTypes

import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildSteps.script

object ChainDemo_Test : BuildType({
    name = "Test"

    steps {
        script {
            name = "Test"
            scriptContent = "echo testing && sleep 5"
        }
    }

    dependencies {
        snapshot(ChainDemo_Compile) {
        }
    }
})
