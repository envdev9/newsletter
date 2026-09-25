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
- Gdy funkcje .NET 10 się wyczerpią → .NET 11 → (dalsze nowości) → schodzimy w dół:
  9 → 8 → 7 → 6, potem wracamy do najnowszej dostępnej wersji.

### 🔧 Ansible
- Aktualny poziom trudności: **podstawy (opanowane)**
- Omówione koncepty: inventory, play, task, module, idempotencja, zmienne (`vars`),
  moduły `file`/`copy`/`debug`, `ansible_connection=local` — wydanie #1, 2026-09-24.
  Zweryfikowane 3 realnymi przebiegami (w tym dowód idempotencji: drugi przebieg
  `changed=0`).
- Następny poziom: handlery (`handlers`/`notify`), role, szablony Jinja2 (`template`),
  warunki (`when`), pętle (`loop`).

### 🏗️ TeamCity
- Aktualny poziom trudności: **podstawy (częściowo — patrz ograniczenie)**
- Omówione koncepty: VCS root, build configuration, build step, trigger, Kotlin DSL
  (`.teamcity/settings.kts`), standalone kompilacja configu przez Maven
  (`configs-dsl-kotlin-latest`) — wydanie #1, 2026-09-24.
- Ograniczenie środowiska: `mvn compile` padł na `UnsupportedClassVersionError` — wtyczka
  `teamcity-configs-maven-plugin:2026.3-dsl6` wymaga JDK 21, maszyna ma JDK 17. Sama
  poprawność `settings.kts` NIE została w pełni potwierdzona kompilacją. Jeśli JDK 21
  będzie dostępne w przyszłości, warto to wydanie zweryfikować retroaktywnie.
- Następny poziom: templates, dependencies (snapshot/artifact), parametry.

### 🧪 TUnit
- Aktualny poziom trudności: **podstawy (opanowane)**
- Omówione koncepty: `[Test]`, `await Assert.That(...)`, source generators vs refleksja
  (xUnit/NUnit/MSTest), asercja na wyjątku i na `bool` — wydanie #1, 2026-09-24.
  Zweryfikowane `dotnet test` (3/3 testy przeszły). Napotkana i udokumentowana pułapka:
  .NET 10 SDK wymaga `global.json` z `"test": {"runner": "Microsoft.Testing.Platform"}`.
- Następny poziom: data-driven testy (`[Arguments]`/`[MethodDataSource]`), hooki
  (`[Before]`/`[After]`), równoległość.

### ✈️ Aspire
- Aktualny poziom trudności: **podstawy (opanowane)**
- Omówione koncepty: `AppHost`, `DistributedApplication.CreateBuilder`, `AddProject<T>`,
  dashboard, OTLP/OpenTelemetry wbudowane, service discovery — wydanie #1, 2026-09-24.
  Zweryfikowane realnym `dotnet run` (dashboard + endpoint wstały, logi potwierdzone).
  Celowo bez zewnętrznych kontenerów (Postgres/Redis/RabbitMQ) w tym wydaniu.
- Następny poziom: integracje z zewnętrznymi zasobami (Postgres/Redis), service
  discovery między dwoma własnymi serwisami, telemetry w praktyce.

### 📨 Messaging .NET (MassTransit)
- Aktualny poziom trudności: **podstawy (opanowane)**
- Omówione koncepty: `Publish` vs `Send`, consumer, bus, transport in-memory
  (`UsingInMemory`) — wydanie #1, 2026-09-24. Zweryfikowane realnym `dotnet run`
  (konsument odebrał wiadomość, output potwierdzony). Użyta wersja: MassTransit 8.5.10
  (ostatnia Apache-2.0 bez wymogu licencji — 9+ wymaga `SetLicense`).
- Następny poziom: sagas, routing, retry/error handling, przejście na RabbitMQ.

### 🤖 AI — Claude Code dla .NET/Angular/SQL
- Omówione przypadki użycia: slash command generujący testy xUnit dla klasy C#, hook
  `PreToolUse` blokujący zapis SQL migration bez sekcji rollback, skill do code-review
  komponentu Angular — wydanie #1, 2026-09-24. Hook zweryfikowany realnymi uruchomieniami
  (blokuje/przepuszcza poprawnie).
- Następne: więcej gotowych przypadków (np. hook walidujący konwencje commitów, skill do
  review migracji EF Core).

### ⚙️ AI — agentic loop / workflow kodowania
- Omówione elementy: pętla tool-use, różnica komenda/skill/subagent/hook (kto naciska
  spust), pełny diagram PreToolUse→wykonanie→PostToolUse, zagnieżdżenie subagenta —
  wydanie #1, 2026-09-24. Hooki zweryfikowane realnymi uruchomieniami z przykładowym
  JSON-em na stdin.
- Następne: `UserPromptSubmit`/`Stop`/`SubagentStop` w praktyce, budowanie własnego
  skilla od zera, kompozycja wielu hooków na tym samym evencie.

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
- Następny poziom: nowości Angular 19+ poza signals, `linkedSignal`, `resource()`,
  integracja signal store z HTTP.

### 🗄️ SQL Server
- Aktualny poziom trudności: **podstawy (kod gotowy, niezweryfikowany)**
- Kod (generator danych, plan wykonania z/bez indeksu, `sys.dm_db_index_physical_stats`)
  napisany, ale NIE zweryfikowany realnym uruchomieniem — `docker pull
  mcr.microsoft.com/mssql/server:2022-latest` padł na `no space left on device`
  (dysk maszyny był przy <500MB wolnego). Do zrobienia przy następnej okazji: odpalić
  `code/run-demo.sh` gdy będzie więcej miejsca i dopisać realny output.
- Następny poziom (po zweryfikowaniu podstaw): statystyki, covering index, execution
  plan cache, parameter sniffing.

### 🧬 PostgreSQL — baza wektorowa (pgvector)
- Aktualny poziom trudności: **podstawy (opanowane)**
- Omówione koncepty: `CREATE EXTENSION vector`, kolumna `vector(N)`, IVFFlat vs HNSW,
  operatory `<->`/`<=>`/`<#>`, `EXPLAIN` i kiedy planner wybiera Seq Scan zamiast indeksu
  — wydanie #1, 2026-09-24. Zweryfikowane realnym kontenerem `pgvector/pgvector:pg16`,
  realnymi zapytaniami podobieństwa z sensownym wynikiem. Użyto deterministycznych
  wektorów demonstracyjnych (nie prawdziwego modelu embeddingowego — brak miejsca na
  dysku na `sentence-transformers`).
- Następny poziom: prawdziwy model embeddingowy (lekki, lokalny), hybrid search
  (wektor + pełnotekstowe), strojenie parametrów IVFFlat/HNSW (`lists`, `m`,
  `ef_construction`).

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
