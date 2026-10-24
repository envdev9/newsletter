<div align="center">

# 🧪 TUnit

### TECH PRASÓWKA — wszystkie artykuły rubryki, najnowsze na górze

</div>

---

Każdy artykuł to osobny folder `<data>-<tytuł>/` z `ARTICLE.md` i pełnym, uruchamialnym
kodem w `code/`. Kolejne artykuły podnoszą poziom — postęp rubryki jest w
[`STATE.md`](../../STATE.md).

| Data | Artykuł | W skrócie | Kod |
|------|---------|-----------|-----|
| 2026-10-24 | [TUnit: własne źródło danych z pliku CSV i własny konstruktor klas testowych z DI](2026-10-24-tunit-wlasne-zrodlo-danych-z-pliku-csv-i-wlasny-konstruktor/ARTICLE.md) | Tabela przypadków w CSV jako własny atrybut danych TUnit i DI per test przez `[ClassConstructor]`, z błędnym wierszem wskazanym w nazwie testu. | [Kod](2026-10-24-tunit-wlasne-zrodlo-danych-z-pliku-csv-i-wlasny-konstruktor/code/) |
| 2026-10-18 | [TUnit: TRX po porażce, wiele kluczy w `[NotInParallel]` i pokrycie kodu, któremu można ufać](2026-10-18-tunit-trx-po-porazce-wiele-kluczy-w-notinparallel-i/ARTICLE.md) | Co ląduje w TRX, gdy test pada (`ErrorInfo` + `StdOut`), jak `[NotInParallel]` z wieloma kluczami czeka na oba naraz i ile kodu naprawdę pokrywają testy: 80% w pełnym przebiegu, 60% przy jednym teście — z niepokrytą gałęzią, którą widzi tylko `[Explicit]`. | [Kod](2026-10-18-tunit-trx-po-porazce-wiele-kluczy-w-notinparallel-i/code/) |
| 2026-10-17 | [TUnit: gdzie ląduje output testu, co trafia do TRX i czym naprawdę jest `[ParallelGroup]`](2026-10-17-tunit-gdzie-laduje-output-testu-co-trafia-do-trx-i-czym/ARTICLE.md) | Gdzie ląduje output testu, co trafia do TRX, jakie kody wyjścia zwraca przebieg z samymi skipami (0 — zielony dla CI!) i czym naprawdę jest `[ParallelGroup]` — wszystko zmierzone osią czasu. | [Kod](2026-10-17-tunit-gdzie-laduje-output-testu-co-trafia-do-trx-i-czym/code/) |
| 2026-10-11 | [TUnit: pominięte testy pod mikroskopem — kiedy dokładnie pada decyzja i co widać w raporcie](2026-10-11-tunit-pominiete-testy-pod-mikroskopem-kiedy-dokladnie-pada/ARTICLE.md) | Pominięty test nie może być cichy — dziś dowód z realnego przebiegu: `ShouldSkip` woła się raz, przed ciałem testu, powód skipu ląduje w raporcie, a `[Explicit]` nie wchodzi nawet do `total`. | [Kod](2026-10-11-tunit-pominiete-testy-pod-mikroskopem-kiedy-dokladnie-pada/code/) |
| 2026-10-10 | [TUnit: pomijanie testów — `[Skip]`, własny `SkipAttribute`, `Skip.Test` i `[Explicit]`](2026-10-10-tunit-pomijanie-testow-skip-wlasny-skipattribute-skip-test/ARTICLE.md) | Zakomentowany test to test zapomniany — TUnit pozwala pominąć go z powodem, warunkiem środowiskowym albo oznaczyć `[Explicit]`, ale w tym wydaniu uczciwie: kod się kompiluje, a przebieg testów nie został zweryfikowany (środowisko odrzuciło `dotnet test`). | [Kod](2026-10-10-tunit-pomijanie-testow-skip-wlasny-skipattribute-skip-test/code/) |
| 2026-10-08 | [TUnit: rotacja kluczy z wyprzedzeniem i klucze z certyfikatów X.509 — czy walidator sprawdza, że certyfikat wygasł?](2026-10-08-tunit-rotacja-kluczy-z-wyprzedzeniem-i-klucze-z/ARTICLE.md) | Wygasły certyfikat nadal podpisuje tokeny przyjmowane przez `JwtBearer`, chyba że sam dodasz sprawdzenie dat — plus dowód, że publikacja klucza w JWKS przed aktywacją usuwa pierwszy 401 po rotacji. | [Kod](2026-10-08-tunit-rotacja-kluczy-z-wyprzedzeniem-i-klucze-z/code/) |
| 2026-10-07 | [TUnit: rotacja kluczy JWT po prawdziwym HTTP i wyścig refresh tokenu — czego nie widać w zielonych testach](2026-10-07-tunit-rotacja-kluczy-jwt-po-prawdziwym-http-i-wyscig/ARTICLE.md) | Dwa prawdziwe serwery, rotacja kluczy JWKS i wyścig refresh tokenu — pierwszy użytkownik z nowym `kid` dostaje 401, wycofany klucz nadal działa, a test wyścigu przez HTTP przepuścił usunięty `lock`. | [Kod](2026-10-07-tunit-rotacja-kluczy-jwt-po-prawdziwym-http-i-wyscig/code/) |
| 2026-10-06 | [TUnit: testy JWT RS256 z rotacją refresh tokenu, sterowanym zegarem i wspólnym `TestKit` między projektami](2026-10-06-tunit-testy-jwt-rs256-z-rotacja-refresh-tokenu-sterowanym/ARTICLE.md) | JWT RS256 pod testem: walidator zna tylko klucz publiczny, tokeny wygasają na `FakeTimeProvider` bez `Thread.Sleep`, refresh token jest jednorazowy — a mutacja `RequireSignedTokens=false` oblewa dokładnie jeden z ośmiu testów fałszerstw (`alg=none`). Plus trzy projekty z `ProjectReference` i `--treenode-filter`. | [Kod](2026-10-06-tunit-testy-jwt-rs256-z-rotacja-refresh-tokenu-sterowanym/code/) |
| 2026-10-05 | [TUnit: `[AfterEvery(Assembly)]` i `[AfterEvery(Class)]` z DWOMA projektami testowymi naraz](2026-10-05-tunit-afterevery-assembly-i-afterevery-class-z-dwoma/ARTICLE.md) | `[AfterEvery(Assembly)]`/`[AfterEvery(Class)]` z DWOMA projektami testowymi w jednym `dotnet test`: hook liczy tylko swój projekt, każdy projekt to osobny proces OS, oba biegną WSPÓŁBIEŻNIE — a identycznie nazwana klasa stanu statycznego w obu wcale się nie myli. | [Kod](2026-10-05-tunit-afterevery-assembly-i-afterevery-class-z-dwoma/code/) |
| 2026-10-02 | [TUnit: `[AfterEvery(Class)]` oraz JWT w testach `WebApplicationFactory`](2026-10-02-tunit-afterevery-class-oraz-jwt-w-testach/ARTICLE.md) | `[AfterEvery(Class)]` domyka rodzinę hooków, a JWT w `WebApplicationFactory` pokazuje zmierzoną pułapkę: źle dobrane `MapInboundClaims`/`RoleClaimType` cicho wyłączają autoryzację (403 zamiast wyjątku). | [Kod](2026-10-02-tunit-afterevery-class-oraz-jwt-w-testach/code/) |
| 2026-09-30 | [TUnit: jeden host, dwie klasy testowe — `SharedType.PerTestSession` + `[AfterEvery(Assembly)]`](2026-09-30-tunit-jeden-host-dwie-klasy-testowe-sharedtype/ARTICLE.md) | `SharedType.PerTestSession` daje jeden `WebApplicationFactory` współdzielony przez dwie różne klasy testowe naraz — dowód nie z logów, tylko z endpointu `/instance-id` po stronie serwera — plus `[AfterEvery(Assembly)]` na raport zbiorczy po całym zestawie. | [Kod](2026-09-30-tunit-jeden-host-dwie-klasy-testowe-sharedtype/code/) |
| 2026-09-28 | [TUnit: prawdziwe API pod testem — `WebApplicationFactory<Program>` + `[ClassDataSource]`](2026-09-28-tunit-prawdziwe-api-pod-testem-webapplicationfactory/ARTICLE.md) | Prawdziwe minimalne API pod testem przez `WebApplicationFactory<Program>` + TUnit-owy odpowiednik `IClassFixture<T>` (`[ClassDataSource]` + `SharedType.PerClass`) — 5/5 testów, plus zmierzona (nie zgadywana) pułapka współdzielonego stanu i empiryczne obalenie rady o `partial class Program`. | [Kod](2026-09-28-tunit-prawdziwe-api-pod-testem-webapplicationfactory/code/) |
| 2026-09-27 | [TUnit: własne asercje, `[AfterEvery]` i retry tylko dla błędów przejściowych](2026-09-27-tunit-wlasne-asercje-afterevery-i-retry-tylko-dla-bledow/ARTICLE.md) | Własne asercje na `Assert.That`, hook `[AfterEvery]` i retry, który ponawia tylko błędy przejściowe, a prawdziwe błędy logiki zostawia czerwone — 6/6 zielone na TUnit 1.69. | [Kod](2026-09-27-tunit-wlasne-asercje-afterevery-i-retry-tylko-dla-bledow/code/) |
| 2026-09-26 | [TUnit: współdzielone fixture'y, retry, timeout i hook globalny](2026-09-26-tunit-wspoldzielone-fixture-y-retry-timeout-i-hook-globalny/ARTICLE.md) | Najdroższa linijka w testach to start zasobu — ile razy się wykona i kto go posprząta? Fixture'y `[ClassDataSource]` w czterech zasięgach, `[Retry]`, `[Timeout]` i hook globalny, zmierzone na żywo (18/18 zielone). | [Kod](2026-09-26-tunit-wspoldzielone-fixture-y-retry-timeout-i-hook-globalny/code/) |
| 2026-09-25 | [TUnit: dane, hooki i równoległość — sterowanie tym, co testy robią naraz](2026-09-25-tunit-dane-hooki-i-rownoleglosc-sterowanie-tym-co-testy/ARTICLE.md) | Testy w TUnit biegną domyślnie równolegle — data-driven (`[Arguments]`, `[MethodDataSource]`, Matrix), hooki w trzech zakresach i sterowanie współbieżnością, zmierzone na żywo (36/36 zielone). | [Kod](2026-09-25-tunit-dane-hooki-i-rownoleglosc-sterowanie-tym-co-testy/code/) |
| 2026-09-24 | [TUnit: pierwszy test bez refleksji w runtime](2026-09-24-tunit-pierwszy-test-bez-refleksji-w-runtime/ARTICLE.md) | Source generators zamiast refleksji, `await Assert.That(...)`, i realna pułapka z .NET | [Kod](2026-09-24-tunit-pierwszy-test-bez-refleksji-w-runtime/code/) |
<!-- kolejne wiersze dopisywane automatycznie, najnowsze na górze -->

---

<div align="center">

[← spis rubryk](../../README.md)

</div>
