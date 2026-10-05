<div align="center">

# 📰 TECH PRASÓWKA — Wydanie #12
### 5 października 2026

</div>

---

### 🔷 [.NET](dotnet/ARTICLE.md)
Span, który porządkuje bajty własnymi zasadami (`SequenceCompareTo<T>` z `IComparer<T>`), i `JsonArray`, który wreszcie umie `RemoveAll`/`RemoveRange` bez ręcznej pętli "od tyłu" — plus gołe `NullReferenceException`, gdy predykat nie pilnuje JSON-owego `null`.
→ [Artykuł](dotnet/ARTICLE.md) · [Kod](dotnet/code/)

### 🔧 [Ansible](ansible/ARTICLE.md)
Własny callback plugin mierzący czas trwania każdego taska, i fact caching, który obala własny mit: cache NIE pomija żywego `Gathering Facts` dla celowanego hosta, ale pozwala czytać `hostvars` hosta, którego dany play wcale nie dotyka.
→ [Artykuł](ansible/ARTICLE.md) · [Kod](ansible/code/)

### 🏗️ [TeamCity](teamcity/ARTICLE.md)
→ [Artykuł](teamcity/ARTICLE.md) · [Kod](teamcity/code/)

### 🧪 [TUnit](tunit/ARTICLE.md)
`[AfterEvery(Assembly)]`/`[AfterEvery(Class)]` z DWOMA projektami testowymi w jednym `dotnet test`: hook liczy tylko swój projekt, każdy projekt to osobny proces OS, oba biegną WSPÓŁBIEŻNIE — a identycznie nazwana klasa stanu statycznego w obu wcale się nie myli.
→ [Artykuł](tunit/ARTICLE.md) · [Kod](tunit/code/)

### ✈️ [Aspire](aspire/ARTICLE.md)
AppHost pod testem TUnit: jeden realny kontener Redis uruchomiony raz na klasę, cztery testy walące w niego równolegle bez kolizji (dzięki unikalnym kluczom) — plus haczyk, że statyczny `[After(Class)]` i instancyjny fixture Aspire wzajemnie się nie widzą.
→ [Artykuł](aspire/ARTICLE.md) · [Kod](aspire/code/)

### 📨 [Messaging .NET z MassTransit](masstransit/ARTICLE.md)
`_error`/`_skipped` na prawdziwym RabbitMQ: proces, który odłożył wiadomość do kolejki błędów, zostaje zabity — a zupełnie nowy proces widzi ją tam nadal. Plus sprostowanie: `Ignore<T>` wcale nie trafia do `_skipped`, tylko prosto do `_error`.
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
`tapResponse()` z `@ngrx/operators` obalone jako "bezpieczne niezależnie od miejsca w pipe" — źle umieszczony zabija `rxMethod` identycznie jak goły `catchError`; realna wartość to wymuszony `error` w typach i `finalize` na anulowanym żądaniu.
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
