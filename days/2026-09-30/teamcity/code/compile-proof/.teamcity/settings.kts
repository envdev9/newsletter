// DOWOD KOMPILACJI: plik CELOWO ograniczony wylacznie do klas BAZOWYCH, ktore naprawde
// istnieja w publicznie pobieralnym artefakcie "configs-dsl-kotlin-latest:2026.3-dsl6"
// (potwierdzone dzis przez zrzut listy klas .class z pobranego .jar - zob. ../../README.md,
// sekcja "Co naprawde jest w jarze"). NIE uzywa GitVcsRoot / vcs{} triggera / pullRequests{}
// / commitStatusPublisher{} - te konkretne klasy sa kontrybuowane przez poszczegolne
// pluginy TeamCity i po prostu NIE SA CZESCIA tego artefaktu (dowod: te pakiety w ogole
// nie istnieja w .jarze, nie tylko "brakuje kilku klas").
//
// Zamiast tego uzyty jest generyczny mechanizm "type + param(...)", DOKLADNIE ten sam,
// ktory wydanie #6 odkrylo dla runnera "DockerCompose" (step { type = "..."; param(...) })
// - tutaj zastosowany DODATKOWO do VcsRoot, Trigger i BuildFeature, bo te trzy bazowe
// klasy tez maja wlasny "type: String" + "param(name, value)" (widac to w javap-owym
// zrzucie klas VcsRoot/Trigger/BuildFeature - zob. README.md).
//
// WAZNE ZASTRZEZENIE UCZCIWOSCIOWE: to, ze ten plik SIE KOMPILUJE, dowodzi tylko, ze
// MECHANIZM (baza VcsRoot/Trigger/BuildFeature + type + param) jest poprawny i akceptowany
// przez generator. NIE dowodzi, ze "jetbrains.git", "vcsTrigger" i "pullRequests" ponizej
// to naprawde poprawne, live'owe identyfikatory typow uzywane przez serwer TeamCity, ani
// ze nazwy parametrow (authenticationType, filterAuthorRole, vcsRootId) sa realnymi
// nazwami wewnetrznych parametrow feature'u Pull Requests - generator offline NIE
// waliduje "type"/parametrow wobec zadnego rejestru zainstalowanych pluginow (nie ma
// go w tym trybie), wiec przyjmie DOWOLNY string bez skargi. "jetbrains.git" i
// "vcsTrigger" sa powszechnie znane/udokumentowane jako prawdziwe identyfikatory
// (widoczne np. w eksportach projektow TeamCity), ALE dokladne wewnetrzne nazwy
// parametrow feature'u "pullRequests" (VcsRootId/authenticationType/filterAuthorRole
// ponizej) sa TUTAJ ILUSTRACYJNE - prawdziwe partie pochodza z DSL-owych nazw pol
// (patrz idiomatyczna wersja w ../../.teamcity/settings.kts), nie z tego pliku.

import jetbrains.buildServer.configs.kotlin.*

version = "2026.1"

project {
    vcsRoot(GenericGitRoot)
    buildType(Build)
}

object GenericGitRoot : VcsRoot({
    name = "Prasówka (generic git root)"
    type = "jetbrains.git"
    param("url", "https://github.com/envdev9/newsletter.git")
    param("branch", "refs/heads/main")
})

object Build : BuildType({
    name = "Build z generycznym triggerem VCS i generycznym build feature 'pullRequests'"

    vcs {
        root(GenericGitRoot)
    }

    triggers {
        trigger(Trigger({
            type = "vcsTrigger"
            param("branchFilter", """
                +:*
                -:<default>
            """.trimIndent())
        }))
    }

    features {
        feature(BuildFeature({
            type = "pullRequests"
            param("vcsRootId", "${GenericGitRoot.id}")
            param("authenticationType", "vcsRoot")
            param("filterAuthorRole", "MEMBER")
        }))
    }
})
