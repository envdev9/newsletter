<div align="center">

# 📰 TECH PRASÓWKA — Wydanie #5
### 28 września 2026

</div>

---

### 🔷 [.NET](dotnet/ARTICLE.md)
Kryptografia postkwantowa (`MLDsa`/`MLKem`, FIPS 203/204) i generyczne uchwyty GC bez boksowania (`GCHandle<T>`) — obie potwierdzone jako nowość .NET 10 przez realne porównanie z SDK 9, a przy okazji złapana nieudokumentowana luka w pinowaniu tablic referencyjnych.
→ [Artykuł](dotnet/ARTICLE.md) · [Kod](dotnet/code/)

### 🔧 [Ansible](ansible/ARTICLE.md)
→ [Artykuł](ansible/ARTICLE.md) · [Kod](ansible/code/)

### 🏗️ [TeamCity](teamcity/ARTICLE.md)
→ [Artykuł](teamcity/ARTICLE.md) · [Kod](teamcity/code/)

### 🧪 [TUnit](tunit/ARTICLE.md)
Prawdziwe minimalne API pod testem przez `WebApplicationFactory<Program>` + TUnit-owy odpowiednik `IClassFixture<T>` (`[ClassDataSource]` + `SharedType.PerClass`) — 5/5 testów, plus zmierzona (nie zgadywana) pułapka współdzielonego stanu i empiryczne obalenie rady o `partial class Program`.
→ [Artykuł](tunit/ARTICLE.md) · [Kod](tunit/code/)

### ✈️ [Aspire](aspire/ARTICLE.md)
Pierwszy prawdziwy kontener w tej rubryce: `AddRedis("cache")` odpala realny Docker, a Aspire po cichu dorzuca losowe hasło i TLS do connection stringa, o które nikt nie prosił — 3 przebiegi, za każdym razem 8/8 PASS.
→ [Artykuł](aspire/ARTICLE.md) · [Kod](aspire/code/)

### 📨 [Messaging .NET z MassTransit](masstransit/ARTICLE.md)
Pierwsze cztery wydania uczyły MassTransit na in-memory — dziś prawdziwy RabbitMQ w Dockerze: realna topologia (exchange→exchange→kolejka) i trwałość, którą pokazują trzy osobne procesy (publish bez konsumenta → wiadomości czekają na brokerze → nowy proces je odbiera).
→ [Artykuł](masstransit/ARTICLE.md) · [Kod](masstransit/code/)

### 🤖 [AI — Claude Code dla .NET/Angular/SQL](ai-claude-code/ARTICLE.md)
→ [Artykuł](ai-claude-code/ARTICLE.md) · [Kod](ai-claude-code/code/)

### ⚙️ [AI — agentic loop](ai-agentic-loop/ARTICLE.md)
→ [Artykuł](ai-agentic-loop/ARTICLE.md) · [Kod](ai-agentic-loop/code/)

### 🧠 [AI — zarządzanie kontekstem](ai-context/ARTICLE.md)
→ [Artykuł](ai-context/ARTICLE.md) · [Kod](ai-context/code/)

### ✍️ [AI — prompty dla developera](ai-prompts/ARTICLE.md)
→ [Artykuł](ai-prompts/ARTICLE.md) · [Kod](ai-prompts/code/)

### 🅰️ [Angular](angular/ARTICLE.md)
Signal Forms (`@angular/forms/signals`, potwierdzone jako `@publicApi 22.0`): formularz bez `FormGroup`, walidacja async przez `resource()` z realnym `AbortSignal` i błąd z serwera trafiający na konkretne pole — 15/15 testów, w tym złapana na żywo pułapka z fake timerami.
→ [Artykuł](angular/ARTICLE.md) · [Kod](angular/code/)

### 🗄️ [SQL Server](sqlserver/ARTICLE.md)
→ [Artykuł](sqlserver/ARTICLE.md) · [Kod](sqlserver/code/)

### 🧬 [PostgreSQL jako baza wektorowa](postgres-vector/ARTICLE.md)
→ [Artykuł](postgres-vector/ARTICLE.md) · [Kod](postgres-vector/code/)

### 🔐 [Certyfikaty i TLS (X.509)](certificates/ARTICLE.md)
→ [Artykuł](certificates/ARTICLE.md) · [Kod](certificates/code/)

---

<div align="center">

[← spis wszystkich wydań](../../README.md)

</div>
