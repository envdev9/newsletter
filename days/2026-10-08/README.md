<div align="center">

# 📰 TECH PRASÓWKA — Wydanie #15
### 8 października 2026

</div>

---

### 🔷 [.NET](dotnet/ARTICLE.md)
Serwer pchający zdarzenia po SSE (`System.Net.ServerSentEvents`) i WebSocket czytany jak zwykły `Stream` (`WebSocketStream`) — dwie sieciowe nowości .NET 10, obie sprawdzone w pamięci i dowiedzione jako brak w .NET 9.
→ [Artykuł](dotnet/ARTICLE.md) · [Kod](dotnet/code/)

### 🔧 [Ansible](ansible/ARTICLE.md)
Kto wygrywa, gdy zmienna ma 10 właścicieli? Dziesięć pojedynków warstw — od `role defaults` po `-e` — zmierzonych jednym playbookiem; zaskoczenie: `include_vars` bije `vars:` na tasku, a równorzędne grupy rozstrzyga alfabet.
→ [Artykuł](ansible/ARTICLE.md) · [Kod](ansible/code/)

### 🏗️ [TeamCity](teamcity/ARTICLE.md)
Łańcuch Compile → Test+Lint → Package → Summary w 10 linijkach Kotlina (`sequential`/`parallel`) — a domyślna reakcja `sequential` sprawia, że testy biegną nawet po padniętej kompilacji.
→ [Artykuł](teamcity/ARTICLE.md) · [Kod](teamcity/code/)

### 🧪 [TUnit](tunit/ARTICLE.md)
Wygasły certyfikat nadal podpisuje tokeny przyjmowane przez `JwtBearer`, chyba że sam dodasz sprawdzenie dat — plus dowód, że publikacja klucza w JWKS przed aktywacją usuwa pierwszy 401 po rotacji.
→ [Artykuł](tunit/ARTICLE.md) · [Kod](tunit/code/)

### ✈️ [Aspire](aspire/ARTICLE.md)
Jedna linijka `WithLifetime(ContainerLifetime.Persistent)` sprawiła, że Redis z danymi przeżył `kill -9` AppHosta i został podpięty przez następny — ale teraz to Ty go sprzątasz.
→ [Artykuł](aspire/ARTICLE.md) · [Kod](aspire/code/)

### 📨 [Messaging .NET z MassTransit](masstransit/ARTICLE.md)
Krok 4 padł i kompensacja kroku 2 też: MassTransit przerywa wtedy cofanie, krok 1 zostaje nietknięty, a zamiast `Faulted` dostajesz osobne `CompensationFailed`.
→ [Artykuł](masstransit/ARTICLE.md) · [Kod](masstransit/code/)

### 🤖 [AI — Claude Code dla .NET/Angular/SQL](ai-claude-code/ARTICLE.md)
`Contains` i `LIKE '%x%'` w EF Core czytają 371 stron zamiast 5 — skaner `ef-core-review` v2 łapie je po typie encji, a interceptor zapisuje prawdziwy plan zapytania; lista 5000 id: 29 ms vs 955 ms zależnie od trybu parametryzacji.
→ [Artykuł](ai-claude-code/ARTICLE.md) · [Kod](ai-claude-code/code/)

### ⚙️ [AI — agentic loop](ai-agentic-loop/ARTICLE.md)
→ [Artykuł](ai-agentic-loop/ARTICLE.md) · [Kod](ai-agentic-loop/code/)

### 🧠 [AI — zarządzanie kontekstem](ai-context/ARTICLE.md)
→ [Artykuł](ai-context/ARTICLE.md) · [Kod](ai-context/code/)

### ✍️ [AI — prompty dla developera](ai-prompts/ARTICLE.md)
→ [Artykuł](ai-prompts/ARTICLE.md) · [Kod](ai-prompts/code/)

### 🅰️ [Angular](angular/ARTICLE.md)
W Signal Forms są dwa różne „debounce" — jedno opóźnia zapis do modelu, drugie tylko request — a `submit()` w trakcie debounce potrafi zwalidować nieaktualny model.
→ [Artykuł](angular/ARTICLE.md) · [Kod](angular/code/)

### 🗄️ [SQL Server](sqlserver/ARTICLE.md)
→ [Artykuł](sqlserver/ARTICLE.md) · [Kod](sqlserver/code/)

### 🧬 [PostgreSQL jako baza wektorowa](postgres-vector/ARTICLE.md)
→ [Artykuł](postgres-vector/ARTICLE.md) · [Kod](postgres-vector/code/)

### 🔐 [Certyfikaty i TLS (X.509)](certificates/ARTICLE.md)
`SslStream` sam z siebie w ogóle nie sprawdza SCT — polityka Certificate Transparency musi siedzieć w callbacku, a jedno `return true` kasuje całe zabezpieczenie; 16 realnych handshake'ów TLS 1.3 to udowadnia.
→ [Artykuł](certificates/ARTICLE.md) · [Kod](certificates/code/)

---

<div align="center">

[← spis wszystkich wydań](../../README.md)

</div>
