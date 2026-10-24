<div align="center">

# 📰 TECH PRASÓWKA — Wydanie #18
### 11 października 2026

</div>

---

### 🔷 [.NET](dotnet/ARTICLE.md)
Cykl w grafie obiektów wywala serializator po 64 poziomach — `JsonKnownReferenceHandler` w .NET 10 pozwala wybrać `Preserve` albo `IgnoreCycles` także w source generatorze, a `FrozenDictionary.Create` buduje zamrożony słownik wprost ze `stackalloc`-owego spana.
→ [Artykuł](dotnet/ARTICLE.md) · [Kod](dotnet/code/)

### 🔧 [Ansible](ansible/ARTICLE.md)
Rola to metoda z sygnaturą — `argument_specs`, deduplikacja wywołań i wyciek zmiennych: zmierzone, że po `roles:` w playu widać default roli, nie przekazany parametr, a `set_stats` z `aggregate` na napisach cicho skleja „2”+„5”+„3” w „253”.
→ [Artykuł](ansible/ARTICLE.md) · [Kod](ansible/code/)

### 🏗️ [TeamCity](teamcity/ARTICLE.md)
→ [Artykuł](teamcity/ARTICLE.md) · [Kod](teamcity/code/)

### 🧪 [TUnit](tunit/ARTICLE.md)
Pominięty test nie może być cichy — dziś dowód z realnego przebiegu: `ShouldSkip` woła się raz, przed ciałem testu, powód skipu ląduje w raporcie, a `[Explicit]` nie wchodzi nawet do `total`.
→ [Artykuł](tunit/ARTICLE.md) · [Kod](tunit/code/)

### ✈️ [Aspire](aspire/ARTICLE.md)
→ [Artykuł](aspire/ARTICLE.md) · [Kod](aspire/code/)

### 📨 [Messaging .NET z MassTransit](masstransit/ARTICLE.md)
→ [Artykuł](masstransit/ARTICLE.md) · [Kod](masstransit/code/)

### 🤖 [AI — Claude Code dla .NET/Angular/SQL](ai-claude-code/ARTICLE.md)
→ [Artykuł](ai-claude-code/ARTICLE.md) · [Kod](ai-claude-code/code/)

### ⚙️ [AI — agentic loop](ai-agentic-loop/ARTICLE.md)
Hash drzewa repo z `git write-tree` zamiast własnego (przy 5000 plików ~8× szybszy z trwałym indeksem), a przy okazji pułapka: crash w kompaktowaniu sprawia, że archiwum i żywy dziennik to ten sam inode — oś zdarzeń pokazuje 79 zdarzeń zamiast 61.
→ [Artykuł](ai-agentic-loop/ARTICLE.md) · [Kod](ai-agentic-loop/code/)

### 🧠 [AI — zarządzanie kontekstem](ai-context/ARTICLE.md)
→ [Artykuł](ai-context/ARTICLE.md) · [Kod](ai-context/code/)

### ✍️ [AI — prompty dla developera](ai-prompts/ARTICLE.md)
Zamiast mega-promptu „napraw i upewnij się, że testy przechodzą" — łańcuch triaż → plan → patch z kontraktem między krokami; na 7 nagraniach 0 fałszywych zielonych vs 2 w wersji bez kontraktów (uczciwie: bez prawdziwego modelu, to test łańcucha, nie LLM-a).
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
