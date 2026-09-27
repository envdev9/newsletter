<div align="center">

# 📰 TECH PRASÓWKA — Wydanie #4
### 27 września 2026

</div>

---

### 🔷 [.NET](dotnet/ARTICLE.md)
Napisz `(text, out result) => int.TryParse(text, out result)` bez ani jednego typu, a `"kajak".IsPalindrome()` zadziała bez `.AsSpan()` — C# 14 kasuje dwie drobne, ale codzienne ceremonie (zweryfikowane na SDK 10).
→ [Artykuł](dotnet/ARTICLE.md) · [Kod](dotnet/code/)

### 🔧 [Ansible](ansible/ARTICLE.md)
Własne filtry i lookupy w Pythonie, `include_tasks` kontra `import_tasks` (czemu `--tags` nie działa tak, jak myślisz) oraz `serial` z canary i `strategy: free` — prawdziwy output, a `ansible-vault` uczciwie oznaczony jako niezweryfikowany.
→ [Artykuł](ansible/ARTICLE.md) · [Kod](ansible/code/)

### 🏗️ [TeamCity](teamcity/ARTICLE.md)
Zielony build to nie zawsze dobry build: TeamCity uczy się czepiać spadku liczby testów, uruchamia kroki w kontenerze i pokazuje cały łańcuch jednym znaczkiem na commicie (kompilacja Kotlin DSL niezweryfikowana — brak narzędzi w środowisku).
→ [Artykuł](teamcity/ARTICLE.md) · [Kod](teamcity/code/)

### 🧪 [TUnit](tunit/ARTICLE.md)
Własne asercje na `Assert.That`, hook `[AfterEvery]` i retry, który ponawia tylko błędy przejściowe, a prawdziwe błędy logiki zostawia czerwone — 6/6 zielone na TUnit 1.69.
→ [Artykuł](tunit/ARTICLE.md) · [Kod](tunit/code/)

### ✈️ [Aspire](aspire/ARTICLE.md)
Skąd proces dostaje sekrety w Aspire i dlaczego `AddParameter("x", "wartość")` po cichu ignoruje konfigurację? Parametry, `WithEnvironment` i `AddExecutable` — zweryfikowane testem AppHosta (bez kontenerów).
→ [Artykuł](aspire/ARTICLE.md) · [Kod](aspire/code/)

### 📨 [Messaging .NET z MassTransit](masstransit/ARTICLE.md)
Nazwy kolejek, pytanie-odpowiedź z timeoutem i filtry w MassTransit: kto, dokąd i przez co — plus pułapka, że `Publish` omija filtr `Send` (zmierzone na in-memory, RabbitMQ niezweryfikowany).
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
Router sam wkłada parametry z URL-a i dane z resolvera do `input()`-ów komponentu, a `@defer` odracza ładowanie kodu komentarzy do momentu, gdy adres zawiera `?tab=comments` — build, 6/6 testów; bez `ng serve`.
→ [Artykuł](angular/ARTICLE.md) · [Kod](angular/code/)

### 🗄️ [SQL Server](sqlserver/ARTICLE.md)
→ [Artykuł](sqlserver/ARTICLE.md) · [Kod](sqlserver/code/)

### 🧬 [PostgreSQL jako baza wektorowa](postgres-vector/ARTICLE.md)
→ [Artykuł](postgres-vector/ARTICLE.md) · [Kod](postgres-vector/code/)

### 🔐 [Certyfikaty i TLS (X.509)](certificates/ARTICLE.md)
Odwołany certyfikat nadal działa? Mierzymy CRL/OCSP w .NET, stapling i handshake TLS 1.3 na bajtach, rotację certu w Kestrelu bez restartu i pinning SPKI — z prawdziwym outputem.
→ [Artykuł](certificates/ARTICLE.md) · [Kod](certificates/code/)

---

<div align="center">

[← spis wszystkich wydań](../../README.md)

</div>
