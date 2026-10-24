<div align="center">

# ✈️ Aspire

### TECH PRASÓWKA — wszystkie artykuły rubryki, najnowsze na górze

</div>

---

Każdy artykuł to osobny folder `<data>-<tytuł>/` z `ARTICLE.md` i pełnym, uruchamialnym
kodem w `code/`. Kolejne artykuły podnoszą poziom — postęp rubryki jest w
[`STATE.md`](../../STATE.md).

| Data | Artykuł | W skrócie | Kod |
|------|---------|-----------|-----|
| 2026-10-15 | ["Trwały" kontener Aspire jest trwały do pierwszej zmiany konfiguracji. Zmień jedną zmienną środowiskową i Redis wstaje od zera](2026-10-15-trwaly-kontener-aspire-jest-trwaly-do-pierwszej-zmiany/ARTICLE.md) | Zmiana env lub taga obrazu cicho odtwarza „trwały" kontener i kasuje dane, a `WithDataVolume` zapisuje na dysk dopiero co 60 s — `docker rm` tuż po zapisie gubi dane mimo woluminu (3 pełne przebiegi na Aspire 13.5.2). | [Kod](2026-10-15-trwaly-kontener-aspire-jest-trwaly-do-pierwszej-zmiany/code/) |
| 2026-10-08 | [Jedna linijka sprawiła, że Redis przeżył `kill -9` AppHosta — razem z danymi. Tylko że teraz to Ty go sprzątasz](2026-10-08-jedna-linijka-sprawila-ze-redis-przezyl-kill-9-apphosta/ARTICLE.md) | Jedna linijka `WithLifetime(ContainerLifetime.Persistent)` sprawiła, że Redis z danymi przeżył `kill -9` AppHosta i został podpięty przez następny — ale teraz to Ty go sprzątasz. | [Kod](2026-10-08-jedna-linijka-sprawila-ze-redis-przezyl-kill-9-apphosta/code/) |
| 2026-10-07 | [Zabiłem proces z AppHostem `kill -9`. Redis w Dockerze zniknął po 12 sekundach — a potem zabiłem też siatkę bezpieczeństwa](2026-10-07-zabilem-proces-z-apphostem-kill-9-redis-w-dockerze-zniknal/ARTICLE.md) | `kill -9` na procesie z AppHostem: Redis w Dockerze znika po ~12 s (sprząta DCP, nie Twój kod) — ale gdy zabijemy też DCP, zostaje sierota, a następny AppHost posprząta tylko kontener i sieć, nie procesy. | [Kod](2026-10-07-zabilem-proces-z-apphostem-kill-9-redis-w-dockerze-zniknal/code/) |
| 2026-10-06 | [Ile AppHostów naprawdę żyje w Twojej sesji testowej? Zmierzyliśmy `docker ps`](2026-10-06-ile-apphostow-naprawde-zyje-w-twojej-sesji-testowej/ARTICLE.md) | Ile żyje AppHost pod testami TUnit: `PerTestSession` daje jeden Redis dla dwóch klas, `PerClass` dwa kontenery naraz — a celowo oblany test i tak nie zostawia po sobie kontenera. Cena: ~14 s samego sprzątania na AppHosta. | [Kod](2026-10-06-ile-apphostow-naprawde-zyje-w-twojej-sesji-testowej/code/) |
| 2026-10-05 | [AppHost pod testem TUnit — jeden kontener, cztery testy na raz, zero kolizji](2026-10-05-apphost-pod-testem-tunit-jeden-kontener-cztery-testy-na-raz/ARTICLE.md) | AppHost pod testem TUnit: jeden realny kontener Redis uruchomiony raz na klasę, cztery testy walące w niego równolegle bez kolizji (dzięki unikalnym kluczom) — plus haczyk, że statyczny `[After(Class)]` i instancyjny fixture Aspire wzajemnie się nie widzą. | [Kod](2026-10-05-apphost-pod-testem-tunit-jeden-kontener-cztery-testy-na-raz/code/) |
| 2026-09-30 | [Postgres, który pamięta, i hasło, którego nie ma w repo](2026-09-30-postgres-ktory-pamieta-i-haslo-ktorego-nie-ma-w-repo/ARTICLE.md) | Postgres z trwałym `WithDataVolume()` i hasłem z `dotnet user-secrets` zamiast kodu — notatka zapisana w pierwszym AppHoście przeżywa `StopAsync`, usunięcie kontenera i start zupełnie nowego AppHosta na tym samym woluminie. | [Kod](2026-09-30-postgres-ktory-pamieta-i-haslo-ktorego-nie-ma-w-repo/code/) |
| 2026-09-28 | [Pierwszy prawdziwy kontener: `AddRedis`, a Aspire po cichu dorzuca hasło i TLS](2026-09-28-pierwszy-prawdziwy-kontener-addredis-a-aspire-po-cichu/ARTICLE.md) | Pierwszy prawdziwy kontener w tej rubryce: `AddRedis("cache")` odpala realny Docker, a Aspire po cichu dorzuca losowe hasło i TLS do connection stringa, o które nikt nie prosił — 3 przebiegi, za każdym razem 8/8 PASS. | [Kod](2026-09-28-pierwszy-prawdziwy-kontener-addredis-a-aspire-po-cichu/code/) |
| 2026-09-27 | [Parametry, sekrety i `WithEnvironment`: co dokładnie dostaje Twój proces](2026-09-27-parametry-sekrety-i-withenvironment-co-dokladnie-dostaje/ARTICLE.md) | Skąd proces dostaje sekrety w Aspire i dlaczego `AddParameter("x", "wartość")` po cichu ignoruje konfigurację? Parametry, `WithEnvironment` i `AddExecutable` — zweryfikowane testem AppHosta (bez kontenerów). | [Kod](2026-09-27-parametry-sekrety-i-withenvironment-co-dokladnie-dostaje/code/) |
| 2026-09-26 | [Dwa serwisy, zero adresów: `WithReference`, `WaitFor` i telemetria, którą napisałeś sam](2026-09-26-dwa-serwisy-zero-adresow-withreference-waitfor-i-telemetria/ARTICLE.md) | `WaitFor` nie czeka, aż proces wstanie, tylko aż serwis powie „jestem gotowy" — dwa serwisy znajdują się po nazwie (`http://catalog`), a całość weryfikuje jedno polecenie `dotnet run` z testowym AppHostem. | [Kod](2026-09-26-dwa-serwisy-zero-adresow-withreference-waitfor-i-telemetria/code/) |
| 2026-09-24 | [AppHost — jeden plik C#, który uruchamia i pilnuje całego środowiska](2026-09-24-apphost-jeden-plik-c-ktory-uruchamia-i-pilnuje-calego/ARTICLE.md) | AppHost, dashboard i OpenTelemetry "za darmo" — bez jednego Dockerowego kontenera. | [Kod](2026-09-24-apphost-jeden-plik-c-ktory-uruchamia-i-pilnuje-calego/code/) |
<!-- kolejne wiersze dopisywane automatycznie, najnowsze na górze -->

---

<div align="center">

[← spis rubryk](../../README.md)

</div>
