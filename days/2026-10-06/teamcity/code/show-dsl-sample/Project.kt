package CascadeDemo

import CascadeDemo.buildTypes.*
import CascadeDemo.vcsRoots.*
import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.Project
import jetbrains.buildServer.configs.kotlin.kubernetesCloudImage
import jetbrains.buildServer.configs.kotlin.kubernetesCloudProfile

object Project : Project({
    uuid = "bf135a0d-cbb4-47e6-864f-ebe8f3a0a31a"
    id("CascadeDemo")
    parentId("_Root")
    name = "Cascade Demo"

    vcsRoot(CascadeRoot)

    buildType(CascadeDemo_Verify)

    features {
        kubernetesCloudImage {
            id = "PROJECT_EXT_2"
            profileId = "kube-1"
            agentPoolId = "-2"
            agentNamePrefix = "k8s-agent"
            maxInstancesCount = 3
            podSpecification = runContainer {
                dockerImage = "jetbrains/teamcity-agent:2025.07"
            }
        }
        kubernetesCloudProfile {
            id = "kube-1"
            name = "K8s demo"
            serverURL = "http://teamcity.example.invalid:8111"
            terminateIdleMinutes = 15
            apiServerURL = "https://k8s.example.invalid:6443"
            namespace = "ci"
            authStrategy = unauthorized()
        }
    }
})
