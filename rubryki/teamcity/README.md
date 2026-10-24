<div align="center">

# 🏗️ TeamCity

### TECH PRASÓWKA — wszystkie artykuły rubryki, najnowsze na górze

</div>

---

Każdy artykuł to osobny folder `<data>-<tytuł>/` z `ARTICLE.md` i pełnym, uruchamialnym
kodem w `code/`. Kolejne artykuły podnoszą poziom — postęp rubryki jest w
[`STATE.md`](../../STATE.md).

| Data | Artykuł | W skrócie | Kod |
|------|---------|-----------|-----|
| 2026-10-15 | [TeamCity: zielone testy na artefakcie z builda, który nie jest Twój — snapshot to nie artefakt](2026-10-15-teamcity-zielone-testy-na-artefakcie-z-builda-ktory-nie/ARTICLE.md) | `snapshot` i `artifacts` wybierają builda niezależnie — łańcuch może zbudować z artefaktu ze starego buildu, a zwykły `snapshot { }` po padniętym Compile i tak uruchamia krok (`RUN_ADD_PROBLEM`); zmierzone na żywym serwerze 2025.07, 19 buildów. | [Kod](2026-10-15-teamcity-zielone-testy-na-artefakcie-z-builda-ktory-nie/code/) |
| 2026-10-08 | [TeamCity: łańcuch buildów w 10 linijkach Kotlina — i domyślne ustawienie, które pozwala testom biec po padniętej kompilacji](2026-10-08-teamcity-lancuch-buildow-w-10-linijkach-kotlina-i-domyslne/ARTICLE.md) | Łańcuch Compile → Test+Lint → Package → Summary w 10 linijkach Kotlina (`sequential`/`parallel`) — a domyślna reakcja `sequential` sprawia, że testy biegną nawet po padniętej kompilacji. | [Kod](2026-10-08-teamcity-lancuch-buildow-w-10-linijkach-kotlina-i-domyslne/code/) |
| 2026-10-07 | [TeamCity: konfiguracja w Gicie działa w OBIE strony — i potrafi się pokłócić sama ze sobą](2026-10-07-teamcity-konfiguracja-w-gicie-dziala-w-obie-strony-i/ARTICLE.md) | Twój config w Gicie to nie archiwum, tylko pętla w obie strony: serwer kładzie obok `settings.kts` łatki z UI, a gdy ten sam krok zmienisz w kodzie, odrzuca Twój push i zostaje przy starej wersji. | [Kod](2026-10-07-teamcity-konfiguracja-w-gicie-dziala-w-obie-strony-i/code/) |
| 2026-10-06 | [TeamCity: cascading merge `feature → integration → main` — z prawdziwym agentem i trzema pułapkami](2026-10-06-teamcity-cascading-merge-feature-integration-main-z/ARTICLE.md) | Cascading merge `feature → integration → main` na żywym serwerze z prawdziwym agentem — a pominięty `commitMessage` po cichu wyłącza merge, zostawiając zielony build. | [Kod](2026-10-06-teamcity-cascading-merge-feature-integration-main-z/code/) |
| 2026-10-01 | [TeamCity: Automatic Merge — i pierwszy w historii tej rubryki `BUILD SUCCESS` na CAŁYM pipeline'ie](2026-10-01-teamcity-automatic-merge-i-pierwszy-w-historii-tej-rubryki/ARTICLE.md) | Po siedmiu porażkach z rzędu — żywy serwer TeamCity w Dockerze, reverse engineering jego własnego szyfrowania RSA haseł, i w końcu prawdziwy `BUILD SUCCESS` na CAŁYM pipeline z nowym tematem: build feature Automatic Merge. | [Kod](2026-10-01-teamcity-automatic-merge-i-pierwszy-w-historii-tej-rubryki/code/) |
| 2026-09-30 | [TeamCity: Pull Requests jako trigger/feature — i pierwszy w historii tej rubryki prawdziwy `BUILD SUCCESS`](2026-09-30-teamcity-pull-requests-jako-trigger-feature-i-pierwszy-w/ARTICLE.md) | Pull Requests jako trigger/feature (`filterAuthorRole = MEMBER` odpowiada na "kto może triggerować build z forka") — i po sześciu porażkach z rzędu, pierwszy w historii rubryki prawdziwy `BUILD SUCCESS` realnego `mvn compile`, plus dowód dlaczego reszta configu i tak się nie skompiluje: publiczny jar DSL nie zawiera klas kontrybuowanych przez pluginy. | [Kod](2026-09-30-teamcity-pull-requests-jako-trigger-feature-i-pierwszy-w/code/) |
| 2026-09-29 | [TeamCity: sekcja śledcza — dlaczego `mvn compile` nadal nie działa (i dlaczego to już nie zgadywanie) + Docker Compose jako krok pipeline'u](2026-09-29-teamcity-sekcja-sledcza-dlaczego-mvn-compile-nadal-nie/ARTICLE.md) | Piąta próba kompilacji Kotlin DSL nadal bez sukcesu, ale pierwszy raz w pełni zdiagnozowana (allowlist poleceń + zakaz wywołań po ścieżce bezwzględnej, sieć jednak działa) — plus nowy krok pipeline'u: Docker Compose z Postgresem dla testów integracyjnych. | [Kod](2026-09-29-teamcity-sekcja-sledcza-dlaczego-mvn-compile-nadal-nie/code/) |
| 2026-09-28 | [TeamCity: matrix builds, parallel tests i realny push do rejestru Dockera](2026-09-28-teamcity-matrix-builds-parallel-tests-i-realny-push-do/ARTICLE.md) | `matrix` builds, `parallelTests` i push do rejestru Dockera (`dockerRegistry`/`dockerSupport`) na pipeline z #4 — plus czwarta z rzędu, tym razem inaczej uzasadniona, próba realnej kompilacji Kotlin DSL (JDK 21 zablokowany przez sandbox, nie przez wersję JDK). | [Kod](2026-09-28-teamcity-matrix-builds-parallel-tests-i-realny-push-do/code/) |
| 2026-09-27 | [TeamCity: build features, failure conditions, Docker i composite build](2026-09-27-teamcity-build-features-failure-conditions-docker-i/ARTICLE.md) | Zielony build to nie zawsze dobry build: TeamCity uczy się czepiać spadku liczby testów, uruchamia kroki w kontenerze i pokazuje cały łańcuch jednym znaczkiem na commicie (kompilacja Kotlin DSL niezweryfikowana — brak narzędzi w środowisku). | [Kod](2026-09-27-teamcity-build-features-failure-conditions-docker-i/code/) |
| 2026-09-26 | [Pipeline .NET w TeamCity: szablony, parametry i łańcuch zależności](2026-09-26-pipeline-net-w-teamcity-szablony-parametry-i-lancuch/ARTICLE.md) | Jeden szablon zamiast trzech kopii configu: Build → Test → Pack jako łańcuch zależności snapshot i artifact, z parametrami i override w Kotlin DSL — uczciwie: kompilacji DSL nie udało się zweryfikować (brak JDK 21). | [Kod](2026-09-26-pipeline-net-w-teamcity-szablony-parametry-i-lancuch/code/) |
| 2026-09-24 | [Konfiguracja builda jako kod: pierwszy `.teamcity/settings.kts`](2026-09-24-konfiguracja-builda-jako-kod-pierwszy-teamcity-settings-kts/ARTICLE.md) | Kotlin DSL, `.teamcity/settings.kts`, i uczciwie opisana granica tego, co dało się | [Kod](2026-09-24-konfiguracja-builda-jako-kod-pierwszy-teamcity-settings-kts/code/) |
<!-- kolejne wiersze dopisywane automatycznie, najnowsze na górze -->

---

<div align="center">

[← spis rubryk](../../README.md)

</div>
