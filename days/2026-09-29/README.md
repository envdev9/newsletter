<div align="center">

# 📰 TECH PRASÓWKA — Wydanie #6
### 29 września 2026

</div>

---

### 🔷 [.NET](dotnet/ARTICLE.md)
→ [Artykuł](dotnet/ARTICLE.md) · [Kod](dotnet/code/)

### 🔧 [Ansible](ansible/ARTICLE.md)
`delegate_facts` (gdzie NAPRAWDĘ ląduje fakt z `set_fact` + `delegate_to`), `run_once` + `serial: 2` (jedno wykonanie na paczkę, nie na cały play) i `throttle: 2` (dwie realne fale zamiast jednej) — plus przypadkiem złapana pułapka z "zamrażaniem" nazwy hosta w logu `TASK [...]`.
→ [Artykuł](ansible/ARTICLE.md) · [Kod](ansible/code/)

### 🏗️ [TeamCity](teamcity/ARTICLE.md)
Piąta próba kompilacji Kotlin DSL nadal bez sukcesu, ale pierwszy raz w pełni zdiagnozowana (allowlist poleceń + zakaz wywołań po ścieżce bezwzględnej, sieć jednak działa) — plus nowy krok pipeline'u: Docker Compose z Postgresem dla testów integracyjnych.
→ [Artykuł](teamcity/ARTICLE.md) · [Kod](teamcity/code/)

### 🧪 [TUnit](tunit/ARTICLE.md)
→ [Artykuł](tunit/ARTICLE.md) · [Kod](tunit/code/)

### ✈️ [Aspire](aspire/ARTICLE.md)
→ [Artykuł](aspire/ARTICLE.md) · [Kod](aspire/code/)

### 📨 [Messaging .NET z MassTransit](masstransit/ARTICLE.md)
→ [Artykuł](masstransit/ARTICLE.md) · [Kod](masstransit/code/)

### 🤖 [AI — Claude Code dla .NET/Angular/SQL](ai-claude-code/ARTICLE.md)
Skill do code-review Angulara skoncentrowany na Signals — deterministyczny skaner wykrywa `effect()` udający `computed()`, mutacje w `.update()` i komponenty bez `OnPush`, zanim model w ogóle zacznie oceniać sens kodu.
→ [Artykuł](ai-claude-code/ARTICLE.md) · [Kod](ai-claude-code/code/)

### ⚙️ [AI — agentic loop](ai-agentic-loop/ARTICLE.md)
Kto wybiera skill? Nie hook, nie harness — model, wyłącznie na podstawie `description`; symulacja pokazuje, jak identyczna procedura z lepiej napisanym opisem łapie parafrazę zadania, a z gorszym opisem daje totalny miss.
→ [Artykuł](ai-agentic-loop/ARTICLE.md) · [Kod](ai-agentic-loop/code/)

### 🧠 [AI — zarządzanie kontekstem](ai-context/ARTICLE.md)
→ [Artykuł](ai-context/ARTICLE.md) · [Kod](ai-context/code/)

### ✍️ [AI — prompty dla developera](ai-prompts/ARTICLE.md)
→ [Artykuł](ai-prompts/ARTICLE.md) · [Kod](ai-prompts/code/)

### 🅰️ [Angular](angular/ARTICLE.md)
→ [Artykuł](angular/ARTICLE.md) · [Kod](angular/code/)

### 🗄️ [SQL Server](sqlserver/ARTICLE.md)
→ [Artykuł](sqlserver/ARTICLE.md) · [Kod](sqlserver/code/)

### 🧬 [PostgreSQL jako baza wektorowa](postgres-vector/ARTICLE.md)
→ [Artykuł](postgres-vector/ARTICLE.md) · [Kod](postgres-vector/code/)

### 🔐 [Certyfikaty i TLS (X.509)](certificates/ARTICLE.md)
Certificate Transparency od zera: własny precertyfikat z rozszerzeniem poison, ręcznie liczony hash liścia drzewa Merkle i podpisany SCT — a potem dowód, że wklejenie cudzego SCT do innego certyfikatu natychmiast się wysypuje.
→ [Artykuł](certificates/ARTICLE.md) · [Kod](certificates/code/)

---

<div align="center">

[← spis wszystkich wydań](../../README.md)

</div>
