# Kontekst sesji: skąd wziął się backend-feature3

Zapis rozmowy o workflow z sesji 2026-11-20, w której powstała aplikacja
[`timer-list-exercises`](https://gitea.loriapps.net/tech02/timer-list-exercises).
Decyzje i analiza kosztów są w [README.md](README.md). Tu jest przebieg i surowe obserwacje.

## Przebieg

1. **Start przez skill `feature-backend`** (`~/.claude/skills/feature-backend/SKILL.md`).
   Skill zakłada: design → STOP → implementacja przez `dotnet-developer` → dwóch reviewerów (`general-purpose`
   z `reviewer-prompt.md` i `security-prompt.md`) równolegle → poprawki → commit.
   Zakłada też ASP.NET Core, Dapper/Postgres, Aspire, Kubernetes i TeamCity.
2. **Niedopasowanie skilla do zadania.** Zadanie to interaktywna konsola .NET + Docker z wyjściem JSON:
   bez bazy, bez API, bez K8s. Kroki o migracjach, bazie testowej, Aspire i helm zostały pominięte jako nie dotyczące zadania.
3. **Bramki designu zadziałały dobrze.** Trzy rundy designu przed kodem:
   - UX klawiszy,
   - warianty ćwiczenia (Tab / Ctrl+Y),
   - menu N/A z dopisywaniem i offsetem liczonym w kolejnych uruchomieniach.
   Każda runda zmieniła design, a żadna nie wymagała przepisywania kodu.
4. **Użytkownik zgłosił mały limit** („mam mało limitu, chciałbym zmieścić się w tej sesji”).
   Decyzja asystenta: implementacja i review w głównej sesji, **bez subagentów**, bo każdy startuje na zimno
   i od nowa czyta kontekst. Odstępstwo zostało zgłoszone wprost w podsumowaniu.
5. **Wynik:** ~600 linii, 23 testy, smoke testy w kontenerze przez pseudo-terminal (`script -qec "docker run -it ..."`),
   dwa commity, push. Zmieściło się w sesji.
6. **Obserwacja użytkownika:** gdy Opus pisze sam, kod bywa „spaghetti bez dobrych praktyk”, a `dotnet-developer`
   pisał zgodnie z zasadami. Pytanie: jak zrobić tanio, ale z praktykami dotnet-developera?
7. **Diagnoza** (po przeczytaniu `~/.claude/agents/dotnet-developer.md`, 118 linii):
   - Jakość agenta wynika z jego system promptu (zasady), a nie z bycia osobnym agentem.
   - Główna sesja tych zasad nie widziała, bo skill tylko kazał uruchomić agenta.
   - Uczciwa samoocena kodu timer-a względem tych zasad:
     - brak TDD (testy po kodzie),
     - brak DI i interfejsów (`StartMenu` statyczny, bezpośrednio na `Console`),
     - `Thread.Sleep` w pętli zamiast `async` + `CancellationToken`,
     - `catch (Exception)` w `Save()`.
   - Dobre strony: czysta logika domenowa (`TrainingSession`), edytor wejścia niezależny od konsoli i przetestowany, rekordy DTO, nullable bez ostrzeżeń.
8. **Pytanie o wzorzec koordynator (Opus) + worker (Haiku), gdzie „koordynator nie pisze kodu, a w planie jest kod”.**
   Wyjaśnienie:
   - Kod w planie to **decyzje**: sygnatury, DTO, DDL, trudne fragmenty i lista testów.
   - „Nie pisze kodu” znaczy, że nie kręci pętli edytuj → build → popraw, która zjada najwięcej tokenów.
   - Słaby model źle decyduje, ale dobrze odtwarza gotowy wzór.
   - Rekomendacja: worker na Sonnecie, a Haiku tylko do mechaniki.
9. **Decyzja użytkownika:** nie poprawiać istniejącego `feature-backend`, tylko zaprojektować nowy workflow
   **backend-feature3** i opisać go w tym repo, z kosztami i osobno ze słabymi stronami.

## Zasady wynikające z tej sesji (do przeniesienia do skilla/zasad)

- **Pytaj o limit/budżet na starcie** przy większych zadaniach i dobieraj ścieżkę (S inline / M-L z workerem).
- **Smoke test aplikacji robi koordynator.** Przy konsolach interaktywnych: `script -qec "<cmd>" /dev/null` z wejściem z `printf`.
  To wyłapuje rzeczy, których nie łapią testy jednostkowe (TTY, kodowanie znaków, sygnały, prawa do plików w wolumenie).
- **Push do Gitei tech02:** HTTPS wymaga logowania. Repo FieldReport pushują po SSH:
  `ssh://git@192.168.1.91:30022/tech02/<repo>.git`. Ustawiamy `git remote set-url --push origin <ssh-url>`,
  a pobieranie zostaje po HTTPS. Kluczy nie trzeba czytać, a `~/.ssh/config` i tak blokuje reguła uprawnień.
- **Skill musi pasować do typu projektu.** Założenia o Dapperze, K8s i Aspire w skillu backendowym przy konsolówce są szumem.
  Stąd w backend-feature3 zasady dzielą się na `dotnet.md` (zawsze) oraz `dotnet-data.md` i `dotnet-cloud.md` (gdy dotyczy).
- **Commit i push zawsze po potwierdzeniu,** nawet przy niskim budżecie. Bramka kosztuje jedną wiadomość.

## Otwarte

- [x] Przygotować pliki do wdrożenia: `dotnet-feature/` (2026-11-22). Instalacja w `~/.claude/` jeszcze nie zrobiona.
- [ ] Pierwszy test: następne zadanie S i jedno M przez backend-feature3, porównać zużycie limitu z `feature-backend`.
  Kandydat: refaktor `timer-list-exercises` pod `rules/dotnet.md`.
- [x] Połączyć `reviewer-prompt.md` i `security-prompt.md` w `review-prompt.md` (`dotnet-feature/global/skills/dotnet-feature/review-prompt.md`).
