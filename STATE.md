# Stan postępu

Czytaj to **przed** pisaniem wydania, aktualizuj **po**. To jedyna pamięć między
przebiegami — kolejny agent nie widzi tej rozmowy, tylko ten plik. Każdego dnia
aktualizowane są **wszystkie** sekcje poniżej (jedno wydanie = wszystkie rubryki).

## Ostatnie wydanie

- Numer: 1
- Data: 2026-09-24

## Postęp per rubryka

### 🔷 .NET
- Aktualna wersja w rotacji: **.NET 10**
- Opisane funkcje (żeby nie powtarzać):
  - [x] Extension members (właściwości/statyczne members w bloku `extension(Typ x)`) — wydanie #1, 2026-09-24
  - [x] File-based apps (`dotnet run plik.cs`, `#:package`) — wydanie #1, 2026-09-24
  - [x] Słowo kluczowe `field` (semi-auto properties, C# 14) — wydanie #2, 2026-09-25
  - [x] Null-conditional assignment (`a?.b = x`, `a?.b += x`; `?.` z `++` nie kompiluje się, CS1059) — wydanie #2, 2026-09-25
  - [x] `Enumerable.LeftJoin`/`RightJoin` (LINQ, .NET 10) — wydanie #3, 2026-09-26
  - [x] Partial constructors/events (C# 14; event z `add`/`remove` nie jest field-like → CS0079 przy `?.Invoke`) — wydanie #3, 2026-09-26. Zweryfikowane `dotnet run`; niezweryfikowane: LeftJoin w EF Core, prawdziwy source generator.
  - [x] Modyfikatory parametrów lambdy bez typów (`(text, out r) => ...`; `params` nadal wymaga typu, CS9272) — wydanie #4, 2026-09-27
  - [x] First-class Span (niejawne `T[]`/`string` → `ReadOnlySpan<T>`, extension methods na spanach) — wydanie #4, 2026-09-27. Zweryfikowane SDK 10.0.400; niezweryfikowane: inne metody `MemoryExtensions`, starsze TFM, `var f = (x, out y) => ...`.
  - [x] Kryptografia postkwantowa `MLDsa`/`MLKem` (FIPS 204/203, `System.Security.Cryptography`) — wydanie #5, 2026-09-28.
    Potwierdzone empirycznie jako nowość .NET 10 (SDK 9.0.316 vs 10.0.400: `CS0103` na net9.0). Na tej maszynie
    `IsSupported=false` (OpenSSL 3.0.2, wymaga 3.5+) — zweryfikowany tylko `PlatformNotSupportedException`, NIE
    zweryfikowano realnego sign/verify ani encapsulate/decapsulate.
  - [x] Generyczne uchwyty GC `GCHandle<T>`/`PinnedGCHandle<T>`/`WeakGCHandle<T>` (`System.Runtime.InteropServices`)
    — wydanie #5, 2026-09-28. W pełni zweryfikowane (`dotnet run -c Release`, 5 sekcji), potwierdzone jako nowość
    .NET 10 (`CS0308` na net9.0). Znaleziona i zmierzona, ale niewyjaśniona różnica: `PinnedGCHandle<string[]>` nie
    rzuca `ArgumentException: Object contains references`, w przeciwieństwie do starego `GCHandle.Alloc(_, Pinned)`.
  - Zostało: inne nowości .NET 10 runtime/BCL (np. System.Text.Json, LINQ, source-generated regex) → potem .NET 11.
- Gdy funkcje .NET 10 się wyczerpią → .NET 11 → (dalsze nowości) → schodzimy w dół:
  9 → 8 → 7 → 6, potem wracamy do najnowszej dostępnej wersji.

### 🔧 Ansible
- Aktualny poziom trudności: **podstawy (opanowane)**
- Omówione koncepty: inventory, play, task, module, idempotencja, zmienne (`vars`),
  moduły `file`/`copy`/`debug`, `ansible_connection=local` — wydanie #1, 2026-09-24.
  Zweryfikowane 3 realnymi przebiegami (w tym dowód idempotencji: drugi przebieg
  `changed=0`).
- Wydanie #2, 2026-09-25: rola `app_config`, szablony Jinja2 (`template`), pętle
  (`loop`/`loop_control`), `when`, `notify`/handlery (raz, tylko przy zmianie),
  `meta: flush_handlers`, `--check --diff`. Zweryfikowane realnie (ansible-core 2.17.14;
  drugi przebieg `changed=0`). Pułapka: `-e x=false` to string → `| bool`. Niezweryfikowane:
  prawdziwy `service` (become), `ansible-galaxy init`, zdalne SSH.
- Wydanie #3, 2026-09-26: inventory grupowe (`web`/`db`/`app:children`) + `group_vars`/`host_vars`,
  `block`/`rescue`/`always` (wdrożenie z rollbackiem), `register` + `failed_when`/`changed_when`,
  tagi, filtry Jinja2 (`combine`, `to_nice_json`, `hash`, `zip`/`extract`…), `no_log`. Zweryfikowane
  (ansible-core 2.17.14): syntax-check, 2 przebiegi (`changed=0`), rescue, tags/limit, `--check --diff`.
  Niezweryfikowane: `ansible-vault` (polecenie odrzucone przez środowisko — opisane, `vault.yml` w
  repo jawny z fikcyjnymi wartościami), `ansible-inventory --graph`, SSH/`become`, `validate`.
- Wydanie #4, 2026-09-27: własny filtr (`filter_plugins`: `mask_secret`, `to_env_lines`) i lookup (`kv_file`),
  `import_tasks` vs `include_tasks` (`--list-tasks`, tagi + `apply`, `when`, `loop`), `serial: [1, 2]` + `max_fail_percentage`
  (canary), `strategy: linear` vs `free`. ansible-core 2.17.14, syntax-check + 2 przebiegi (`changed=0`). Pułapki: tag na
  `include_tasks` nie obejmuje wnętrza (potrzebne `apply`); `import_tasks` + `loop` → błąd parsowania; `false` po interpolacji
  w filtrze Pythona = `False`; `serial` = osobny play per paczka; ansible w powłoce agenta wymaga `2>&1 | cat`.
  Niezweryfikowane: `ansible-vault` (encrypt odrzucone przez środowisko; komendy w README), `ansible-galaxy`/kolekcje, Molecule,
  `serial` z %, `throttle`, SSH/`become`.
- Następny poziom: `ansible-vault` (jeśli środowisko pozwoli), kolekcje i `ansible-galaxy`, Molecule, `throttle`, `delegate_to`, `async`/`poll`.

### 🏗️ TeamCity
- Aktualny poziom trudności: **podstawy (częściowo — patrz ograniczenie)**
- Omówione koncepty: VCS root, build configuration, build step, trigger, Kotlin DSL
  (`.teamcity/settings.kts`), standalone kompilacja configu przez Maven
  (`configs-dsl-kotlin-latest`) — wydanie #1, 2026-09-24.
- Ograniczenie środowiska: `mvn compile` padł na `UnsupportedClassVersionError` — wtyczka
  `teamcity-configs-maven-plugin:2026.3-dsl6` wymaga JDK 21, maszyna ma JDK 17. Sama
  poprawność `settings.kts` NIE została w pełni potwierdzona kompilacją. Jeśli JDK 21
  będzie dostępne w przyszłości, warto to wydanie zweryfikować retroaktywnie.
- Wydanie #3, 2026-09-26: pipeline .NET Build→Test→Pack — `template(...)` z dziedziczeniem i override,
  parametry (`env.`/`system.`/konfiguracyjne, `%param%`, typ `password`), snapshot vs artifact dependency,
  artifact rules, trigger na końcu łańcucha, `buildNumberPattern`. **Kompilacja NIEZWERYFIKOWANA** —
  pobranie JDK 21/Maven do /tmp odrzucone przez środowisko (mvn brak, java 17); składnia z dokumentacji.
  Do potwierdzenia: `password(label=, display=)`, `sameChainOrLastFinished()`, `requirements`.
  Zostawiony pusty katalog /tmp/tc-verify (nie dało się usunąć).
- Wydanie #4, 2026-09-27: build features (commit status publisher, swabra, perfmon), failure conditions (timeout,
  `failOnMetricChange` na liczbie testów, `failOnText`), Docker (`dockerImage` na kroku `script` vs `dockerCommand`),
  Composite build (`Type.COMPOSITE`), versioned settings. **Kompilacja NIEZWERYFIKOWANA po raz trzeci** (#1, #3, #4) —
  subagent miał zablokowany cały Bash, nie sprawdzał nawet JDK/Maven. Niepewna składnia oznaczona `[?]` w `settings.kts`:
  enumy `versionedSettings`, pola `failOnMetricChange`, `failOnText` (`reverse`), `commitStatusPublisher` (`github`/`personalToken`),
  `dockerImagePlatform`. Składnię można potwierdzić w UI (*Versioned Settings → Show DSL*).
- Następny poziom: `matrix`, `parallelTests`, `dockerCompose`, login do rejestru (`dockerSupport`), pull requests; przede wszystkim
  realna kompilacja (JDK 21 + Maven), gdy środowisko pozwoli.

### 🧪 TUnit
- Aktualny poziom trudności: **podstawy (opanowane)**
- Omówione koncepty: `[Test]`, `await Assert.That(...)`, source generators vs refleksja
  (xUnit/NUnit/MSTest), asercja na wyjątku i na `bool` — wydanie #1, 2026-09-24.
  Zweryfikowane `dotnet test` (3/3 testy przeszły). Napotkana i udokumentowana pułapka:
  .NET 10 SDK wymaga `global.json` z `"test": {"runner": "Microsoft.Testing.Platform"}`.
- Wydanie #2, 2026-09-25: `[Arguments]`, `[MethodDataSource]`, `[MatrixDataSource]`, hooki
  `[Before]`/`[After]` (Test/Class/Assembly), `[NotInParallel]`, `[DependsOn]`,
  `[ParallelLimiter<T>]`. TUnit 1.69.0, `dotnet test` 36/36; szczyt równoległości zmierzony
  (6 / 1 / 2). Niezweryfikowane (opisane wprost): DependsOn przy porażce, `[ClassDataSource]`,
  `[BeforeEvery]`.
- Wydanie #3, 2026-09-26: `[ClassDataSource<T>]` + `SharedType` (PerTestSession/PerClass/Keyed/None),
  fixture z `IAsyncInitializer`/`IAsyncDisposable`, `[Retry]` + `CurrentRetryAttempt`, `[Timeout]`,
  `[BeforeEvery(Test)]`, `[After(TestSession)]`. TUnit 1.69.0, `dotnet test` 18/18. Pułapka:
  `[ClassDataSource]` na parametrze → TUnit0038/0070. Niezweryfikowane: `[AfterEvery]`, BeforeEvery
  Class/Assembly, własne asercje (`Assertion<T>`), warunkowy retry.
- Wydanie #4, 2026-09-27: własne asercje (`Assertion<T>` + extension na `IAssertionSource<T>`, oraz
  `[GenerateAssertion]`, łączenie `.And`), `[AfterEvery(Test)]` (widzi wynik testu), warunkowy retry
  (`RetryAttribute.ShouldRetry`, ponawia tylko `TransientException`). TUnit 1.69.0, `dotnet test` 6/6.
  Pułapki: TUnit0028 (własny `[AttributeUsage]` zabroniony), numeracja prób w `ShouldRetry` od 1.
  Niezweryfikowane: `[AfterEvery(Class/Assembly)]`, WebApplicationFactory, `ShouldRetry` + `[Timeout]`.
  Uwaga: w korzeniu repo powstał niechciany `TestResults/` (nie commitowany, nie dało się usunąć).
- Następny poziom: testy z Aspire/WebApplicationFactory, `[AfterEvery]` Class/Assembly.

### ✈️ Aspire
- Aktualny poziom trudności: **podstawy (opanowane)**
- Omówione koncepty: `AppHost`, `DistributedApplication.CreateBuilder`, `AddProject<T>`,
  dashboard, OTLP/OpenTelemetry wbudowane, service discovery — wydanie #1, 2026-09-24.
  Zweryfikowane realnym `dotnet run` (dashboard + endpoint wstały, logi potwierdzone).
  Celowo bez zewnętrznych kontenerów (Postgres/Redis/RabbitMQ) w tym wydaniu.
- Wydanie #2, 2026-09-25: NIEDOKOŃCZONE (kod przepadł) — nadrobione w wydaniu #3.
- Wydanie #3, 2026-09-26: dwa serwisy (CatalogApi + StoreApi), service discovery
  `WithReference`, `WaitFor` + `WithHttpHealthCheck`, ServiceDefaults (health, OTel, resilience),
  własny ActivitySource/Meter. Aspire 13.5.2. Zweryfikowane bez curl: `Store.Verify`
  (`DistributedApplicationTestingBuilder` + HttpClient), 10× PASS. Niezweryfikowane: dashboard,
  realny eksport OTLP, retry/circuit breaker przy awarii, wildcard `Store.*` w AddSource/AddMeter.
- Wydanie #4, 2026-09-27: `AddParameter` (z konfiguracji / `secret: true` / wartość stała ignorująca konfigurację),
  przeciążenia `WithEnvironment` (literał, parametr, `ReferenceExpression`, callback z `IsRunMode`), `AddExecutable`
  + logi przez `ResourceLoggerService`, brak sekretu → `FailedToStart`, test AppHosta z argumentami `Parameters:...`.
  Aspire 13.5.2, `Config.Verify` → WSZYSTKO OK. Niezweryfikowane: kontenery (Postgres/Redis — brak pobranych obrazów,
  nie pobierano), dashboard/maskowanie sekretów, user-secrets, `publish`; `appsettings.json` AppHosta jako źródło
  `Parameters:*` w teście nie zadziałał (nie zbadano).
- Następny poziom: integracje z kontenerami (Postgres/Redis, gdy Docker ma obrazy/miejsce), user-secrets, testy AppHosta w TUnit.

### 📨 Messaging .NET (MassTransit)
- Aktualny poziom trudności: **podstawy (opanowane)**
- Omówione koncepty: `Publish` vs `Send`, consumer, bus, transport in-memory
  (`UsingInMemory`) — wydanie #1, 2026-09-24. Zweryfikowane realnym `dotnet run`
  (konsument odebrał wiadomość, output potwierdzony). Użyta wersja: MassTransit 8.5.10
  (ostatnia Apache-2.0 bez wymogu licencji — 9+ wymaga `SetLicense`).
- Wydanie #2, 2026-09-25: `UseMessageRetry` (Immediate/Interval/Exponential, `Ignore<T>`),
  `Fault<T>`, kolejki `_error`/`_skipped` (in-memory je tworzy), delayed redelivery,
  `UseInMemoryOutbox` — zweryfikowane realnym `dotnet run` (MassTransit 8.5.10). Niezweryfikowane:
  zachowanie na prawdziwym brokerze, transakcyjny outbox z bazą.
- Wydanie #3, 2026-09-26: sagi — `MassTransitStateMachine<T>`, `CorrelateById`, `Initially`/`During`/
  `Ignore`/`Finally`, `SetCompletedWhenFinalized`, `Schedule`/`Unschedule` (timeout), `CompositeEvent`,
  `Fault<T>` przy evencie w złym stanie; pułapka: handler składnika composite biegnie po przejściu
  composite → guard. 6 scenariuszy zweryfikowane `dotnet run` (8.5.10, in-memory). Niezweryfikowane:
  trwałe repozytoria sag (EF/Mongo/Redis), RabbitMQ/ASB scheduler, wyścig płatność vs timeout, kompensacje.
- Wydanie #4, 2026-09-27: `KebabCaseEndpointNameFormatter` + `ConfigureEndpoints` (kolejka `dev-price`),
  `ConsumerDefinition` (jawny `EndpointName`, `ConcurrentMessageLimit`), Request/Response (`GetResponse<A, B>`,
  `RequestFaultException`, `RequestTimeoutException`), filtry consume/send (`IFilter`, open generic w DI), `Send` po adresie
  `queue:`. Pułapki: `Publish` nie przechodzi przez filtr `Send`; klient dostaje odpowiedź przed końcem filtra consume.
  MassTransit 8.5.10, in-memory, `dotnet run`. Niezweryfikowane: RabbitMQ (exchange'e/bindingi), `UsePublishFilter`,
  kolejność filtrów, RoutingSlip/Courier, trwałe repozytoria sag.
- Następny poziom: przejście na RabbitMQ (topologia, exchange), RoutingSlip/Courier, trwałe repozytorium sag.

### 🤖 AI — Claude Code dla .NET/Angular/SQL
- Omówione przypadki użycia: slash command generujący testy xUnit dla klasy C#, hook
  `PreToolUse` blokujący zapis SQL migration bez sekcji rollback, skill do code-review
  komponentu Angular — wydanie #1, 2026-09-24. Hook zweryfikowany realnymi uruchomieniami
  (blokuje/przepuszcza poprawnie).
- Wydanie #2, 2026-09-25: hook `PreToolUse` na `Bash` wymuszający Conventional Commits
  (exit 2 + stderr; obsługa `-am`, `--message=`, `git -C`, `&&`, heredoc; 21/21 przypadków
  testowych) i skill `ef-migration-review` (skaner `scan_migration.py` + instrukcja). Zweryfikowane
  realnymi uruchomieniami. Niezweryfikowane: wpięcie w żywej sesji Claude Code, auto-aktywacja
  skilla, migracje z prawdziwego `dotnet ef`. Znane luki hooka: `-F plik`, zmienna powłoki, `--amend --no-edit`.
- Wydanie #3, 2026-09-26: hook `PostToolUse` (po edycji `.cs`: `dotnet format` + `dotnet build`, błąd → exit 2)
  i zespołowy `settings.json` (permissions + hook) z linterem `validate_settings.py`. Zweryfikowane na .NET SDK
  10.0.400: demo 5/5, walidator OK. Pułapka: `dotnet format --include` z bezwzględną ścieżką nic nie robi
  (exit 0). Niezweryfikowane: żywa sesja, payload `PostToolUse`, składnia/pierwszeństwo `permissions`.
  Zapis do `.claude/` był odrzucony → katalogi `claude-hooks/`, `claude-config/`. Zostały `bin/`,`obj/`
  (gitignore) i pusty `code/team-config/`.
- Wydanie #4, 2026-09-27: skill `sql-plan-review` (`scan_sql.py` — reguły antywzorców T-SQL, `scan_plan.py` — plan XML:
  missing index, scan, Key Lookup, niejawna konwersja, spill, rozjazd estymat). `run_tests.py` 4/4 (Python 3.10). Niezweryfikowane:
  brak SQL Servera/sqlcmd — plany to ręczne fixtury, nazwy atrybutów XML z pamięci, progi arbitralne, żywa sesja Claude Code.
- Następne: skill Angular (review komponentu na signals), skill SQL na prawdziwym planie z `sqlcmd`.

### ⚙️ AI — agentic loop / workflow kodowania
- Omówione elementy: pętla tool-use, różnica komenda/skill/subagent/hook (kto naciska
  spust), pełny diagram PreToolUse→wykonanie→PostToolUse, zagnieżdżenie subagenta —
  wydanie #1, 2026-09-24. Hooki zweryfikowane realnymi uruchomieniami z przykładowym
  JSON-em na stdin.
- Wydanie #2, 2026-09-25: `UserPromptSubmit` (exit 2 / stdout→kontekst), `Stop`/`SubagentStop`
  (bramka testów, `decision: block`, `stop_hook_active`), kompozycja wielu hooków (równoległość,
  brak gwarancji kolejności; symulator 1.05 s vs 2.10 s), własny skill `changelog-entry`.
  Zweryfikowane: demo 7/7, walidator skilla. Niezweryfikowane (opisane wprost): żywa sesja
  Claude Code, pola payloadu `SubagentStop`, reguły łączenia sprzecznych decyzji.
- Wydanie #3, 2026-09-26: własny subagent `dotnet-reviewer` (frontmatter, `tools: Read, Grep, Glob`,
  `description` jako mechanizm delegowania, izolacja kontekstu), pętla z weryfikacją (exit code testów,
  feedback, limit iteracji), hooki `PreCompact`/`SessionStart` (snapshot zadań i odtworzenie po compact).
  Zweryfikowane lokalnie w Pythonie: lint agenta, pętla (sukces w 2. iteracji / porażka przy limicie),
  demo hooków 7/7. Niezweryfikowane: `claude` CLI (`--version` odrzucone), `claude -p`, wybór agenta po
  `description`, egzekwowanie `tools`, kształt payloadów `PreCompact`/`SessionStart`; rolę agenta gra skrypt.
- Wydanie #4, 2026-09-27: wachlarz (fan-out) 4 reviewerów równolegle + scalanie (dedup, sort, `--top`, `PARTIAL` przy awarii
  workera), lokalny model reguł uprawnień (pułapka: `dotnet test && git push` pasuje do `dotnet test*`), bramka CI wokół
  `claude -p` z kodami wyjścia 10–14 i niezależnym weryfikatorem (`fake_claude.py` udaje agenta). `run_tests.py` 19/19 (Python 3.10).
  Niezweryfikowane: `claude` CLI (`--version` odrzucone), flagi `-p`/JSON, `permissionMode`, równoległość subagentów w żywej
  sesji, szkic GitHub Actions. Zostały `__pycache__/` w `code/`.
- Następne: skille ładowane przez agenta, `permissionMode` w frontmatterze agenta (po weryfikacji CLI), hooki w trybie headless, worktree dla równoległych agentów.

### 🧠 AI — zarządzanie kontekstem
- Omówione elementy: kolejność warstw kontekstu (system→narzędzia/MCP→pamięć→historia→
  system-reminder→bieżąca tura), prompt caching i dlaczego kolejność ma znaczenie
  ekonomicznie, transkrypty `.jsonl`, kiedy delegować do subagenta, `grep`/`head` vs
  `cat` (zmierzone: 619× mniej kontekstu) — wydanie #1, 2026-09-24.
- Wydanie #2 (nadrobione), 2026-09-26: metryka „token-tury” (rozmiar wyniku × liczba tur), `/compact`
  (co przeżywa/ginie, sterowanie), łańcuchy subagentów (wskaźniki do plików, kontrakt na rozmiar raportu),
  checklista budżetowania. Skrypty `gen_transcript.py`/`analyze_transcript.py`/`test_analyzer.py` (6/6)
  zweryfikowane na SYNTETYCZNYM transkrypcie (odczyt `~/.claude/projects` odrzucony) — liczby to
  ilustracja mechanizmu, nie pomiar. Niezweryfikowane: `/compact` z instrukcją, CLAUDE.md po compact,
  żywy łańcuch subagentów. Zostało `code/__pycache__/` (w .gitignore).
- Wydanie #3 rubryki, 2026-09-27: pamięć/`CLAUDE.md` jako stały koszt (hierarchia, import `@plik`, przycinanie, leniwe ładowanie
  z podkatalogów) i koszt definicji narzędzi MCP (per serwer, what-if „wyłącz serwer"). `ctxaudit.py` (`memory`/`mcp`), test 13/13
  (Python 3.10). Fixture: 1242→304 tok. (4,1×); MCP 2076 tok., serwer `tracker` 86%. Dane SYNTETYCZNE (odczyt `~/.claude/projects` i
  WebFetch odrzucone); tokeny = bajty/4. Reguły ładowania pamięci z pamięci autora — niezweryfikowane (tabela w artykule).
- Następne: analiza prawdziwego transkryptu (gdy odczyt dozwolony), filtrowanie/leniwe ładowanie narzędzi MCP, weryfikacja reguł CLAUDE.md w docs.

### ✍️ AI — prompty dla developera
- Omówione elementy: 5 par zły/dobry prompt (konkretność+pliki/linie, "dlaczego" vs
  "co", niejednoznaczność, format odpowiedzi, zakres zmiany) — wydanie #1, 2026-09-24.
  Zweryfikowane skryptem walidującym przykłady (5/5 OK, plus test negatywny wykrywający
  błąd).
- Wydanie #3, 2026-09-26: debugowanie .NET (stack trace, repro, hipotezy przed poprawką), debugowanie SQL
  (dane z planu), code review Angulara (skala ważności, czego nie komentować), iteracyjne dopracowywanie
  promptu (3 wersje: lint 0/9→4/9→9/9). `prompt_lint.py` zweryfikowany: 9/9 zgodnych, test negatywny
  (7/9, exit 1), `--strict`. Niezweryfikowane: jakość odpowiedzi modelu — lint to heurystyka regex,
  reguły dobrane pod własne przykłady.
- Wydanie #4, 2026-09-27: prompty do refaktoryzacji (cel strukturalny, „zachowanie bez zmian", testy charakteryzujące),
  migracji Newtonsoft → System.Text.Json (inwentarz→plan→zmiany, „zatrzymaj się i zapytaj"), few-shot ze schematem i formatem
  wyjścia, CLAUDE.md jako trwały prompt. `prompt_lint2.py`: 8/8, test negatywny 6/7 (exit 1), `--strict`; golden-master (.NET 10)
  672 przypadki/0 różnic, mutant 37 różnic. Niezweryfikowane: jakość odpowiedzi modelu (żaden model nie uruchamiany), reguły
  lintu to regexy dobrane pod własne przykłady, próg 60 linii umowny.
- Następne: ewaluacja promptów na prawdziwym modelu (gdy dostępny), prompty do generowania testów i dokumentacji, łańcuchy promptów.

### 🅰️ Angular
- Aktualny poziom trudności: **podstawy (opanowane)**
- Omówione koncepty: `signal()`/`computed()`/`effect()` jako fundament, `@ngrx/signals`
  (signal store) na tym fundamencie, komponenty: counter, shipping-picker,
  quantity-stepper, cart (signal store), search (RxJS) — wydanie #1, 2026-09-24.
  Zweryfikowane `npm ci` + `npx ng build` (build przeszedł, 7.75s) — budowane w
  `/dev/shm` z powodu pełnego dysku systemowego, dysk repo nietknięty.
- Wydanie #2, 2026-09-25: **POMINIĘTE** — na maszynie brak Node/npm (toolchain z /dev/shm
  zniknął, instalacja niedozwolona). Do nadrobienia, gdy Node będzie dostępny.
- Wydanie #3, 2026-09-26: pierwotnie pominięte (brak Node), nadrobione tego samego dnia gdy Node v22.23.3
  był dostępny: `linkedSignal` (`source`/`computation` z poprzednią wartością), `httpResource`
  (`params`, nie `request`), `resource()`/`rxResource` (tylko z typów, bez kodu), signal store + HTTP
  (`withState`/`withComputed`/`withMethods`, `rxMethod`: debounceTime→distinctUntilChanged→switchMap,
  `catchError` wewnątrz), switchMap vs exhaustMap vs concatMap. Angular 22.2.0, @ngrx/signals 22.0.1,
  rxjs 7.8.2. Zweryfikowane: `npm ci`, `ng build`, `ng test` 8/8 (Vitest+jsdom). Pułapka: `npm install`
  bez lockfile'a padł → `--legacy-peer-deps`. Niezweryfikowane: `ng serve`, `resource()` z własnym loaderem,
  `tapResponse`. W `code/` zostały `node_modules/`, `dist/`, `.angular/` (w .gitignore).
- Wydanie #4, 2026-09-27: `withComponentInputBinding` (param ścieżki, query param i dane resolvera → `input()`),
  `ResolveFn` z `RedirectCommand` na `/not-found`, `@defer (when …)` sterowany `?tab=comments` + `@loading`/`@error`.
  Zweryfikowane: `npm ci`, `ng build` (osobny chunk komentarzy), `ng test` 6/6 (`RouterTestingHarness`). Pułapka:
  literalne `@defer` w szablonie → NG5002 (użyć `&#64;`). Niezweryfikowane: `ng serve`/przeglądarka, `DeferBlockFixture`
  (test czeka 300 ms — kruchy), inne wyzwalacze `@defer`.
- Następny poziom: formularze na signals (Signal Forms), SSR/hydration, `resource()` z własnym loaderem, `tapResponse`.

### 🗄️ SQL Server
- Aktualny poziom trudności: **podstawy (kod gotowy, niezweryfikowany)**
- Kod (generator danych, plan wykonania z/bez indeksu, `sys.dm_db_index_physical_stats`)
  napisany, ale NIE zweryfikowany realnym uruchomieniem — `docker pull
  mcr.microsoft.com/mssql/server:2022-latest` padł na `no space left on device`
  (dysk maszyny był przy <500MB wolnego). Do zrobienia przy następnej okazji: odpalić
  `code/run-demo.sh` gdy będzie więcej miejsca i dopisać realny output.
- Wydanie #2, 2026-09-25: statystyki (histogram), Key Lookup, covering index (`INCLUDE`),
  parameter sniffing + plan cache (skośny rozkład: ta sama procedura 21 vs 600 350
  logical reads). Skrypty 01–05 zweryfikowane realnie na SQL Server 2022 (RTM-CU27) w
  Dockerze, ręcznymi `docker exec … sqlcmd` (samo `run-demo.sh` zablokowane uprawnieniami).
- Wydanie #1 (podstawy, days/2026-09-24) nadal bez realnego outputu — krok 0 pominięty
  (uruchomienie run-demo.sh odrzucone przez uprawnienia). Dopisać output przy okazji.
- Wydanie #3, 2026-09-26: leczenie parameter sniffingu (`OPTION (RECOMPILE)`, `OPTIMIZE FOR UNKNOWN`,
  `OPTIMIZE FOR (@p=1)`; 600 350 vs 21 vs 2 486 reads; koszt RECOMPILE 574 vs 5 414 ms/2000 wywołań),
  Query Store (`sys.query_store_*`, regresja planu, `sp_query_store_force_plan`/`unforce`), filtered index
  na kolejce zadań (6 846 → 3 → 2 reads; pułapka: zapytanie z parametrem pomija indeks bez RECOMPILE).
  Skrypty 01–05 zweryfikowane realnie (SQL Server 2022 RTM-CU27, ręcznie docker exec). Niezweryfikowane:
  cały `run-demo.sh`, `06-cleanup.sql`, wymuszony plan po zniknięciu indeksu, Query Store hints. PSP
  optimization nie zadziałało w tym scenariuszu (przyczyny nie zbadane). Krok 0 (weryfikacja #1) nadal
  pominięty — uruchomienie `run-demo.sh` odrzucone przez uprawnienia.
- Wydanie #4, 2026-09-27: deadlock (dwie sesje, błąd 1205, graf z `system_health`, naprawa spójną kolejnością blokad `UPDLOCK`),
  blokowanie czytelnika vs `READ_COMMITTED_SNAPSHOT` (4 762 ms vs 0 ms), columnstore vs rowstore na 5 mln wierszy (33,6 vs 189,1 MB;
  agregacja 27 ms vs 892 ms, batch mode, eliminacja segmentów po sortowaniu: skipped 4). SQL Server 2022 RTM-CU27, skrypty 01–09
  zweryfikowane ręcznym `docker exec sqlcmd`. Pułapki: `.xel` z opóźnieniem (ring_buffer szybciej), XML w sqlcmd wymaga `-I`,
  `ROLLBACK IMMEDIATE` zabija pisarza, `INSERT…ORDER BY` nie sortuje rowgroupów. Niezweryfikowane: cały `run-demo.sh`, `10-cleanup.sql`,
  nonclustered columnstore, UPDATE/DELETE w columnstore, szkic C# dla 1205, wyniki bez MAXDOP 1. Krok 0 (weryfikacja #1) nadal
  pominięty — `run-demo.sh` odrzucone przez uprawnienia (Docker i miejsce OK).
- Następny poziom: Query Store hints, PSP optimization, nonclustered columnstore na OLTP (delta store, `REORGANIZE`), `SERIALIZABLE`/`sp_getapplock`.

### 🧬 PostgreSQL — baza wektorowa (pgvector)
- Aktualny poziom trudności: **podstawy (opanowane)**
- Omówione koncepty: `CREATE EXTENSION vector`, kolumna `vector(N)`, IVFFlat vs HNSW,
  operatory `<->`/`<=>`/`<#>`, `EXPLAIN` i kiedy planner wybiera Seq Scan zamiast indeksu
  — wydanie #1, 2026-09-24. Zweryfikowane realnym kontenerem `pgvector/pgvector:pg16`,
  realnymi zapytaniami podobieństwa z sensownym wynikiem. Użyto deterministycznych
  wektorów demonstracyjnych (nie prawdziwego modelu embeddingowego — brak miejsca na
  dysku na `sentence-transformers`).
- Wydanie #2, 2026-09-25: hybrid search (tsvector/GIN + wektor, Reciprocal Rank Fusion),
  prawdziwy model `paraphrase-multilingual-MiniLM-L12-v2` przez `fastembed`, strojenie
  IVFFlat (`lists`/`probes`) i HNSW (`m`/`ef_construction`/`ef_search`) z pomiarem recall@10.
  **Kod napisany, NIEZWERYFIKOWANY** — uruchomienie `run-demo.sh` odrzucone przez
  uprawnienia; w artykule brak zmierzonych liczb. Do zrobienia: odpalić `run-demo.sh`
  i wkleić prawdziwy output.
- Wydanie #3, 2026-09-26: problem post-filtrowania w HNSW (recall 0,019 z filtrem tenanta),
  `hnsw.iterative_scan` (`strict_order`/`relaxed_order`, `max_scan_tuples`; recall 0,91–0,93), B-tree na
  kolumnie filtra (nie wystarcza), partial index HNSW (408 kB), kwantyzacja `halfvec` (indeks 54 vs 79 MB,
  recall bez zmian) i `bit` + rerank (8,5 MB vs 156 MB, ale recall 0,45–0,58). pgvector 0.8.6 / PG 16.15.
  Zweryfikowane realnie SQL-em (ręcznie docker exec), dane SYNTETYCZNE (deterministyczne, bez modelu).
  Niezweryfikowane: cały `run-demo.sh`, partycjonowanie, `halfvec` jako typ kolumny, Npgsql+Pgvector (.NET),
  kod z wydania #2 (nadal niezweryfikowany).
- Wydanie #4, 2026-09-27: pgvector z .NET — Npgsql 10.0.3 + `Pgvector` 0.3.2 (`UseVector()`, typ `Vector`, binary COPY 20 000 wierszy
  w 825 ms), kNN z parametrem, HNSW `ef_search` 10/40/200 → recall@10 0,972/1,0/1,0 (1,47–2,54 ms vs Seq Scan 22,1 ms), `SET LOCAL`,
  EF Core (`Pgvector.EntityFrameworkCore` 0.3.0: `vector(64)`, indeks HNSW z modelu, `CosineDistance`). .NET 10.0.400, PG 16.15, pgvector
  0.8.6, dane SYNTETYCZNE. Pułapki: `float[]`→`real[]` (`operator does not exist`), zły wymiar, EF `Id=0` → `ValueGeneratedNever()`, pakiet EF
  ściąga EF Core 9, budowa HNSW niedeterministyczna (recall 0,956–0,994). Niezweryfikowane: `run-demo.sh` jako całość, migracje `dotnet ef`,
  `L2Distance`/`MaxInnerProduct`, użycie HNSW przez zapytanie EF, `halfvec` w C#, kod z #2 (fastembed) nadal niezweryfikowany.
- Następny poziom: partycjonowanie z HNSW, migracje EF z indeksem HNSW, `HalfVector`, `iterative_scan` w .NET z pulą połączeń,
  naprawa i uruchomienie kodu z #2 (realne embeddingi).

### 🔐 Certyfikaty i TLS (X.509)
- Aktualny poziom trudności: **podstawy (opanowane)**
- Cel nadrzędny tej rubryki: poziom mistrzowski (patrz TOPICS.md, pkt 14).
- Omówione koncepty: klucz publiczny/prywatny, podpis cyfrowy, łańcuch zaufania
  root→intermediate→leaf, self-signed vs CA-signed, TLS 1.2 vs 1.3, `X509Certificate2` +
  `X509Chain` w .NET — wydanie #1, 2026-09-24. Zweryfikowane realnym `openssl` (własne
  CA + certyfikat + "rogue" self-signed) i realnym `dotnet run` (3 scenariusze walidacji
  łańcucha, w tym poprawne odrzucenie self-signed: `UntrustedRoot`).
- Wydanie #2 (25.09) nie powstało (brak artykułu) — nie nadrabiane.
- Wydanie #3, 2026-09-26: mTLS w Kestrelu (`RequireCertificate`, `CustomRootTrust`, EKU clientAuth),
  PKI root→intermediate (pathlen:0)→serwer/klient przez `openssl ca`, `HttpClient` z certyfikatem klienta,
  katalog błędów (brak certu, zły EKU, wygasły, obcy wystawca, brak intermediate, IP poza SAN, CRL
  `certificate revoked`). Zweryfikowane `dotnet run` (net10.0) + openssl. Ustalenia: .NET z
  `RevocationMode.NoCheck` przepuszcza odwołany cert; brak SAN przechodzi dla `localhost` (fallback do CN).
  Niezweryfikowane: cały `generate-mtls-pki.sh` jako skrypt (uruchomienie odrzucone; komendy ręcznie),
  OCSP/stapling, włączone sprawdzanie CRL w .NET, przeglądarki/AIA, Windows/PFX, nieznany status `PartialChain` w scenariuszu B.
- Wydanie #4, 2026-09-27: revocation w .NET (macierz `NoCheck`/`Offline`/`Online` × zdrowy/odwołany/martwy CDP, lokalny serwer CRL),
  OCSP (`openssl ocsp` responder), stapling (`s_server -status_file`), TLS 1.3 (`-trace`, negatyw `-tls1_2`), własny `X509Store`
  (`CurrentUser\PrasowkaDemo`), rotacja w Kestrelu bez restartu (`ServerCertificateSelector`), pinning SPKI (5 scenariuszy).
  .NET 10.0.400, OpenSSL 3.0.2. Pułapki: `Offline` czyta tylko cache (pusty → `RevocationStatusUnknown`, `Build=false`); martwy CDP
  ≠ „dobry"; .NET/Linux użył CRL, nie OCSP; przeterminowany CRL przepuszczony przez .NET (openssl odrzuca); klucz z
  `CreateFromPemFile` efemeryczny (do magazynu przez PFX + `PersistKeySet`); pin SPKI nie przeżywa zmiany klucza → pin zapasowy.
  Niezweryfikowane: `setup-pki.sh` jako całość (odrzucone; komendy ręcznie), OCSP inicjowany przez .NET, stapling w Kestrelu,
  `SslStream` z revocation, Windows/macOS, Must-Staple, ACME; niewyjaśnione: przeterminowany CRL w .NET, `Response Verify Failure`.
- Następny poziom: ACME/Let's Encrypt, Must-Staple, revocation w `SslStream`/Kestrelu, Windows/macOS store, CT logs, DANE/CAA.
