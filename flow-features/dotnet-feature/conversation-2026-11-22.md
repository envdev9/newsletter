# Rozmowa 2026-11-22: od backend-feature3 do dotnet-feature

Ślad pytań i wyjaśnień z sesji, w której workflow backend-feature3 został dopracowany i przygotowany do wdrożenia jako `dotnet-feature`.
Poprzednia sesja (2026-11-20, skąd wziął się workflow): [session-context.md](../backend-feature3/session-context.md).

## 1. Czy backend-feature3 dzieli się na orkiestratora i workera?

**Tak, ale tylko przy większych zadaniach.** Zależy od rozmiaru:

- **S** (do ~5 plików, bez migracji, bez nowego API): bez podziału. Wszystko robi główna sesja (Opus) z zasadami i TDD.
  Przekazanie kontekstu agentowi kosztowałoby więcej niż samo pisanie.
- **M/L:** podział.
  - **Koordynator (Opus):** plan z „kodem w planie” (sygnatury, DTO, DDL, trudne fragmenty, lista testów), prompt dla workera bez eksploracji,
    sam uruchamia build/testy/smoke (raport to deklaracja, nie dowód), ocenia uwagi reviewera, pilnuje bramek.
  - **Worker (`dotnet-developer` na Sonnecie):** implementuje według planu i kręci drogą pętlę edytuj → build → popraw. Haiku tylko do mechaniki.
  - **Reviewer:** jeden na Sonnecie (diff + plan); przy zmianach wrażliwych dodatkowo security na Opusie.

Sens: Opus decyduje i weryfikuje, tańszy model wykonuje drogą pętlę.

## 2. Wymagania jasne w 80%: czy TDD się opłaca, czy testy na koniec?

**Nie odkładać testów na koniec. Niejasne wymagania to argument za TDD, tylko na właściwym poziomie.**

Dlaczego nie testy na koniec:
- test po kodzie sprawdza to, co kod robi, a nie to, czego chce biznes, czyli utrwala Twoją interpretację brakujących 20%,
- zmiana wymagań i tak zmienia kod; brak testów nie oszczędza pracy, tylko ukrywa, co się zepsuło,
- „na koniec” w praktyce często znaczy „mało albo wcale”,
- lista testów w planie to kryterium „gotowe” dla workera i podstawa weryfikacji dla koordynatora.

Pisanie testu wymusza konkretną wartość („co przy ilości 0?”), więc luki wychodzą przed kodem.

Jak robić przy niepełnych wymaganiach:
1. **Najpierw pytania** do biznesu: najtańsza pozycja w całym procesie.
2. **Testy zachowania, nie implementacji:** mało testów, przez publiczne API, bez mockowania wnętrza. Zmiana wymagania zmienia 1–2 testy, nie 15.
3. **Założenia jawnie w testach:** `[Trait("Assumption", "A1")]`, a czekające na decyzję `[Fact(Skip = "czeka na decyzję A2")]`.
4. **Spike** na naprawdę mglisty fragment: wyrzucany prototyp bez testów, potem właściwa wersja w TDD.

## 3. Co spowoduje reguła „otwarte pytania i założenia”?

Reguła zmienia workflow w czterech miejscach:
1. **Plan:** sekcja „Otwarte pytania / założenia” (tylko gdy są niejasności), każdy punkt to pytanie, założenie albo spike.
2. **Bramka designu:** widzisz punkty czarno na białym. Do kodu wchodzą tylko założenia zaakceptowane świadomie, a nie zgadnięte po cichu przez model.
3. **Worker i testy:** dostaje listę założeń, testy oparte na założeniach są oznaczone, funkcje czekające na decyzję mają `Skip`.
4. **Review i raport:** reviewer szuka ukrytych założeń spoza listy; raport końcowy wymienia otwarte założenia i pominięte testy.

| Plusy | Minusy |
|---|---|
| mniej przepisywania, luki wychodzą przed kodem | plan dłuższy o kilkaset tokenów, decyzje na bramce |
| zmiana wymagania = znana lista testów do poprawy | testy ze `Skip` trzeba potem odblokować |
| nie da się „zapomnieć”, co było zgadywane | przy jasnym zadaniu sekcję pomijamy, żeby nie robić biurokracji |

Reguła została dopisana do backend-feature3 (decyzja 9) i weszła do `dotnet-feature`.

## 4. Dlaczego feature-backend to skill, a nie komenda?

W Claude Code skill to dziś komenda: każdy skill wywołasz jako `/nazwa`, a stare `~/.claude/commands/*.md` zostały w skillach scalone.

- **Pliki pomocnicze:** skill to katalog, więc obok `SKILL.md` leżą `reviewer-prompt.md` i `security-prompt.md`. Komenda to pojedynczy plik.
- **Zachowanie komendy:** `feature-backend` ma `disable-model-invocation: true`, więc model sam go nie uruchomi. Odpala go tylko `/feature-backend <opis>`, a `$ARGUMENTS` wstawia opis.
- **Jeden format:** skille mają więcej opcji, komendy to format przestarzały.

## 5. Czy model może sam uruchomić skill i czy `/dotnet-feature <opis>` też zadziała?

**Tak, oba sposoby działają.** Bez `disable-model-invocation`:
- ręcznie: `/dotnet-feature <opis>` (skille domyślnie mają `user-invocable: true`),
- automatycznie: model ładuje skill, gdy zadanie pasuje do `description`.

Brak `$ARGUMENTS` w treści nie przeszkadza: Claude Code dokleja wtedy `ARGUMENTS: <opis>` na koniec.
Uwaga: szeroki `description` sprawia, że model może sięgnąć po skill także przy drobnej zmianie i dołożyć bramkę designu.
Jeśli zacznie przeszkadzać, wystarczy zawęzić `description`.

**Decyzja:** zostawiamy automatyczne uruchamianie.

## 6. Gdzie trzymać zasady projektu (stack, jak pisać controllery, serwisy)?

**W repo projektu, nie w skillu.** Claude Code wczytuje je sam, więc skill nie potrzebuje spisu treści.

| Poziom | Gdzie | Co |
|---|---|---|
| Globalny | `~/.claude/rules/dotnet*.md` | ogólne standardy C#/.NET |
| Projekt | `<repo>/CLAUDE.md` | stack, warstwy, komendy, mapa katalogów, pliki wzorcowe |
| Projekt, szczegóły | `<repo>/.claude/rules/*.md` z `paths:` | jak pisać controllery, serwisy, repozytoria (ładuje się przy pracy na pasujących plikach) |
| Workflow | skill `dotnet-feature` | jak pracować: wymagania, design, bramki, worker, review |

- **Najskuteczniejszy jest wzorzec plus plik:** zamiast długiego opisu dajesz „wzorcowy serwis: `src/Orders/OrderService.cs`”. Model lepiej odtwarza przykład niż prozę.
- **Projekt w trakcie implementacji (spaghetti):** inwentaryzacja konwencji → decyzja i pliki wzorcowe → zapis w `CLAUDE.md` + `.claude/rules/` → nowy kod według zasad, stary przy okazji, bez wielkiego refaktoru.

## 7. Dlaczego Opus zrobił delete + insert, choć prosiłem o update?

Bez wglądu w tamtą sesję to hipotezy. Typowe przyczyny:
- **wzorzec w kodzie wygrywa z poleceniem:** jeśli w repo jest już „usuń i wstaw od nowa”, model to kopiuje (przy spaghetti częste),
- **nawyk modelu:** przy kolekcjach podrzędnych delete + insert to najprostsza i bardzo częsta implementacja „podmiany” w Dapperze,
- **polecenie zginęło w kontekście:** w długiej rozmowie albo po kompakcji jedno zdanie z czatu traci wagę,
- **niejednoznaczność:** „zrób update” mogło znaczyć „zaktualizuj dane”, a nie „użyj SQL `UPDATE`”.

Zabezpieczenia wbudowane w `dotnet-feature`:
- reguła z powodem w `dotnet-data.md` i `repo/.claude/rules/data-access.md` („`UPDATE` w miejscu, nigdy delete + insert, bo zmienia ID, psuje FK, audyt i triggery”),
- reguła w `dotnet.md`: polecenie i design wygrywają ze wzorcem z kodu, a rozbieżność trzeba zgłosić,
- design M/L zawiera SQL zapytań modyfikujących, więc widzisz `UPDATE ... WHERE id = @Id` na bramce,
- test integracyjny sprawdza, że ID się nie zmieniło,
- reviewer i checklista self-review mają ten punkt.

## 8. Implementacja: nazwa i struktura

- **Nazwa:** `dotnet-feature` (zamiast `backend-feature3`). Zmiana nazwy skilla to nazwa katalogu `skills/<nazwa>/` i pole `name:`.
- **Struktura:** `global/` (do `~/.claude/`) i `repo/` (do katalogu projektu). Szczegóły i instrukcja instalacji: [README.md](README.md).
- `feature-backend` zostaje bez zmian (do porównania). Agent `dotnet-developer` jest wspólny, więc po instalacji oba workflow mają workera na Sonnecie.

## 9. Pytania na starcie i plan krok po kroku

Pytanie: inna implementacja feature'a zadaje pytania (co, gdzie…), rozpisuje plan krok po kroku i podczas implementacji mówi „implementuję krok 1, krok 2”. Czy tu też tak będzie?

Wcześniejszy szkic tego nie miał (pytania tylko „gdy zmieniają design”, bez numerowanych kroków). Dodane do `dotnet-feature`:

- **Krok „1. Wymagania”** przed designem. Cel: zebrać pełne wymagania od razu, żeby nie dopytywać w trakcie implementacji.
  Najpierw czytanie repo (nie pytamy o to, co wynika z kodu), potem zgrupowane pytania w 1–2 rundach według listy:
  co, kto, gdzie, wejście, wyjście, przypadki brzegowe, błędy, dane/migracje, poza zakresem, kryteria akceptacji.
  Kończy się listą „Wymagania” z kryteriami akceptacji, które w designie stają się testami. Czego użytkownik nie wie, trafia do założeń.
- **„Kroki implementacji”** w designie: numerowana lista małych kroków, każdy z testem i weryfikowalnym wynikiem.
- **Implementacja krok po kroku:** lista zadań z jednym zadaniem na krok, komunikaty „Krok N/M: …” i wynik testów po każdym kroku (S).
  Przy M/L worker wykonuje kroki po kolei, a raport zawiera wynik po każdym kroku. Na bieżąco widać tylko ścieżkę S,
  bo worker pracuje w tle i jego postęp przychodzi w raporcie.

## Otwarte

- [ ] Zainstalować `dotnet-feature/global` w `~/.claude/` (instrukcja w README).
- [ ] W projekcie, gdzie był delete + insert: wkleić `repo/`, uzupełnić szablony, wskazać pliki wzorcowe.
- [ ] Pierwszy test: jedno zadanie S i jedno M przez `/dotnet-feature`, porównać zużycie limitu z `feature-backend`.
- [ ] Sprawdzić w praktyce, czy `paths:` w `~/.claude/rules/` faktycznie ogranicza ładowanie do plików .NET (jeśli nie, przenieść import do `CLAUDE.md` repo).
