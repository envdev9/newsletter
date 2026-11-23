---
name: backend-feature3
description: Implementacja funkcji backendowej .NET tanio i zgodnie ze standardami. Małe zadania robi główna sesja sama, większe koordynator (plan z sygnaturami) + worker dotnet-developer na Sonnecie. Jeden reviewer, bramki na design i commit.
---

# backend-feature3

Wykonuj kroki po kolei. Nie przeskakuj bramek.

## 0. Zasady

- Przeczytaj `~/.claude/rules/dotnet.md` (jeśli nie jest już w kontekście z CLAUDE.md).
- Jeśli zadanie dotyczy bazy, przeczytaj `~/.claude/rules/dotnet-data.md`. Jeśli dotyczy API, deployu lub Kubernetesa, przeczytaj `~/.claude/rules/dotnet-cloud.md`.

## 1. Design

- Przeczytaj tylko potrzebne części repo: strukturę, sąsiedni kod, komendy build i test.
- Pytania tylko wtedy, gdy zmieniają design (pojedynczo, max kilka).
- Oceń rozmiar: **S** (do ~5 plików, bez migracji, bez nowego kontraktu API) albo **M/L**.
- Przedstaw design:
  - S: pliki, zachowanie, testy.
  - M/L: dodatkowo **sygnatury publicznych typów i metod, DTO, DDL migracji, trudne fragmenty algorytmu, lista testów (nazwa + co sprawdza)**.
- Jeśli wymagania są niejasne, dodaj sekcję **„Otwarte pytania / założenia”** (przy jasnym zadaniu pomiń). Każdy punkt oznacz:
  - **pytanie**: blokuje, potrzebna odpowiedź przed implementacją,
  - **założenie** (A1, A2…): „zakładam X, bo Y”,
  - **spike**: najpierw wyrzucany prototyp bez testów, potem właściwa wersja w TDD.
- **STOP.** Czekaj na wyraźne „tak”. Do implementacji wchodzą tylko założenia zaakceptowane przez użytkownika.

## 2. Implementacja

**S:** implementuj sam, TDD (test, który się wywala, potem kod, potem `dotnet test`), zgodnie z `rules/dotnet.md`.

**M/L:** uruchom `dotnet-developer` (Sonnet). Prompt musi zawierać:
- zatwierdzony design z sekcją kodu,
- dokładne ścieżki plików do utworzenia i zmiany oraz 1–2 pliki wzorcowe,
- komendy build i test,
- ograniczenia: bez commita, tylko lokalna lub testowa baza, bez zmian poza listą plików.
- listę zaakceptowanych założeń i regułę oznaczania testów (niżej).

**Testy przy niejasnych wymaganiach (S i M/L):**
- test oparty na założeniu: `[Trait("Assumption", "A1")]`,
- funkcja czekająca na decyzję: `[Fact(Skip = "czeka na decyzję A2")]` zamiast zgadywanej implementacji,
- testy przez publiczne API, bez mockowania wnętrza, żeby zmiana wymagania zmieniała mało testów.
- Testów nie odkładaj na koniec.

Po raporcie uruchom **sam** `dotnet build`, `dotnet test` i smoke test aplikacji. Nie ufaj samemu raportowi.

## 3. Review

- S: self-review diffu według checklisty z `rules/dotnet.md`.
- M/L: jeden subagent `general-purpose` (model: sonnet) z `review-prompt.md` + diff + design. Tylko czyta.
- Zmiany wrażliwe (auth, SQL, sekrety, upload, dane osobowe): dodatkowo `security-prompt.md` na Opusie.
- Reviewer sprawdza też ukryte założenia w kodzie, których nie ma na liście z designu.
- Oceń ustalenia krytycznie, odrzuć fałszywe alarmy z uzasadnieniem. Poprawki: S sam, M/L przez workera.
- Po poprawkach ponownie build, test i smoke.

## 4. Commit

- Pokaż `git status` + podsumowanie (co, testy, review, ścieżka S lub M/L, **otwarte założenia i testy ze `Skip`**).
- Commit po potwierdzeniu. Push tylko na wyraźną prośbę.

## Zasady

- Raportuj uczciwie: padające testy z outputem, pominięte kroki wprost.
- Jeśli zadanie okaże się większe (S → M/L, nowy podsystem, zmiana kontraktu), zatrzymaj się i wróć do kroku 1.
- Zmiany w Helm, deployu i CI proponuj jako osobny krok (skill `helm-deploy`), nie rób ich sam.
