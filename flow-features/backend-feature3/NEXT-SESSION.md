# Master prompt: następna sesja o workflow backend-feature3

Wklej poniższy blok na start nowej sesji Claude Code (najlepiej w `~`, żeby widziała `~/.claude/`).

---

```
Kontynuujemy pracę nad workflow Claude Code dla backendu .NET: „backend-feature3”.

Przeczytaj najpierw (repo https://gitea.loriapps.net/tech02/flow-feautres.git,
push po SSH: ssh://git@192.168.1.91:30022/tech02/flow-feautres.git):
- backend-feature3/README.md: decyzje, koszty, słabe strony, szkic wdrożenia
- backend-feature3/SKILL.md: szkic skilla
- backend-feature3/session-context.md: skąd się to wzięło i otwarte punkty

Obecny stan na dysku (jeszcze NIEZMIENIONY):
- ~/.claude/agents/dotnet-developer.md: 118 linii zasad (Zasady pracy, Standardy C#, Dapper/Postgres,
  SqlDeployer, API, Cloud-ready K8s, Aspire)
- ~/.claude/skills/feature-backend/: SKILL.md + reviewer-prompt.md + security-prompt.md
- ~/.claude/CLAUDE.md: bez importu zasad .NET

Cel tej sesji: wdrożyć backend-feature3 zgodnie z sekcją „Szkic wdrożenia”:
1. Rozbić zasady agenta na ~/.claude/rules/dotnet.md (ogólne + checklista self-review),
   dotnet-data.md (Dapper/Postgres/SqlDeployer) i dotnet-cloud.md (API/K8s/Aspire). Treść przenieść, nie przepisywać.
2. Import @~/.claude/rules/dotnet.md w ~/.claude/CLAUDE.md, albo w CLAUDE.md repo .NET (zapytaj mnie, którą opcję wybrać).
3. dotnet-developer.md: model: sonnet i odwołania do plików zasad zamiast kopii.
4. ~/.claude/skills/backend-feature3/ z SKILL.md z repo + review-prompt.md (połączenie reviewer i security);
   security-prompt.md zostaje dla zmian wrażliwych.
5. feature-backend zostaje bez zmian (porównanie).

Zasady pracy w tej sesji:
- Mam ograniczony limit: pracuj w głównej sesji, bez subagentów, chyba że o nie poproszę.
- Najpierw pokaż plan zmian plików (co skąd przenosisz) i czekaj na moje „tak”.
- Przed nadpisaniem pliku w ~/.claude pokaż diff. Nie ruszaj ~/.ssh.
- Po wdrożeniu zaktualizuj repo flow-feautres (status w session-context.md: odhacz punkty) i zrób commit + push
  dopiero po moim potwierdzeniu.
- Odpowiadaj po polsku, zwięźle.
```
