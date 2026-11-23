# backend-feature3: tanio i dobrze

> Wersja do wdrożenia: [dotnet-feature](../dotnet-feature/README.md) (zmieniona nazwa, krok wymagań, plan krok po kroku, szablony zasad repo).

Wnioski z sesji, w której powstała aplikacja `timer-list-exercises` (konsola .NET 10 + Docker, ~600 linii, 23 testy),
i propozycja nowego workflow, który zastąpi `feature-backend`.

## Problem

Obecny `feature-backend` ma trzy subagenty: `dotnet-developer` do implementacji oraz dwóch `general-purpose` reviewerów (code i security).

| Obserwacja | Skutek |
|---|---|
| Każdy subagent startuje „na zimno”: od nowa czyta repo, ma własny system prompt i własną pętlę narzędzi. | Przy małym zadaniu narzut agentów jest większy niż sama praca. |
| Żeby oszczędzić limit, kod napisał sam Opus w głównej sesji. | Było tanio, ale kod nie trzymał standardów agenta: brak TDD, brak DI, `Thread.Sleep` zamiast `async` + `CancellationToken`, `catch (Exception)`. |
| Jakość `dotnet-developer` wynika z jego 118 linii zasad w system prompcie, a nie z tego, że jest osobnym agentem. | Główna sesja tych zasad nie widziała. Ten sam model z tymi zasadami pisze tak samo. |

**Wniosek:** jakość daje treść zasad, a koszt daje liczba zimnych startów i to, który model kręci pętlę edytuj → build → popraw.

## Decyzje

### 1. Zasady w jednym pliku, który widzą wszyscy

**Co:** ogólne standardy C#/.NET (TDD, nullable, async + CancellationToken, DI, obsługa błędów, krótkie metody)
trafiają do `~/.claude/rules/dotnet.md`. Ładują go:
- główna sesja, przez import w `~/.claude/CLAUDE.md`: `@~/.claude/rules/dotnet.md`;
- agent `dotnet-developer`, przez odwołanie w swoim prompcie zamiast kopii.

Sekcje specyficzne (Dapper/Postgres, API, Kubernetes, Aspire, SqlDeployer) zostają w osobnych plikach
(`rules/dotnet-data.md`, `rules/dotnet-cloud.md`). Skill czyta je tylko wtedy, gdy zadanie ich dotyczy.

**Dlaczego:**
- Jedno źródło prawdy, więc nie ma rozjazdu między agentem a główną sesją.
- Ogólne zasady to kilka tysięcy tokenów w kontekście, czyli dużo mniej niż jeden zimny start agenta.
- Konsolówka nie płaci za zasady Dappera i Kubernetesa.

### 2. Ścieżka zależna od rozmiaru zadania

| Rozmiar | Kryterium (orientacyjnie) | Kto implementuje |
|---|---|---|
| **S** | Do ~5 plików, bez zmian schematu bazy, bez nowego kontraktu API | **Główna sesja (Opus) sama**, z załadowanymi zasadami, TDD |
| **M/L** | Więcej plików, migracje, nowe endpointy, kilka warstw | **Koordynator (Opus) robi plan, worker (Sonnet) implementuje** |

**Dlaczego:**
- Przy S przekazanie kontekstu agentowi kosztuje więcej niż samo pisanie.
- Przy M/L pętla build/test jest długa i tam opłaca się tańszy model. Główny kontekst Opusa zostaje też czysty na review i decyzje.

### 3. Koordynator pisze „kod w planie”, a worker pisze kod

Plan zawiera fragmenty kodu, bo **kod w planie to decyzje**, a nie implementacja:
- sygnatury publicznych typów i metod, interfejsy, rekordy DTO,
- schemat bazy (DDL migracji),
- trudny fragment algorytmu, jeśli jest (np. liczenie offsetu w uruchomieniach),
- lista testów: nazwa testu i co sprawdza.

Koordynator **nie** wchodzi w pętlę edytuj → build → czytaj błędy → popraw. To ta pętla zjada najwięcej tokenów
i ją dostaje tańszy model.

**Dlaczego:** słabszy model źle podejmuje decyzje projektowe, ale dobrze odtwarza gotowy wzór. Opus wydaje
kilka tysięcy tokenów na precyzyjny plan, a worker przepala dziesiątki tysięcy na wpisywanie.

### 4. Worker = Sonnet, Haiku tylko do mechaniki

**Co:** `dotnet-developer` dostaje `model: sonnet` we frontmatterze. Haiku tylko do zadań czysto mechanicznych
(rename, przeniesienie plików, boilerplate według wzoru 1:1).

**Dlaczego:** przy C# z DI, async i testami Haiku częściej zbacza z zasad i robi więcej rund poprawek.
Tańszy token nie pomaga, gdy rund jest dwa razy więcej.

### 5. Prompt workera bez eksploracji

Worker dostaje w prompcie wszystko, czego potrzebuje, żeby nie czytał repo od zera:
- zatwierdzony plan (z sekcją kodu z pkt 3),
- **dokładne ścieżki** plików do utworzenia i zmiany oraz 1–2 pliki wzorcowe do naśladowania,
- komendy `build`, `test` (i `docker build`, jeśli dotyczy),
- ograniczenia: bez commita, tylko lokalna lub testowa baza, nie zmieniaj plików spoza listy.

**Dlaczego:** największy koszt zimnego startu to czytanie repo. Ścieżki i komendy podane wprost ucinają go prawie całkowicie.

### 6. Jeden reviewer zamiast dwóch

| Rozmiar | Review |
|---|---|
| S | Self-review w głównej sesji według checklisty z `rules/dotnet.md` |
| M/L | **Jeden** subagent na Sonnecie, z promptem code + security w jednym, dostaje **sam diff** + plan |
| Wrażliwe (auth, SQL, sekrety, upload plików, dane osobowe) | Osobny security reviewer na Opusie, niezależnie od rozmiaru |

**Dlaczego:**
- Dwóch reviewerów czyta ten sam diff i w większości zgłasza te same rzeczy.
- Osobny przegląd security ma sens tylko tam, gdzie powierzchnia ataku jest realna.
- Koordynator i tak ocenia każde ustalenie krytycznie i odrzuca fałszywe alarmy.

### 7. Weryfikacja zawsze robi koordynator

`dotnet build` i `dotnet test` (oraz smoke test aplikacji: `docker run` / `dotnet run` ze scenariuszem) uruchamia główna sesja sama, po raporcie workera.
Raport agenta to deklaracja, a nie dowód.

**Dlaczego:** w sesji timer-a dopiero test end-to-end w kontenerze (pseudo-terminal, `script`) potwierdził, że czas startuje od
pierwszej litery, polskie znaki przechodzą, a Ctrl+C zapisuje plik. Testy jednostkowe tego nie pokazały.

### 8. Bramki zostają

1. Design: **STOP**, czekaj na wyraźne „tak”.
2. Commit: pokaż `git status` + podsumowanie, czekaj na potwierdzenie.
3. Push: tylko gdy użytkownik o niego prosi. Remote po SSH, jeśli HTTPS wymaga logowania (jak w repo FieldReport).

**Dlaczego:** bramki są tanie (jedna wiadomość) i chronią przed najdroższym błędem, czyli zrobieniem nie tego, co trzeba.

### 9. Niejasne wymagania: jawne pytania i założenia, TDD zostaje

**Co:** gdy wymagania są wyjaśnione tylko częściowo, plan dostaje sekcję **„Otwarte pytania / założenia”**
(tylko wtedy, gdy są niejasności; przy jasnym zadaniu sekcji nie ma). Każdy punkt ma jeden status:
- **pytanie**: blokuje sensowny start, więc trzeba odpowiedzi przed implementacją,
- **założenie**: „zakładam X, bo Y”, łatwe do zmiany, wchodzi do implementacji po akceptacji na bramce designu,
- **spike**: za mało wiadomo nawet na założenie, więc najpierw krótki, wyrzucany prototyp bez testów, a potem właściwa wersja w TDD.

W testach:
- test oparty na założeniu ma to w nazwie lub atrybucie, np. `[Trait("Assumption", "A1")]`, z odwołaniem do punktu w planie,
- funkcja czekająca na decyzję biznesu dostaje test `[Fact(Skip = "czeka na decyzję A2")]` zamiast zgadywanej implementacji,
- testy sprawdzają zachowanie przez publiczne API (mało testów, bez mockowania wnętrza), więc zmiana wymagania zmienia 1–2 testy, a nie kilkanaście.

Reviewer sprawdza też, czy w kodzie nie ma ukrytych założeń spoza listy. Raport końcowy wymienia otwarte założenia i pominięte testy.

**Dlaczego nie testy na koniec:**
- Test pisany po kodzie sprawdza to, co kod robi, a nie to, czego chce biznes. Utrwala niezweryfikowaną interpretację luk.
- Pisanie testu wymusza konkretną wartość („co przy ilości 0?”), więc luki w wymaganiach wychodzą przed kodem, a nie po nim.
- Zmiana wymagania i tak zmienia kod. Brak testów nie oszczędza pracy, tylko ukrywa, co się przy okazji zepsuło.
- Lista testów w planie to kryterium „gotowe” dla workera i podstawa weryfikacji dla koordynatora.

**Koszt:** kilkaset tokenów Opusa więcej w planie i decyzje użytkownika na bramce. Testy ze `Skip` trzeba potem odblokować, inaczej zostają martwe.

## Koszty: dlaczego taniej i równie dobrze

### Z czego składa się koszt

W pracy agentowej płaci się głównie za **tokeny wejściowe powtarzane w każdej turze**. Każde wywołanie narzędzia
(Read, Edit, Bash) to kolejne zapytanie do modelu z całym dotychczasowym kontekstem. W uproszczeniu:

```
koszt ≈ Σ po turach (rozmiar kontekstu × cena tokenu modelu) + tokeny wyjściowe
```

Koszt rośnie więc z trzech powodów:
1. **Liczba tur.** Pętla edytuj → build → czytaj błędy → popraw to dziesiątki tur.
2. **Rozmiar kontekstu.** Każdy przeczytany plik i każdy output builda jedzie dalej w każdej kolejnej turze.
3. **Cena modelu.** Opus jest droższy za token niż Sonnet, a Sonnet niż Haiku.

Prompt caching obniża cenę powtarzanego kontekstu, ale tylko kontekstu „ciepłego”. Nowy subagent zaczyna z zimnym cache.

### Gdzie backend-feature3 oszczędza

| Źródło kosztu | feature-backend | backend-feature3 | Dlaczego mniej |
|---|---|---|---|
| Zimne starty | 3 agenty: każdy ładuje system prompt + narzędzia i **ponownie czyta te same pliki**, które główna sesja już przeczytała | S: 0, M/L: 1 worker + 1 reviewer | Mniej powtórnego czytania repo i mniej zimnego cache |
| Pętla build/fix | agent (model zależny od definicji) | S: Opus, ale krótka pętla. M/L: **Sonnet** | Najdłuższa pętla idzie na tańszym modelu |
| Eksploracja workera | worker sam szuka plików i konwencji | ścieżki, pliki wzorcowe i komendy w prompcie | Mniej tur „rozglądania się” i mniej plików w kontekście |
| Review | 2 agenty czytają ten sam diff, wyniki w dużej części się pokrywają | 1 agent z połączonym promptem, security na Opusie tylko dla zmian wrażliwych | Diff czytany raz, bez dublowania ustaleń |
| Plan | design bez sygnatur, więc worker sam podejmuje decyzje i czasem robi rundy poprawek | plan z sygnaturami, DTO, DDL i listą testów | Mniej rund „zrobił inaczej niż trzeba” |
| Zasady | 118 linii tylko w agencie | wspólny plik, cache'owany w głównej sesji | Ogólne zasady to mały, stały koszt zamiast kopiowania kontekstu do agenta |

### Dlaczego jakość zostaje

Jakość wyznaczają trzy rzeczy. Żadna nie zależy od tego, czy kod pisze osobny agent:

1. **Zasady.** Te same co w `dotnet-developer`, tylko w pliku, który widzi też główna sesja.
2. **Decyzje projektowe.** Podejmuje je Opus w designie, zatwierdzone przez człowieka. W M/L są zapisane w planie na poziomie sygnatur, więc worker ich nie zgaduje.
3. **Weryfikacja.** Build, testy i smoke test uruchamia koordynator sam. To, a nie deklaracja agenta, decyduje o „działa”.

Model workera (Sonnet) dostaje zadanie odtwórcze z precyzyjnym planem i zasadami. W takim trybie różnica jakości względem Opusa jest mała,
a koordynator i tak łapie odstępstwa na review i w testach.

## Słabe strony względem pełnego workflow z dotnet-developer

Ten workflow jest tańszy, ale nie jest darmowy. Traci się:

- **Niezależne oko przy małych zadaniach.** W ścieżce S kod pisze i przegląda ta sama sesja. Autor ma tendencję do potwierdzania
  własnych założeń. Osobny reviewer ze świeżym kontekstem łapie więcej, właśnie dlatego, że nie zna „intencji” autora.
- **Słabnącą pozycję zasad w długiej sesji.** Agent ma zasady w system prompcie, zawsze na początku i z najwyższym priorytetem.
  W głównej sesji zasady z CLAUDE.md konkurują z długą rozmową, a po kompakcji kontekstu mogą zostać streszczone.
  Ryzyko dryfu (jak w sesji timer-a) rośnie wraz z długością rozmowy.
- **Koszt błędnej klasyfikacji S.** Jeśli zadanie „S” okaże się większe, długa pętla build/fix kręci się na drogim Opusie,
  w dodatku w zapchanym kontekście. Wtedy wychodzi drożej niż `feature-backend`.
- **Zależność od jakości planu w M/L.** Sonnet wiernie odtwarza plan, więc błąd w sygnaturach lub w DDL przechodzi dalej.
  Agent na mocniejszym modelu częściej sam zauważy, że plan nie pasuje do kodu.
- **Mniejszą różnorodność review.** Jeden reviewer z połączonym promptem rzadziej znajdzie problem bezpieczeństwa niż dedykowany.
  Jeśli zmianę błędnie uznamy za „niewrażliwą”, security review w ogóle się nie odbędzie.
- **Stały koszt zasad w każdej sesji.** Import w `~/.claude/CLAUDE.md` ładuje się też w sesjach niezwiązanych z .NET (infra, notatki, Android).
- **Brak izolacji.** Implementacja w głównej sesji miesza rozmowę, decyzje i kod w jednym kontekście.
  Agent (opcjonalnie w osobnym worktree) pracuje w czystym środowisku.

**Jak ograniczyć te słabości:**
- Przy S z logiką nietrywialną (współbieżność, czas, bezpieczeństwo) i tak uruchom jednego reviewera.
- Po każdej kompakcji przeczytaj `rules/dotnet.md` ponownie.
- Gdy w trakcie S zmienia się więcej niż ~5 plików, przełącz na M/L.
- Import zasad trzymaj w `CLAUDE.md` repo .NET zamiast globalnym, jeśli koszt w innych sesjach przeszkadza.

## Porównanie

| | feature-backend (obecny) | Opus sam, bez zasad | **backend-feature3** |
|---|---|---|---|
| Zimne starty agentów | 3 (dev + 2 review) | 0 | S: 0, M/L: 1–2 |
| Kto kręci pętlę build/fix | agent | Opus | S: Opus, M/L: Sonnet |
| Standardy kodu | tak (prompt agenta) | **nie** | tak (wspólny plik zasad) |
| Review | 2 agenty | brak lub pobieżne | S: self, M/L: 1 agent, wrażliwe: +security |
| Koszt przy małym zadaniu | wysoki | niski | niski |
| Koszt przy dużym zadaniu | średni | wysoki (Opus w pętli) | średni-niski |

## Szkic wdrożenia

1. Wydzielić z `~/.claude/agents/dotnet-developer.md`:
   - `~/.claude/rules/dotnet.md`: sekcje „Zasady pracy” i „Standardy C# / .NET” + checklista self-review,
   - `~/.claude/rules/dotnet-data.md`: „Dapper i PostgreSQL”, „Migracje: SqlDeployer”,
   - `~/.claude/rules/dotnet-cloud.md`: „API”, „Cloud-ready (Kubernetes)”, Aspire.
2. `~/.claude/CLAUDE.md`: dodać `@~/.claude/rules/dotnet.md`.
3. `dotnet-developer.md`: `model: sonnet`, a w treści odwołania do plików zasad zamiast kopii.
4. Nowy skill `~/.claude/skills/backend-feature3/SKILL.md` według [SKILL.md](SKILL.md) z tego katalogu.
5. Połączyć `reviewer-prompt.md` i `security-prompt.md` w jeden `review-prompt.md`, a security na Opusie zostawić jako wariant dla zmian wrażliwych.
6. Przetestować na następnym zadaniu S i jednym M i porównać zużycie limitu z `feature-backend`.
