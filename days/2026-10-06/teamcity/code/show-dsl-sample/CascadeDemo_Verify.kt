package CascadeDemo.buildTypes

import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildFeatures.AutoMerge
import jetbrains.buildServer.configs.kotlin.buildFeatures.merge
import jetbrains.buildServer.configs.kotlin.buildSteps.script
import jetbrains.buildServer.configs.kotlin.triggers.vcs

object CascadeDemo_Verify : BuildType({
    uuid = "9c3c6ebf-f6c6-4132-a16d-0c268f61ba40"
    name = "Verify"

    vcs {
        root(CascadeDemo.vcsRoots.CascadeRoot)

        checkoutMode = CheckoutMode.ON_SERVER
    }

    steps {
        script {
            name = "Test"
            scriptContent = "echo build-on-%teamcity.build.branch%"
        }
    }

    triggers {
        vcs {
            enableQueueOptimization = false
        }
    }

    features {
        merge {
            branchFilter = "+:feature/*"
            destinationBranch = "integration"
            commitMessage = "Auto-merge: %teamcity.build.branch% (build #%build.number%)"
        }
        merge {
            branchFilter = "+:integration"
            destinationBranch = "main"
            commitMessage = "Auto-merge: %teamcity.build.branch% (build #%build.number%)"
            mergePolicy = AutoMerge.MergePolicy.FAST_FORWARD
            mergeCondition = "noNewTests"
            runPolicy = AutoMerge.RunPolicy.BEFORE_BUILD_FINISH
        }
    }
})
