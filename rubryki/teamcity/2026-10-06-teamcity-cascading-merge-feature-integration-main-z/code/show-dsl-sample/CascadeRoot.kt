package CascadeDemo.vcsRoots

import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.vcs.GitVcsRoot

object CascadeRoot : GitVcsRoot({
    uuid = "98d24a7e-5990-489d-a7f2-c305603ce803"
    name = "Cascade Root"
    url = "file:///srv/demo.git"
    branch = "refs/heads/main"
    branchSpec = """
        +:refs/heads/(feature/*)
        +:refs/heads/(integration)
        +:refs/heads/(main)
    """.trimIndent()
})
