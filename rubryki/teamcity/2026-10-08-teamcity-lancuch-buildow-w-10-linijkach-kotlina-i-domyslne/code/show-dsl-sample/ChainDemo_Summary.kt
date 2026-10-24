package ChainDemo.buildTypes

import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildSteps.script

object ChainDemo_Summary : BuildType({
    name = "Summary"

    steps {
        script {
            name = "Summary"
            scriptContent = "echo summary"
        }
    }

    dependencies {
        snapshot(ChainDemo_Package) {
            onDependencyFailure = FailureAction.IGNORE
            onDependencyCancel = FailureAction.IGNORE
        }
    }
})
