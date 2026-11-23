---
name: dotnet-feature
description: Implementacja funkcji lub zmiany w kodzie .NET tanio i zgodnie ze standardami. Małe zadania robi główna sesja sama, większe koordynator (plan z sygnaturami i SQL) + worker dotnet-developer na Sonnecie. Zbiera pełne wymagania pytaniami na starcie, plan krok po kroku, jawne założenia, TDD, jeden reviewer, bramki na design i commit.
---

# dotnet-feature

Wykonuj kroki po kolei. Nie przeskakuj bramek.

## 0. Zasady

- Przeczytaj `~/.claude/rules/dotnet.md` (jeśli nie ma go już w kontekście).
- Zadanie dotyczy bazy, zapytań, migracji lub testów integracyjnych: przeczytaj `~/.claude/rules/dotnet-data.md`.
- Zadanie dotyczy API, hostingu, Aspire, Dockera lub CI: przeczytaj `~/.claude/rules/dotnet-cloud.md`.
- Zasady repo (`CLAUDE.md`, `.claude/rules/`) mają pierwszeństwo przed globalnymi. Pliki wzorcowe z nich są wzorem dla nowego kodu.
- Przy większym zadaniu zapytaj o budżet/limit, jeśli użytkownik go nie podał. Wpływa na wybór ścieżki S lub M/L.

## 1. Wymagania

Cel: zebrać od razu pełne wymagania, żeby nie dopytywać w trakcie implementacji.

- Najpierw przeczytaj tylko potrzebne części repo: strukturę, sąsiedni kod, pliki wzorcowe, komendy build i test.
  O nic, co da się ustalić z kodu, nie pytaj.
- Przejdź po liście i dla każdego punktu, który nie wynika z opisu zadania ani z kodu, zadaj pytanie:
  - **Co:** jakie zachowanie, co jest wynikiem, co dokładnie się zmienia (np. aktualizacja w miejscu czy podmiana)?
  - **Kto:** kto wywołuje, jakie uprawnienia, czyje dane?
  - **Gdzie:** która warstwa, endpoint, ekran, tabela; nowy element czy zmiana istniejącego?
  - **Wejście:** pola, typy, wymagalność, limity, format, walidacja?
  - **Wyjście:** odpowiedź, kody/komunikaty, co się zapisuje, zdarzenia, logi?
  - **Przypadki brzegowe:** puste, zero, duplikaty, nieistniejący zasób, równoległa edycja, duże wolumeny?
  - **Błędy:** co się dzieje przy błędzie walidacji, braku zasobu, awarii zależności?
  - **Dane:** zmiany schematu, migracja istniejących danych, wsteczna kompatybilność?
  - **Poza zakresem:** czego świadomie nie robimy?
  - **Kryteria akceptacji:** po czym poznamy, że jest gotowe (2–5 konkretnych scenariuszy)?
- Pytaj w jednej lub dwóch rundach, zgrupowane (AskUserQuestion, do 4 pytań na raz, z propozycjami odpowiedzi
  i rekomendowaną opcją), a nie po jednym przez całą rozmowę. Przy prostym zadaniu pytań może być zero.
- Na koniec wypisz **„Wymagania”**: krótka lista ustaleń + kryteria akceptacji. Na to, czego użytkownik nie wie,
  nie zgaduj: to trafia do „Otwartych pytań / założeń” w designie.

## 2. Design

- Oceń rozmiar: **S** (do ~5 plików, bez migracji, bez nowego kontraktu API) albo **M/L**.
- Przedstaw design oparty na „Wymaganiach” (kryteria akceptacji stają się testami):
  - S: pliki, zachowanie, testy.
  - M/L: dodatkowo **sygnatury publicznych typów i metod, DTO, DDL migracji, SQL zapytań modyfikujących dane, trudne fragmenty algorytmu, lista testów (nazwa + co sprawdza)**.
- Zakończ design sekcją **„Kroki implementacji”**: numerowana lista małych kroków, każdy z testem i weryfikowalnym wynikiem
  (np. „1. Rekord `UpdateOrderRequest` + walidacja, testy walidacji”, „2. `OrderRepository.UpdateAsync` z `UPDATE`, test integracyjny”).
  S: 2–4 kroki, M/L: tyle, ile trzeba. Krok, który zmienia więcej niż kilka plików, podziel.
- Jeśli wymagania są niejasne, dodaj sekcję **„Otwarte pytania / założenia”** (przy jasnym zadaniu pomiń). Każdy punkt oznacz:
  - **pytanie**: blokuje, potrzebna odpowiedź przed implementacją,
  - **założenie** (A1, A2…): „zakładam X, bo Y”,
  - **spike**: najpierw wyrzucany prototyp bez testów, potem właściwa wersja w TDD.
- **STOP.** Czekaj na wyraźne „tak”. Do implementacji wchodzą tylko założenia zaakceptowane przez użytkownika.

## 3. Implementacja

Pracuj według „Kroków implementacji” z designu, po kolei. Postęp prowadź na liście zadań (TodoWrite/Task), jedno zadanie na krok.

**S:** implementuj sam, krok po kroku. Przed krokiem napisz jedną linię „Krok N/M: <co>”, po kroku jedną linię z wynikiem testów.
Każdy krok w TDD (test, który się wywala, potem kod, potem `dotnet test`).

**M/L:** uruchom agenta `dotnet-developer` (Sonnet). Agent nie widzi tej rozmowy. Prompt musi zawierać:
- zatwierdzony design z sekcją kodu i „Krokami implementacji” (agent wykonuje je po kolei, w raporcie wynik testów po każdym kroku),
- dokładne ścieżki plików do utworzenia i zmiany oraz 1–2 pliki wzorcowe,
- które pliki zasad przeczytać (`dotnet-data.md`, `dotnet-cloud.md`, jeśli dotyczy),
- komendy build i test,
- listę zaakceptowanych założeń,
- ograniczenia: bez commita, tylko lokalna lub testowa baza, bez zmian poza listą plików.

**Testy przy niejasnych wymaganiach (S i M/L):**
- test oparty na założeniu: `[Trait("Assumption", "A1")]`,
- funkcja czekająca na decyzję: `[Fact(Skip = "czeka na decyzję A2")]` zamiast zgadywanej implementacji,
- testy przez publiczne API, bez mockowania wnętrza, żeby zmiana wymagania zmieniała mało testów.
- Testów nie odkładaj na koniec.

Po implementacji uruchom **sam** `dotnet build`, `dotnet test` i smoke test aplikacji. Nie ufaj samemu raportowi agenta.

## 4. Review

- S: self-review diffu według checklisty z `~/.claude/rules/dotnet.md`. Przy nietrywialnej logice (współbieżność, czas, bezpieczeństwo) i tak uruchom reviewera jak dla M/L.
- M/L: jeden subagent `general-purpose` (model: sonnet) z `review-prompt.md` (obok tego pliku) + diff + design. Tylko czyta.
- Zmiany wrażliwe (auth, SQL budowany dynamicznie, sekrety, upload plików, dane osobowe): dodatkowo subagent z `security-prompt.md` na Opusie, niezależnie od rozmiaru.
- Reviewer sprawdza też ukryte założenia w kodzie, których nie ma na liście z designu.
- Oceń ustalenia krytycznie, odrzuć fałszywe alarmy z uzasadnieniem. Poprawki: S sam, M/L przez workera.
- Po poprawkach ponownie build, test i smoke.

## 5. Commit

- Pokaż `git status` + podsumowanie (co, testy, review, ścieżka S lub M/L, **otwarte założenia i testy ze `Skip`**).
- Commit po potwierdzeniu. Push tylko na wyraźną prośbę.

## Zasady

- Raportuj uczciwie: padające testy z outputem, pominięte kroki wprost.
- Jeśli zadanie okaże się większe (S → M/L, więcej niż ~5 plików, nowy podsystem, zmiana kontraktu), zatrzymaj się i wróć do kroku 1 (wymagania) lub 2 (design).
- Po kompakcji kontekstu przeczytaj ponownie `~/.claude/rules/dotnet.md` i zasady repo.
- Zmiany w Helm, deployu i CI proponuj jako osobny krok (skill `helm-deploy`), nie rób ich sam.
