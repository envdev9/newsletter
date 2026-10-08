package ChainDemo.buildTypes

import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildSteps.script

object ChainDemo_Package : BuildType({
    name = "Package"

    steps {
        script {
            name = "Package"
            scriptContent = "echo packaging"
        }
    }

    dependencies {
        snapshot(ChainDemo_Lint) {
            reuseBuilds = ReuseBuilds.NO
            onDependencyFailure = FailureAction.FAIL_TO_START
        }
        snapshot(ChainDemo_Test) {
            reuseBuilds = ReuseBuilds.NO
            onDependencyFailure = FailureAction.FAIL_TO_START
        }
    }
})
