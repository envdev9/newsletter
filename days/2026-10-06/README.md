<div align="center">

# 📰 TECH PRASÓWKA — Wydanie #13
### 6 października 2026

</div>

---

### 🔷 [.NET](dotnet/ARTICLE.md)
`Utf8JsonWriter` wreszcie pisze string i base64 w kawałkach (`WriteStringValueSegment`, `WriteBase64StringSegment`) — ale bez `Flush()` nic nie streamuje — oraz `JsonObject.TryAdd`/`TryGetPropertyValue` zwracające indeks właściwości (upsert bez drugiego wyszukiwania).
→ [Artykuł](dotnet/ARTICLE.md) · [Kod](dotnet/code/)

### 🔧 [Ansible](ansible/ARTICLE.md)
Własny inventory plugin w Pythonie (`-i` bez `ansible.cfg`) oraz `any_errors_fatal` kontra `max_fail_percentage` na flocie z celowymi awariami — próg jest ścisły (`>`): przy 33,3% awarii wartość 33 przerywa play, a 34 jedzie dalej.
→ [Artykuł](ansible/ARTICLE.md) · [Kod](ansible/code/)

### 🏗️ [TeamCity](teamcity/ARTICLE.md)
Cascading merge `feature → integration → main` na żywym serwerze z prawdziwym agentem — a pominięty `commitMessage` po cichu wyłącza merge, zostawiając zielony build.
→ [Artykuł](teamcity/ARTICLE.md) · [Kod](teamcity/code/)

### 🧪 [TUnit](tunit/ARTICLE.md)
JWT RS256 pod testem: walidator zna tylko klucz publiczny, tokeny wygasają na `FakeTimeProvider` bez `Thread.Sleep`, refresh token jest jednorazowy — a mutacja `RequireSignedTokens=false` oblewa dokładnie jeden z ośmiu testów fałszerstw (`alg=none`). Plus trzy projekty z `ProjectReference` i `--treenode-filter`.
→ [Artykuł](tunit/ARTICLE.md) · [Kod](tunit/code/)

### ✈️ [Aspire](aspire/ARTICLE.md)
Ile żyje AppHost pod testami TUnit: `PerTestSession` daje jeden Redis dla dwóch klas, `PerClass` dwa kontenery naraz — a celowo oblany test i tak nie zostawia po sobie kontenera. Cena: ~14 s samego sprzątania na AppHosta.
→ [Artykuł](aspire/ARTICLE.md) · [Kod](aspire/code/)

### 📨 [Messaging .NET z MassTransit](masstransit/ARTICLE.md)
Routing po kluczu na RabbitMQ (topic i direct exchange): domyślna topologia daje konsumentowi 0 wiadomości bez żadnego błędu, a niedopasowany alert znika po cichu — widać go tylko w statystykach exchange'a.
→ [Artykuł](masstransit/ARTICLE.md) · [Kod](masstransit/code/)

### 🤖 [AI — Claude Code dla .NET/Angular/SQL](ai-claude-code/ARTICLE.md)
Skaner planów SQL Server z czterema regułami (spill do tempdb, przerośnięty memory grant, brak predykatu joina, brak statystyk) sprawdzony na prawdziwych planach — a realne plany ujawniły dwa błędy samego skanera, w tym fałszywy alarm przepuszczony przez zielony test.
→ [Artykuł](ai-claude-code/ARTICLE.md) · [Kod](ai-claude-code/code/)

### ⚙️ [AI — agentic loop](ai-agentic-loop/ARTICLE.md)
Dwóch agentów w jednym katalogu to ciche nadpisanie cudzej zmiany bez błędu — `git worktree` daje każdemu własny katalog, `HEAD` i indeks, a konflikt wychodzi jawnie dopiero przy merge.
→ [Artykuł](ai-agentic-loop/ARTICLE.md) · [Kod](ai-agentic-loop/code/)

### 🧠 [AI — zarządzanie kontekstem](ai-context/ARTICLE.md)
Każda kompresja wyniku narzędzia jest stratna — oceniaj ją tokenami i przeżywalnością faktów naraz: w teście `head` dawał 88× oszczędności i gubił wszystkie 4 kluczowe fakty, a filtr na JSON-ie zmniejszał 44 tys. tokenów do 80.
→ [Artykuł](ai-context/ARTICLE.md) · [Kod](ai-context/code/)

### ✍️ [AI — prompty dla developera](ai-prompts/ARTICLE.md)
→ [Artykuł](ai-prompts/ARTICLE.md) · [Kod](ai-prompts/code/)

### 🅰️ [Angular](angular/ARTICLE.md)
`validateHttp` z Signal Forms: asynchroniczna walidacja prosto na `httpResource` — z debounce (4 szybkie zmiany = 1 request zamiast 4), obowiązkową obsługą błędu sieci w typach i pułapką: pierwsza wartość nie jest debounce'owana, jeśli pole nie było wcześniej czytane.
→ [Artykuł](angular/ARTICLE.md) · [Kod](angular/code/)

### 🗄️ [SQL Server](sqlserver/ARTICLE.md)
→ [Artykuł](sqlserver/ARTICLE.md) · [Kod](sqlserver/code/)

### 🧬 [PostgreSQL jako baza wektorowa](postgres-vector/ARTICLE.md)
→ [Artykuł](postgres-vector/ARTICLE.md) · [Kod](postgres-vector/code/)

### 🔐 [Certyfikaty i TLS (X.509)](certificates/ARTICLE.md)
ACME (RFC 8555) od zera: własny serwer i klient .NET z challenge http-01 — podpis ECDSA w DER (71 B) zamiast `r‖s` (64 B) i serwer odpowiada `malformed`, a pierwszy `badNonce` to normalna część protokołu.
→ [Artykuł](certificates/ARTICLE.md) · [Kod](certificates/code/)

---

<div align="center">

[← spis wszystkich wydań](../../README.md)

</div>
