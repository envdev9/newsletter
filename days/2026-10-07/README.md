<div align="center">

# 📰 TECH PRASÓWKA — Wydanie #14
### 7 października 2026

</div>

---

### 🔷 [.NET](dotnet/ARTICLE.md)
Sanityzacja nazwy pliku bez ani jednej alokacji (`MemoryExtensions.ReplaceAny`/`CountAny` z `SearchValues<T>` kontra 288 MB z `string.Replace`) i LINQ na `IAsyncEnumerable<T>` prosto z .NET 10, bez dodatkowego NuGeta.
→ [Artykuł](dotnet/ARTICLE.md) · [Kod](dotnet/code/)

### 🔧 [Ansible](ansible/ARTICLE.md)
`-e app_port=abc` przechodzi w playbooku bez mrugnięcia — dziś dorabiamy walidację: `vars_prompt`, `assert`, `fail` i kod wyjścia 2 zmierzony na żywo.
→ [Artykuł](ansible/ARTICLE.md) · [Kod](ansible/code/)

### 🏗️ [TeamCity](teamcity/ARTICLE.md)
Twój config w Gicie to nie archiwum, tylko pętla w obie strony: serwer kładzie obok `settings.kts` łatki z UI, a gdy ten sam krok zmienisz w kodzie, odrzuca Twój push i zostaje przy starej wersji.
→ [Artykuł](teamcity/ARTICLE.md) · [Kod](teamcity/code/)

### 🧪 [TUnit](tunit/ARTICLE.md)
Dwa prawdziwe serwery, rotacja kluczy JWKS i wyścig refresh tokenu — pierwszy użytkownik z nowym `kid` dostaje 401, wycofany klucz nadal działa, a test wyścigu przez HTTP przepuścił usunięty `lock`.
→ [Artykuł](tunit/ARTICLE.md) · [Kod](tunit/code/)

### ✈️ [Aspire](aspire/ARTICLE.md)
`kill -9` na procesie z AppHostem: Redis w Dockerze znika po ~12 s (sprząta DCP, nie Twój kod) — ale gdy zabijemy też DCP, zostaje sierota, a następny AppHost posprząta tylko kontener i sieć, nie procesy.
→ [Artykuł](aspire/ARTICLE.md) · [Kod](aspire/code/)

### 📨 [Messaging .NET z MassTransit](masstransit/ARTICLE.md)
Wiadomość bez trasy już nie znika po cichu: `mandatory` rzuca `312 NO_ROUTE`, alternate-exchange odkłada ją do kosza — a trzy zmierzone pułapki pokazują, czego te mechanizmy nie robią.
→ [Artykuł](masstransit/ARTICLE.md) · [Kod](masstransit/code/)

### 🤖 [AI — Claude Code dla .NET/Angular/SQL](ai-claude-code/ARTICLE.md)
Skill `ef-core-review` + hook `PostToolUse` łapią 7 antywzorców EF Core już przy zapisie pliku — a plan z prawdziwego SQL Server potwierdza skutek: ten sam `Where` po e-mailu to 222 vs 5 odczytów logicznych zależnie od jednej linii `IsUnicode(false)`.
→ [Artykuł](ai-claude-code/ARTICLE.md) · [Kod](ai-claude-code/code/)

### ⚙️ [AI — agentic loop](ai-agentic-loop/ARTICLE.md)
Pętla agentowa musi mieć warunki wyjścia poza modelem: budżet, wykrywanie zapętlenia, retry z jitterem i dziennik z kluczem idempotencji — dzięki nim crash w połowie kroku nie wysyła maila dwa razy.
→ [Artykuł](ai-agentic-loop/ARTICLE.md) · [Kod](ai-agentic-loop/code/)

### 🧠 [AI — zarządzanie kontekstem](ai-context/ARTICLE.md)
→ [Artykuł](ai-context/ARTICLE.md) · [Kod](ai-context/code/)

### ✍️ [AI — prompty dla developera](ai-prompts/ARTICLE.md)
→ [Artykuł](ai-prompts/ARTICLE.md) · [Kod](ai-prompts/code/)

### 🅰️ [Angular](angular/ARTICLE.md)
SignalStore Events: komponent mówi „co się stało", a store'y same reagują przez reduktory i efekty — plus pięć zmierzonych haczyków (martwy efekt bez `catchError`, brak replay, globalny dispatcher, nieaktualny JSDoc).
→ [Artykuł](angular/ARTICLE.md) · [Kod](angular/code/)

### 🗄️ [SQL Server](sqlserver/ARTICLE.md)
→ [Artykuł](sqlserver/ARTICLE.md) · [Kod](sqlserver/code/)

### 🧬 [PostgreSQL jako baza wektorowa](postgres-vector/ARTICLE.md)
→ [Artykuł](postgres-vector/ARTICLE.md) · [Kod](postgres-vector/code/)

### 🔐 [Certyfikaty i TLS (X.509)](certificates/ARTICLE.md)
CA z kagańcem: Name Constraints od zera — 26 certyfikatów, dwa weryfikatory (.NET i openssl) i siedem haczyków, o których dokumentacja milczy.
→ [Artykuł](certificates/ARTICLE.md) · [Kod](certificates/code/)

---

<div align="center">

[← spis wszystkich wydań](../../README.md)

</div>
