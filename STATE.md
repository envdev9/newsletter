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
  - Zostało w .NET 10 m.in.: lambda modifiers bez typów, `Span` conversions, inne nowości → potem .NET 11.
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
- Następny poziom: realnie zweryfikować `ansible-vault` (encrypt/view/encrypt_string), kolekcje i
  `ansible-galaxy`, własne filtry/lookupy, `include_tasks` vs `import_tasks`, `strategy`/`serial`, Molecule.

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
- Następny poziom: (po weryfikacji JDK 21) build features, Composite builds, matrix/`parallelTests`,
  Kotlin DSL — wersjonowanie w repo, integracja z Docker.

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
- Następny poziom: własne asercje, testy z Aspire/WebApplicationFactory, `[AfterEvery]`, warunkowy retry.

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
- Następny poziom: integracje z zewnętrznymi zasobami (Postgres/Redis, gdy Docker ma miejsce),
  parametry/sekrety, WithEnvironment, testy AppHosta w TUnit.

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
- Następny poziom: routing (topologia, exchange), przejście na RabbitMQ, trwałe repozytorium sag.

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
- Następne: hook `PostToolUse` uruchamiający `dotnet format`/testy po edycji, skill do
  SQL (przegląd planu/indeksów), Angular (review komponentu na signals), konfiguracja `.claude/` w zespole.

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
- Następne: subagenci w praktyce (własny agent w `.claude/agents/`, izolacja kontekstu,
  ograniczanie narzędzi), pętla z weryfikacją (headless `claude -p`), hooki `PreCompact`/`SessionStart`.

### 🧠 AI — zarządzanie kontekstem
- Omówione elementy: kolejność warstw kontekstu (system→narzędzia/MCP→pamięć→historia→
  system-reminder→bieżąca tura), prompt caching i dlaczego kolejność ma znaczenie
  ekonomicznie, transkrypty `.jsonl`, kiedy delegować do subagenta, `grep`/`head` vs
  `cat` (zmierzone: 619× mniej kontekstu) — wydanie #1, 2026-09-24.
- Następne: kompaktowanie/`/compact`, strategie dzielenia bardzo dużych zadań na
  łańcuchy subagentów, budżetowanie kontekstu w długich sesjach.

### ✍️ AI — prompty dla developera
- Omówione elementy: 5 par zły/dobry prompt (konkretność+pliki/linie, "dlaczego" vs
  "co", niejednoznaczność, format odpowiedzi, zakres zmiany) — wydanie #1, 2026-09-24.
  Zweryfikowane skryptem walidującym przykłady (5/5 OK, plus test negatywny wykrywający
  błąd).
- Następne: prompty do debugowania, prompty do code review, iteracyjne dopracowywanie
  promptu w trakcie sesji.

### 🅰️ Angular
- Aktualny poziom trudności: **podstawy (opanowane)**
- Omówione koncepty: `signal()`/`computed()`/`effect()` jako fundament, `@ngrx/signals`
  (signal store) na tym fundamencie, komponenty: counter, shipping-picker,
  quantity-stepper, cart (signal store), search (RxJS) — wydanie #1, 2026-09-24.
  Zweryfikowane `npm ci` + `npx ng build` (build przeszedł, 7.75s) — budowane w
  `/dev/shm` z powodu pełnego dysku systemowego, dysk repo nietknięty.
- Wydanie #2, 2026-09-25: **POMINIĘTE** — na maszynie brak Node/npm (toolchain z /dev/shm
  zniknął, instalacja niedozwolona). Do nadrobienia, gdy Node będzie dostępny.
- Wydanie #3, 2026-09-26: **POMINIĘTE** — nadal brak Node/npm na maszynie (`node: command not found`).
- Następny poziom: nowości Angular 19+ poza signals, `linkedSignal`, `resource()`,
  integracja signal store z HTTP.

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
- Następny poziom: `OPTION (RECOMPILE)`/`OPTIMIZE FOR`, Query Store, filtered indexes,
  columnstore, deadlocki/blokady.

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
- Następny poziom (po weryfikacji): filtrowanie + indeks (iterative scan), partycjonowanie,
  quantization (halfvec/bit), pgvector z .NET (Npgsql + EF Core).

### 🔐 Certyfikaty i TLS (X.509)
- Aktualny poziom trudności: **podstawy (opanowane)**
- Cel nadrzędny tej rubryki: poziom mistrzowski (patrz TOPICS.md, pkt 14).
- Omówione koncepty: klucz publiczny/prywatny, podpis cyfrowy, łańcuch zaufania
  root→intermediate→leaf, self-signed vs CA-signed, TLS 1.2 vs 1.3, `X509Certificate2` +
  `X509Chain` w .NET — wydanie #1, 2026-09-24. Zweryfikowane realnym `openssl` (własne
  CA + certyfikat + "rogue" self-signed) i realnym `dotnet run` (3 scenariusze walidacji
  łańcucha, w tym poprawne odrzucenie self-signed: `UntrustedRoot`).
- Następny poziom: mTLS (klient i serwer wzajemnie się weryfikują), OCSP/CRL,
  Kestrel/HTTPS konfiguracja w .NET, typowe błędy zaufania w produkcji i jak je
  diagnozować.
