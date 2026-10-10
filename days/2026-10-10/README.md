<div align="center">

# 📰 TECH PRASÓWKA — Wydanie #17
### 10 października 2026

</div>

---

### 🔷 [.NET](dotnet/ARTICLE.md)
`System.Text.Json` w .NET 10 czyta JSON prosto z `PipeReader`, bez adaptera `AsStream()` i z 3× mniejszym szczytem pamięci przy strumieniowaniu, ale uwaga: `DeserializeAsync` wraca dopiero, gdy writer zamknie potok. Przy okazji `ActivitySource` dostaje wreszcie opcje, tagi i adres schematu telemetrii.
→ [Artykuł](dotnet/ARTICLE.md) · [Kod](dotnet/code/)

### 🔧 [Ansible](ansible/ARTICLE.md)
Edytuj, nie nadpisuj — `lineinfile`, `blockinfile`, `template` z `validate` i `assemble`: jak zmienić jedną linię cudzego pliku, nie zepsuć go i nie zostawić po sobie śmieci, które `changed=0` przemilczy.
→ [Artykuł](ansible/ARTICLE.md) · [Kod](ansible/code/)

### 🏗️ [TeamCity](teamcity/ARTICLE.md)
→ [Artykuł](teamcity/ARTICLE.md) · [Kod](teamcity/code/)

### 🧪 [TUnit](tunit/ARTICLE.md)
Zakomentowany test to test zapomniany — TUnit pozwala pominąć go z powodem, warunkiem środowiskowym albo oznaczyć `[Explicit]`, ale w tym wydaniu uczciwie: kod się kompiluje, a przebieg testów nie został zweryfikowany (środowisko odrzuciło `dotnet test`).
→ [Artykuł](tunit/ARTICLE.md) · [Kod](tunit/code/)

### ✈️ [Aspire](aspire/ARTICLE.md)
→ [Artykuł](aspire/ARTICLE.md) · [Kod](aspire/code/)

### 📨 [Messaging .NET z MassTransit](masstransit/ARTICLE.md)
→ [Artykuł](masstransit/ARTICLE.md) · [Kod](masstransit/code/)

### 🤖 [AI — Claude Code dla .NET/Angular/SQL](ai-claude-code/ARTICLE.md)
→ [Artykuł](ai-claude-code/ARTICLE.md) · [Kod](ai-claude-code/code/)

### ⚙️ [AI — agentic loop](ai-agentic-loop/ARTICLE.md)
Agent, który po raz piąty puszcza testy na tym samym kodzie, ma tekst błędu za każdym razem inny, więc stary detektor milczy — hash drzewa repo zatrzymuje go po 3 porażkach, a snapshoty zmniejszają dziennik prawie 6 razy bez zmiany wyniku.
→ [Artykuł](ai-agentic-loop/ARTICLE.md) · [Kod](ai-agentic-loop/code/)

### 🧠 [AI — zarządzanie kontekstem](ai-context/ARTICLE.md)
→ [Artykuł](ai-context/ARTICLE.md) · [Kod](ai-context/code/)

### ✍️ [AI — prompty dla developera](ai-prompts/ARTICLE.md)
Dokumentacja z modelu zmyśla parametry i starzeje się po cichu — dziś fakty o kodzie wchodzą do promptu ze skryptu, a ten sam skrypt waliduje wynik; zmierzone na 11 rozjazdach: walidator 9/11, kompilator 2/11.
→ [Artykuł](ai-prompts/ARTICLE.md) · [Kod](ai-prompts/code/)

### 🅰️ [Angular](angular/ARTICLE.md)
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
