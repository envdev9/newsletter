<div align="center">

# 📰 TECH PRASÓWKA — bonus do wydania #13
### ⚙️ AI — agentic loop

![Bonus](https://img.shields.io/badge/bonus-prawdziwy_artefakt-5A67D8?style=for-the-badge)
![Zero fikcji](https://img.shields.io/badge/zero_fikcji-rzeczywista_sesja-brightgreen?style=for-the-badge)

## Prawdziwa specyfikacja: szkielet pętli agentowej

</div>

---

Artykuł dnia (wyżej) symulował współbieżnych agentów skryptem Pythona, bo żywa sesja
`claude` była dziś niedostępna do weryfikacji. Ten plik to coś innego: **realny wynik
rzeczywistej sesji brainstormingowej** (skill `superpowers:brainstorming`) nad dokładnie
tym samym tematem — jak zbudować uniwersalny, inżynieryjny szkielet agentowej pętli
wytwórczej dla Claude Code. Zero symulacji: to jest prawdziwa specyfikacja projektowa
(`spec.md`-podobny dokument), po samoprzeglądzie, zatwierdzona do commita.

Dokument został **zanonimizowany pod kątem danych o konkretnym użytkowniku** przed
publikacją w tym publicznym repozytorium — w oryginale takich danych zresztą nie było
(brak nazw hostów, adresów IP, kluczy, e-maili), więc treść poniżej jest identyczna z
oryginałem.

> 💡 **Dlaczego to ważne:** artykuł wyżej uczy mechaniki (`git worktree`, izolacja
> dysku). Ten dokument pokazuje **warstwę wyżej**: jak w ogóle zaprojektować proces
> wokół takich mechanizmów — bramki, role agentów, budżety, powrót do specyfikacji przy
> luce (`SPEC-GAP`) — żeby to było inżynierskie, a nie „vibe coding".

---

# Agentic Flow — projekt szkieletu agentowej pętli wytwórczej

Data: 2026-10-06 · Status: do zatwierdzenia

## 1. Cel i zakres

Uniwersalny, niezależny od projektu szkielet, który prowadzi kolejne featury przez cały cykl życia oprogramowania (spec → projekt → plan → implementacja → weryfikacja → review i bezpieczeństwo → przygotowanie wydania → retrospektywa) w sposób inżynieryjny, powtarzalny i audytowalny, z maksymalną autonomią agentów między bramkami człowieka.

**Wynik:** repozytorium-szablon kopiowane do projektu (nowego lub istniejącego), działające natywnie w Claude Code. Nie jest to aplikacja ani własny orkiestrator.

**Kryterium sukcesu:** po skopiowaniu szablonu i wypełnieniu `profile.md` użytkownik opisuje featurę, a pętla prowadzi ją od specyfikacji do gałęzi gotowej do merge'a, zatrzymując się wyłącznie na zdefiniowanych bramkach lub przy `BLOCKED`.

**Poza zakresem (v1):** własny orkiestrator na Agent SDK, dystrybucja jako plugin, automatyczny deploy na produkcję, zapis wiedzy bez zatwierdzenia człowieka, obsługa wielu równoległych featur w jednym repo (kolejność sekwencyjna).

## 2. Decyzje podstawowe

| Obszar | Decyzja |
|---|---|
| Runtime | Claude Code natywnie: subagenci, skille, hooki, `CLAUDE.md` |
| Architektura | Maszyna stanów na artefaktach plikowych; wyspecjalizowani subagenci; twarde bramki w hookach i skryptach |
| Bramki człowieka | Bramka 0 (bootstrap projektu, jednorazowa), Bramka 1 (spec), Bramka 2 (końcowy przegląd przed merge'em) |
| Deploy | Osobna, ręczna akcja człowieka po merge'u; agenci nie wdrażają |
| Uczenie | Agent proponuje wpisy do wiedzy, człowiek zatwierdza przy Bramce 2 |
| Dystrybucja | Szablon do skopiowania, z jasnym podziałem własności plików (sekcja 3) |

## 3. Struktura katalogów i własność plików

```
CLAUDE.md                      # ≤100 linii: zasady nadrzędne + mapa
.claude/
  settings.json                # uprawnienia + podpięcie hooków
  agents/                      # definicje subagentów
  skills/                      # /feature (orkiestrator), /init-flow, skille faz
  hooks/                       # skrypty hooków
docs/
  project/  profile.md · architecture.md · domain.md
  adr/      NNNN-tytuł.md
  features/NNN-slug/  spec.md · design.md · plan.md · status.md · review.md · evidence/
  knowledge/ antipatterns.md · practices.md · proposals/   (+ indeks, pliki tematyczne)
  process/  lifecycle.md · gates.md · budgets.md · definition-of-done.md
  ops/      runbook.md · CHANGELOG.md
scripts/gates/                 # skrypty bramek, czytają profile.md
.flow-version                  # wersja szablonu
```

**Własność:**
- *Szablon (nadpisywalne w całości przy aktualizacji):* `.claude/`, `scripts/gates/`, `docs/process/`.
- *Projekt (szablon nie rusza):* część projektowa `CLAUDE.md`, `docs/project/`, `docs/adr/`, `docs/features/`, `docs/knowledge/`, `docs/ops/`.
- Jedynym plikiem zależnym od stacku jest `docs/project/profile.md`.

**Skąd agent wie, gdzie zajrzeć:** (1) `CLAUDE.md` zawiera mapę i ładuje się automatycznie; (2) definicja agenta wymienia jego wejścia i wyjścia wprost; (3) orkiestrator przekazuje konkretne ścieżki featury; (4) hooki wymuszają to, czego nie da się zostawić w prompcie. Rejestr ścieżek jest w jednym miejscu — `docs/process/lifecycle.md` — pozostałe pliki się do niego odwołują, nie powielają list. Struktura `docs/` to konwencja własna; nazwy `CLAUDE.md`, `.claude/*` są narzucone przez Claude Code.

**Zasady:**
- Stan vs przyrost: `architecture.md` i `runbook.md` opisują stan obecny; `features/` i `adr/` to historia. Po featurze aktualizowane są oba stany.
- Prawda w repo, nie w rozmowie; agenci nie polegają na pamięci poprzednich sesji.
- Wiedza dwustopniowa: `proposals/` (niezatwierdzone) vs `antipatterns.md`/`practices.md` (zatwierdzone). Agenci czytają tylko zatwierdzone.
- Decyzje zapisywane od razu: każda decyzja z uzasadnieniem i odrzuconymi alternatywami trafia do `design.md` (decyzja lokalna dla featury) lub ADR-a (decyzja trwała) w momencie jej podjęcia, nie na koniec fazy. Transkrypt rozmowy nie jest źródłem prawdy dla kolejnych sesji — służy wyłącznie jako archiwum do audytu i diagnozy; nowe sesje odtwarzają kontekst z artefaktów (`spec.md`, `design.md`, `adr/`, `status.md`, `knowledge/`).

## 4. Agenci

Orkiestrator `/feature` to skill w głównej sesji (nie subagent): czyta `status.md`, uruchamia właściwego agenta z konkretną ścieżką, zapisuje wynik bramki. Pracę wykonują subagenci.

| Agent | Faza | Czyta | Produkuje | Zakazy |
|---|---|---|---|---|
| spec-analyst | Spec | opis featury, `domain.md`, `architecture.md`, `knowledge/` | `spec.md`: wymagania, AC z ID, poza zakresem, otwarte pytania | kod; zgadywanie (niejasność → otwarte pytania) |
| architect | Projekt | `spec.md`, kod (RO), `adr/`, `architecture.md` | `design.md`: warianty, wybór, wpływ; propozycje ADR | zmiany kodu; naruszanie ADR bez nowego ADR |
| planner | Plan | `spec.md`, `design.md`, `profile.md` | `plan.md`: małe zadania, mapowanie na AC, paczka kontekstu, test do napisania najpierw | zakres spoza specyfikacji |
| implementer | Implementacja | zadanie z `plan.md` + jego paczka kontekstu | kod + testy (TDD), jedno zadanie na uruchomienie | edycja spec/design/plan; „ciche" naprawianie luk (zgłasza SPEC-GAP) |
| qa-verifier | Weryfikacja | `spec.md`, testy, uruchomiona aplikacja | `evidence/`, macierz AC → test → wynik, brakujące przypadki brzegowe | edycja kodu produkcyjnego |
| code-reviewer | Review | diff, spec, design, wiedza zatwierdzona | sekcja w `review.md`, werdykt | edycja kodu; wgląd w rozumowanie implementera |
| security-reviewer | Bezpieczeństwo | diff, zależności, `architecture.md` | sekcja w `review.md`, werdykt | edycja kodu |
| release-engineer | Wydanie | `status.md`, `runbook.md`, diff | wpis w `CHANGELOG.md`, wersja, plan wdrożenia i rollbacku, aktualizacja `runbook.md` | wdrażanie |
| retrospective | Zamknięcie | katalog featury, `status.md` | `knowledge/proposals/`, propozycje zmian `architecture.md` | zapis do zatwierdzonej wiedzy |

**Zasady wspólne:** jedna odpowiedzialność, jawne wejścia/wyjścia w definicji; najmniejsze uprawnienia (zakres zapisu w `tools` agenta i dodatkowo w hooku); niezależna weryfikacja (implementer, qa-verifier, code-reviewer = osobne konteksty, weryfikator dostaje artefakty i diff, nie rozumowanie); raport zwrotny krótki i ustrukturyzowany (werdykt PASS/FAIL/BLOCKED + ścieżki + problemy), szczegóły w plikach.

## 5. Przebieg featury

```
SPEC → [BRAMKA 1] → DESIGN → PLAN → IMPLEMENT⟲ → VERIFY → REVIEW → RELEASE_PREP → RETRO → [BRAMKA 2] → merge → (deploy ręcznie)
```

- Retro działa przed Bramką 2, żeby człowiek zatwierdził za jednym razem kod, przygotowanie wydania i propozycje wiedzy.
- IMPLEMENT: pętla po zadaniach; jedno zadanie = jeden świeży implementer = jeden commit = jedna bramka zadania.
- Praca na gałęzi `feat/NNN-slug` (najlepiej worktree); merge na główną robi człowiek.
- `status.md`: nagłówek YAML (faza, liczniki iteracji, wyniki bramek, hash zatwierdzonej specyfikacji, `spec_gaps`, `resume_from`) + log przejść. Jest jedynym źródłem prawdy orkiestratora; sesję można przerwać i wznowić.

### Bramki automatyczne (`scripts/gates/`, komendy z `profile.md`)

| Po fazie | Sprawdza |
|---|---|
| SPEC | każde AC ma ID i jest testowalne, brak otwartych pytań, jest sekcja „poza zakresem", limit długości |
| DESIGN | brak konfliktu z ADR, wpływ na `architecture.md` opisany |
| PLAN | każde AC pokryte zadaniem, każde zadanie ma test do napisania najpierw i paczkę kontekstu, limity rozmiaru zadania |
| zadanie IMPLEMENT | build, testy, lint, typy, format zielone; diff w limicie (inaczej `TASK-TOO-BIG`) |
| VERIFY | macierz AC → test → wynik kompletna i zaliczona, próg pokrycia |
| REVIEW | brak niezamkniętych uwag blokujących |
| REVIEW (bezpieczeństwo) | skan sekretów, audyt zależności bez podatności wysokich/krytycznych |
| RELEASE_PREP | wpis w changelogu, plan rollbacku, zaktualizowany runbook |

Bramka to skrypt zwracający kod wyjścia i zapisujący wynik w `status.md`; agent nie ocenia sam, czy „przeszło".

### Hooki

- blokada zakończenia fazy bez sukcesu bramki;
- zamrożenie `spec.md` po Bramce 1 (porównanie hasha ze `status.md`);
- ograniczenie zapisu per agent (allowlista ścieżek);
- zakazane akcje w uprawnieniach: push na główną gałąź, force push, komendy deploya, usuwanie poza katalogiem projektu;
- egzekwowanie budżetów (sekcja 7).

## 6. Powrót do specyfikacji (SPEC-GAP)

1. **Zgłoszenie.** Implementer, qa-verifier, reviewer, architect lub planner kończy pracę werdyktem `BLOCKED` i raportem `SPEC-GAP`: ID AC/sekcja, rodzaj (niejednoznaczność/sprzeczność/brak), dowód (plik, linia, scenariusz), opcjonalnie 1–2 interpretacje. Agent nie poprawia specyfikacji. Trwające zadanie jest wstrzymane (commit WIP lub stash, numer zadania w `status.md`).
2. **Stan.** `phase: SPEC_AMENDMENT`, `resume_from`, `blocked_task`, wpis w `spec_gaps`.
3. **Poprawka.** spec-analyst dostaje tylko `spec.md` i raport luki (bez wglądu w implementację). Hook odblokowuje `spec.md` wyłącznie dla niego i wyłącznie w tym stanie. Powstaje rewizja: sekcja „Rewizje" (numer, powód, lista zmienionych AC).
4. **Klasyfikacja deterministyczna** (skrypt bramki porównuje rewizje): *redakcyjna* — zmiana poza sekcjami AC i „zakres"; *merytoryczna* — dodane/usunięte/zmienione AC lub zakres.
5. **Redakcyjna:** nowy hash, ponowne zamrożenie, powrót do `resume_from`, bez udziału człowieka.
6. **Merytoryczna:** (a) Bramka 1 ponownie, pokazując człowiekowi diff AC i powód; (b) po zatwierdzeniu analiza wpływu — odświeżane tylko dotknięte sekcje `design.md`, zadania mapowane na zmienione AC dostają `REWORK`, nowe AC dostają nowe zadania, zakończone zadania o niezmienionych AC zostają; (c) wyniki VERIFY/REVIEW/bezpieczeństwa unieważnione; (d) powrót do IMPLEMENT od pierwszego zadania `REWORK`.
7. **Odrzucenie przez człowieka:** zostaje stara specyfikacja (człowiek podaje obejście), zmiana po jego myśli, albo anulowanie featury; decyzja w `status.md`.
8. **Zabezpieczenia:** po 2 zmianach merytorycznych w featurze pętla zatrzymuje się z zaleceniem rozbicia/przepisania specyfikacji; każdy `SPEC-GAP` trafia do retrospective jako dane wejściowe (jakie pytanie należało zadać wcześniej).

## 7. Kontekst i timebox

**Kontrola kontekstu:**
- Izolacja: każdy subagent ma własne okno; zadanie = nowy agent bez pamięci. Orkiestrator czyta tylko `status.md` i krótkie raporty.
- Paczka kontekstu na zadanie: planner wpisuje w `plan.md` listę wejść (AC, fragment `design.md`, pliki kodu, istotne wpisy wiedzy); implementer czyta tylko to.
- Limit zadania (wartości startowe do kalibracji): ≤5 plików, ≤~300 linii diffu, 1–3 AC. Skrypt mierzy faktyczny diff; przekroczenie = `TASK-TOO-BIG` → planner dzieli zadanie.
- Progresywne ujawnianie: `CLAUDE.md` ≤100 linii; wiedza w krótkich plikach tematycznych z indeksem; limity długości dokumentów sprawdzane w bramkach.
- Reset między fazami możliwy dzięki `status.md` (świeża sesja lub kompaktowanie bez utraty ciągłości).

**Timebox** (`docs/process/budgets.md`, egzekwowany hookiem; wartości startowe do kalibracji po pierwszych featurach):

| Budżet | Miernik | Po przekroczeniu |
|---|---|---|
| iteracje bramki | 3 próby tej samej bramki | `BLOCKED`, eskalacja do człowieka |
| zadanie | limit tur/wywołań narzędzi + czas zegarowy | agent kończy checkpointem |
| faza | czas zegarowy | orkiestrator zatrzymuje i raportuje |
| featura | łączny czas lub koszt | wstrzymanie i decyzja człowieka |
| ta sama awaria | ten sam błąd 2× z rzędu | wczesne zatrzymanie |

Checkpoint: commit WIP + notka (co zrobione, co zostało, dlaczego stanęło); orkiestrator wybiera: podział zadania, nowy agent z notką albo eskalacja. Egzekwowanie: hook zapisuje w `status.md` czas startu i licznik wywołań narzędzi, po przekroczeniu blokuje kolejne narzędzia i każe domknąć pracę checkpointem; w trybie headless dodatkowo limit tur i `timeout` procesu.

### Format checkpointu

Checkpoint to bezpieczne zatrzymanie pracy bez utraty stanu. Powstaje przy przekroczeniu budżetu, `TASK-TOO-BIG`, `SPEC-GAP` i każdym innym `BLOCKED`. Składa się z dwóch części:

1. **Commit WIP** na gałęzi featury, z komunikatem `WIP(<id zadania>): <powód>`. Commit WIP nie liczy się jako ukończone zadanie i nie przechodzi bramki zadania.
2. **Plik** `docs/features/NNN-slug/checkpoints/<id zadania>-<n>.md` (n = kolejny numer checkpointu tego zadania). `status.md` zawiera tylko wskaźnik na ostatni checkpoint.

Struktura pliku:

```
---
task: T03
reason: BUDGET_TURNS | BUDGET_TIME | SAME_FAILURE | TASK_TOO_BIG | SPEC_GAP | BLOCKED_OTHER
commit: <sha commita WIP>
created_at: <ISO 8601>
---
## Zrobione
## Zostało
## Dlaczego stanęło
## Wskazówki dla następnego agenta   (pliki ruszone, padający test, niezweryfikowane założenia)
```

Zasady:
- Skrypt `checkpoint-lint` sprawdza obecność wszystkich pól i sekcji oraz zgodność `commit` z historią; checkpoint niepełny nie zamyka zatrzymania.
- Orkiestrator na podstawie `reason` wybiera: podział zadania (`TASK_TOO_BIG`), świeżego agenta z checkpointem jako dodatkowym wejściem (`BUDGET_*`, `SAME_FAILURE`), powrót do specyfikacji (`SPEC_GAP`) albo eskalację (`BLOCKED_OTHER`).
- Po 2 checkpointach tego samego zadania orkiestrator eskaluje do człowieka zamiast uruchamiać trzeciego agenta.
- Po zaliczeniu bramki zadania commity WIP tego zadania są łączone (squash) w jeden commit zadania, a przed Bramką 2 skrypt sprawdza, że w gałęzi nie zostały commity WIP.
- Pliki checkpointów zostają w katalogu featury jako ślad audytowy i dane wejściowe retrospective.

**Do zweryfikowania w spike (plan implementacji, krok pierwszy):** które natywne limity Claude Code (limit tur w definicji subagenta, limit kosztu w trybie headless) działają w używanej wersji. Jeśli brak — zostaje mechanizm oparty o hooki i skrypty; projekt się nie zmienia, tylko sposób egzekwowania.

## 8. Uruchomienie w projekcie

Skill `/init-flow`:
- **Greenfield:** wywiad (cel, stack, środowiska, sposób wdrażania) → wypełnienie `profile.md`, szkielet `architecture.md` i `domain.md`, pierwszy ADR (stack) → bramka bootstrapu uruchamia każdą komendę z `profile.md` na pustym szkielecie.
- **Brownfield:** badanie repo w trybie odczytu (stack, komendy z plików pakietów i CI) → odtworzenie `architecture.md` i szkicu `domain.md` oznaczonych „wywnioskowane, do weryfikacji" → zapis stanu bazowego (pokrycie, ostrzeżenia lintera, padające testy); bramki działają jako zapadka (wynik nie gorszy niż bazowy).
- **Bramka 0 (człowiek, jednorazowa):** zatwierdzenie `profile.md` i `architecture.md`.

**`CLAUDE.md` (≤100 linii):** nie pisz kodu bez zatwierdzonej specyfikacji (featury przez `/feature`); źródło prawdy w repo; zakazane akcje; format raportu agenta; odsyłacz do `lifecycle.md` jako rejestru ścieżek.

**`profile.md`:** blok YAML (parsowany przez skrypty) + krótki opis. Pola: stack, struktura kodu, konwencje, komendy (`build`, `test`, `test-one`, `lint`, `typecheck`, `format`, `secrets-scan`, `dep-audit`, `run`), progi (pokrycie, limity rozmiaru zadania), stan bazowy, sposób wdrożenia i środowiska, wersja szablonu. Pole nieistniejące w projekcie jest jawnie `n/a` (bramka pomija je widocznie).

## 9. Wiedza i uczenie

Po featurze retrospective analizuje katalog featury i `status.md` (iteracje, awarie bramek, `SPEC-GAP`) i zapisuje propozycje w `knowledge/proposals/` (antywzorce, praktyki, kandydaci na ADR, propozycje zmian `architecture.md`). Człowiek zatwierdza je przy Bramce 2; zatwierdzone trafiają do `antipatterns.md`/`practices.md` (lub nowego ADR). Agenci roboczy czytają wyłącznie zatwierdzoną wiedzę, wybierając pliki tematyczne przez indeks.

## 10. Testowanie szkieletu

1. Testy skryptów bramek: przykładowe dobre i złe `spec.md`/`plan.md`/`status.md` z oczekiwanymi kodami wyjścia (bats lub pytest).
2. Testy hooków: symulowane wywołania narzędzi (zapis poza zakresem, edycja zamrożonej specyfikacji, przekroczony budżet) → oczekiwana blokada.
3. Lint definicji agentów i skilli: jawne wejścia/wyjścia, minimalne narzędzia, istniejące ścieżki.
4. Projekt przykładowy (`examples/`) i test dymny: `/feature` na gotowej featurze od SPEC po RETRO w trybie headless; asercje na artefaktach i stanie, nie na treści generowanej przez model.
5. Scenariusze regresyjne: SPEC-GAP (redakcyjny i merytoryczny), `TASK-TOO-BIG`, przekroczony budżet, trzy nieudane bramki → `BLOCKED`; weryfikacja stanu końcowego, uruchamiane wielokrotnie (niedeterminizm modelu).

Punkty 1–3 deterministyczne i tanie (CI szablonu); 4–5 droższe, uruchamiane przed wydaniem nowej wersji szablonu. Wersjonowanie szablonu: `.flow-version` + changelog szablonu.

## 11. Ryzyka i otwarte kwestie

- **Rozjazd kopii szablonu między projektami** — ograniczony podziałem własności plików i `.flow-version`; pełne rozwiązanie (plugin) świadomie odłożone.
- **Niedeterminizm modelu** — dlatego bramki są skryptami, a testy szkieletu sprawdzają stan, nie treść.
- **Wartości liczbowe (limity zadań, budżety)** — startowe; kalibracja po pierwszych featurach.
- **Natywne limity Claude Code** — do weryfikacji w spike (sekcja 7).
- **Jakość `architecture.md` w brownfield** — wnioskowana automatycznie, stąd Bramka 0 i oznaczenie „do weryfikacji".
