<div align="center">

# 🤖 AI — Claude Code dla .NET/Angular/SQL

### TECH PRASÓWKA — wszystkie artykuły rubryki, najnowsze na górze

</div>

---

Każdy artykuł to osobny folder `<data>-<tytuł>/` z `ARTICLE.md` i pełnym, uruchamialnym
kodem w `code/`. Kolejne artykuły podnoszą poziom — postęp rubryki jest w
[`STATE.md`](../../STATE.md).

| Data | Artykuł | W skrócie | Kod |
|------|---------|-----------|-----|
| 2026-10-16 | [Rachunek za GIN: ile kosztuje indeks, który ratuje `Contains` — i co z `ILIKE` oraz `citext`](2026-10-16-rachunek-za-gin-ile-kosztuje-indeks-ktory-ratuje-contains-i/ARTICLE.md) | Ile naprawdę kosztuje indeks GIN `gin_trgm_ops`, który ratuje `Contains`: 8,7 s vs 0,5 s przy insercie 200 tys. wierszy oraz pułapki `ILIKE`, `lower()` i `citext`, zmierzone na PostgreSQL 16. | [Kod](2026-10-16-rachunek-za-gin-ile-kosztuje-indeks-ktory-ratuje-contains-i/code/) |
| 2026-10-09 | [`ef-core-review` v3: ten sam skill, drugi silnik — PostgreSQL, plany z `EXPLAIN` i bramka w CI](2026-10-09-ef-core-review-v3-ten-sam-skill-drugi-silnik-postgresql/ARTICLE.md) | Ten sam `Email.Contains(term)` z EF Core to na PostgreSQL 1696 buforów i Seq Scan, a z jednym indeksem GIN 17 — skaner planów `EXPLAIN` w `ef-core-review` v3 potrafi zatrzymać takie zapytanie w CI, zanim trafi na produkcję. | [Kod](2026-10-09-ef-core-review-v3-ten-sam-skill-drugi-silnik-postgresql/code/) |
| 2026-10-08 | [`ef-core-review` v2: LIKE '%x%', `Contains` na listach — i plan zapytania prosto z aplikacji](2026-10-08-ef-core-review-v2-like-x-contains-na-listach-i-plan/ARTICLE.md) | `Contains` i `LIKE '%x%'` w EF Core czytają 371 stron zamiast 5 — skaner `ef-core-review` v2 łapie je po typie encji, a interceptor zapisuje prawdziwy plan zapytania; lista 5000 id: 29 ms vs 955 ms zależnie od trybu parametryzacji. | [Kod](2026-10-08-ef-core-review-v2-like-x-contains-na-listach-i-plan/code/) |
| 2026-10-07 | [Skill + hook `ef-core-review`: skaner EF Core, który łączy się z planem wykonania](2026-10-07-skill-hook-ef-core-review-skaner-ef-core-ktory-laczy-sie-z/ARTICLE.md) | Skill `ef-core-review` + hook `PostToolUse` łapią 7 antywzorców EF Core już przy zapisie pliku — a plan z prawdziwego SQL Server potwierdza skutek: ten sam `Where` po e-mailu to 222 vs 5 odczytów logicznych zależnie od jednej linii `IsUnicode(false)`. | [Kod](2026-10-07-skill-hook-ef-core-review-skaner-ef-core-ktory-laczy-sie-z/code/) |
| 2026-10-06 | [Cztery reguły skanera, które czekały na prawdziwy plan — i dwa błędy, które się przy okazji ujawniły](2026-10-06-cztery-reguly-skanera-ktore-czekaly-na-prawdziwy-plan-i-dwa/ARTICLE.md) | Skaner planów SQL Server z czterema regułami (spill do tempdb, przerośnięty memory grant, brak predykatu joina, brak statystyk) sprawdzony na prawdziwych planach — a realne plany ujawniły dwa błędy samego skanera, w tym fałszywy alarm przepuszczony przez zielony test. | [Kod](2026-10-06-cztery-reguly-skanera-ktore-czekaly-na-prawdziwy-plan-i-dwa/code/) |
| 2026-10-03 | [Skill `sql-plan-review` zdaje egzamin na prawdziwym SQL Serverze](2026-10-03-skill-sql-plan-review-zdaje-egzamin-na-prawdziwym-sql/ARTICLE.md) | Skill `sql-plan-review` z wydania #4 zderzony z PRAWDZIWYM planem SQL Servera — zero zmian w kodzie, ale nowa pułapka: `string`-parametr jako `NVARCHAR` ignoruje indeks (57× więcej odczytów). | [Kod](2026-10-03-skill-sql-plan-review-zdaje-egzamin-na-prawdziwym-sql/code/) |
| 2026-09-29 | [Skill do Angulara: `effect()` nie jest gorszym `computed()`](2026-09-29-skill-do-angulara-effect-nie-jest-gorszym-computed/ARTICLE.md) | Skill do code-review Angulara skoncentrowany na Signals — deterministyczny skaner wykrywa `effect()` udający `computed()`, mutacje w `.update()` i komponenty bez `OnPush`, zanim model w ogóle zacznie oceniać sens kodu. | [Kod](2026-09-29-skill-do-angulara-effect-nie-jest-gorszym-computed/code/) |
| 2026-09-27 | [Skill do SQL: Claude czyta plan wykonania, zanim zrobi to DBA](2026-09-27-skill-do-sql-claude-czyta-plan-wykonania-zanim-zrobi-to-dba/ARTICLE.md) | Skill `sql-plan-review`: Claude czyta plan wykonania i pliki `.sql`, wyłapuje brakujące indeksy, Key Lookupy i niejawne konwersje — skanery przetestowane 4/4 na fixturach (bez prawdziwego SQL Servera). | [Kod](2026-09-27-skill-do-sql-claude-czyta-plan-wykonania-zanim-zrobi-to-dba/code/) |
| 2026-09-26 | [Agent edytuje C#, a hook sam formatuje i buduje — oraz `.claude/` dla całego zespołu](2026-09-26-agent-edytuje-c-a-hook-sam-formatuje-i-buduje-oraz-claude/ARTICLE.md) | Agent zmienia plik `.cs`, a hook `PostToolUse` w tej samej chwili go formatuje i buduje — błąd kompilacji wraca do modelu od razu, a zespołowy `settings.json` daje wszystkim te same bariery (hook zweryfikowany na SDK 10, żywa sesja Claude Code nie). | [Kod](2026-09-26-agent-edytuje-c-a-hook-sam-formatuje-i-buduje-oraz-claude/code/) |
| 2026-09-25 | [Strażnik commitów i recenzent migracji EF Core — dwa kolejne pliki do `.claude/`](2026-09-25-straznik-commitow-i-recenzent-migracji-ef-core-dwa-kolejne/ARTICLE.md) | Hook, który czyta komendę powłoki i nie wpuści `git commit` bez Conventional Commits, oraz skill do review migracji EF Core, w którym skaner podaje fakty, a model dopiero potem ocenia. | [Kod](2026-09-25-straznik-commitow-i-recenzent-migracji-ef-core-dwa-kolejne/code/) |
| 2026-09-24 | [Trzy konfiguracje Claude Code, które realnie skracają dzień pracy w .NET/Angular/SQL](2026-09-24-trzy-konfiguracje-claude-code-ktore-realnie-skracaja-dzien/ARTICLE.md) | Gotowe do skopiowania: slash command generujący testy, hook pilnujący rollbacku w | [Kod](2026-09-24-trzy-konfiguracje-claude-code-ktore-realnie-skracaja-dzien/code/) |
<!-- kolejne wiersze dopisywane automatycznie, najnowsze na górze -->

---

<div align="center">

[← spis rubryk](../../README.md)

</div>
