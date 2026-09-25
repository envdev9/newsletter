<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #1 — 24 września 2026

![AI](https://img.shields.io/badge/AI_%2F_Claude_Code-D97757?style=for-the-badge&logo=anthropic&logoColor=white)

## Trzy konfiguracje Claude Code, które realnie skracają dzień pracy w .NET/Angular/SQL

</div>

---

> _"Custom slash command to nie skrót klawiszowy do 'napisz mi kod' - to zapisana,
> powtarzalna procedura, którą Claude Code wykonuje tak samo za każdym razem, z
> weryfikacją na końcu, zamiast za każdym razem tłumaczyć to samo od nowa w czacie."_

Dziś nie o tym "że AI pomaga kodować", tylko o trzech konkretnych plikach
konfiguracyjnych, które można wrzucić do repo `.claude/` **dzisiaj** i mieć z nich
korzyść jutro rano: **slash command** generujący testy jednostkowe dla klasy C#,
**hook** blokujący zapis migracji SQL bez rollbacku, i **skill** do code-review
komponentu Angular. Wszystkie trzy pliki są w [`code/`](code/), zwalidowane skryptem
i (tam gdzie się dało bez samego Claude Code) faktycznie uruchomione.

---

## 1️⃣ Slash command: generator testów xUnit dla klasy C#

### Problem, który to rozwiązuje

Dopisywanie testów jednostkowych do nowej/zmienionej klasy to praca, którą każdy
robi trochę inaczej: różne nazewnictwo metod testowych, różny poziom pokrycia
edge case'ów, czasem ktoś zapomina przetestować rzucany wyjątek. W code review
wraca to jako komentarz "brakuje testu na X" - runda tam i z powrotem, która kosztuje
więcej czasu niż samo napisanie testu by kosztowało za pierwszym razem.

### Co się zyskuje

Plik [`code/claude-commands/gen-csharp-tests.md`](code/claude-commands/gen-csharp-tests.md)
to custom slash command - w projekcie docelowym ląduje jako
`.claude/commands/gen-csharp-tests.md`, a w Claude Code wywołuje się go jako
`/gen-csharp-tests src/Services/OrderService.cs`. Frontmatter pliku deklaruje, jakich
narzędzi command może używać (`allowed-tools`), a treść to **procedura krok po
kroku**: przeczytaj klasę, znajdź projekt testowy, wygeneruj testy w konwencji
Arrange-Act-Assert pokrywające happy path + brzegi + wyjątki, a na koniec **sam
uruchom `dotnet build` i `dotnet test`** i popraw się, jeśli coś nie przechodzi.

To ostatnie jest kluczowe: command nie kończy pracy na "wygenerowałem plik", tylko
weryfikuje, że to co wygenerował faktycznie się kompiluje i przechodzi, zanim odda
kontrolę z powrotem. Realny zysk: testy dla typowej klasy serwisowej (konstruktor +
3-4 publiczne metody) to zwykle 15-30 minut pracy ręcznej łącznie z odpaleniem i
poprawkami - z tym commandem to jedno wywołanie, które **samo się weryfikuje**, więc
to co trafia do review jest już zielone na `dotnet test`, nie tylko "wygląda dobrze".

---

## 2️⃣ Hook: SQL migration bez rollbacku nie zostanie zapisana

### Problem, który to rozwiązuje

Migracja bazy danych bez zdefiniowanej ścieżki wycofania to standardowy incydent
produkcyjny w każdym zespole: coś idzie nie tak po deployu, a jedyny plan to "napiszmy
teraz, na szybko, jak to cofnąć". Da się to wymusić code review'em - ale code review
to kontrola *po fakcie*, kiedy plik już istnieje i ktoś już się przyzwyczaił do jego
kształtu.

### Co się zyskuje

Plik [`code/claude-hooks/check-sql-rollback.py`](code/claude-hooks/check-sql-rollback.py)
to **hook typu `PreToolUse`** - Claude Code wywołuje go automatycznie *przed* każdym
użyciem narzędzia `Write` albo `Edit` (konfiguracja wpięcia:
[`code/claude-hooks/settings.snippet.json`](code/claude-hooks/settings.snippet.json)).
Hook dostaje na `stdin` JSON z opisem operacji (jaki plik, jaka treść) i decyduje kodem
wyjścia: `exit 0` - operacja przechodzi, `exit 2` - operacja jest **zablokowana**, a
komunikat na `stderr` wraca do samego Claude jako informacja zwrotna, więc model widzi
*dlaczego* i może od razu dopisać brakującą sekcję, bez pytania człowieka.

Konkretnie: jeśli ścieżka pliku zawiera `/migrations/` i kończy się na `.sql`, a treść
nie zawiera znacznika `-- ROLLBACK`, zapis jest odrzucany. To przesuwa kontrolę z "code
review złapie to później" na "fizycznie nie da się zapisać migracji bez rollbacku w
ogóle" - niezależnie od tego, czy piszesz ją ręcznie z pomocą Claude Code, czy Claude
Code robi to autonomicznie w ramach większego zadania. Zysk nie jest w czasie, tylko w
jakości/bezpieczeństwie: klasa błędów ("zapomniałem o rollbacku") znika strukturalnie,
zamiast zależeć od czujności reviewera.

---

## 3️⃣ Skill: code-review komponentu Angular pod jedną komendą

### Problem, który to rozwiązuje

Angular ma swój własny zestaw powtarzających się błędów w PR-ach: brak
`ChangeDetectionStrategy.OnPush`, subskrypcje RxJS bez sprzątania (`takeUntilDestroyed`),
zagnieżdżone `.subscribe()`, `*ngFor`/`@for` bez `trackBy`. Każdy .NET dev, który
dotyka też frontendu, zna te problemy z nazwy, ale nie zawsze pamięta o nich przy
każdym review - a lista rzeczy do sprawdzenia w głowie ma tendencję do kurczenia się
pod presją czasu.

### Co się zyskuje

Plik [`code/claude-skills/angular-component-review/SKILL.md`](code/claude-skills/angular-component-review/SKILL.md)
to skill - w projekcie docelowym ląduje jako
`.claude/skills/angular-component-review/SKILL.md`. W przeciwieństwie do slash
commanda (wywoływanego jawnie), skill ma pole `description`, które Claude Code
przeszukuje **automatycznie** - gdy poprosisz "zrób review tego komponentu Angular"
albo otworzysz diff `*.component.ts`, model sam decyduje, że warto go użyć, i
stosuje zaszytą w nim checklistę (change detection, subskrypcje, standalone,
signals vs RxJS, template, dostępność) zamiast improwizować za każdym razem inny
zestaw uwag. Wymuszony jest też **format odpowiedzi** - tabela `Plik:linia | Kategoria
| Problem | Poprawka` - więc wynik nadaje się od razu do wklejenia w komentarz PR-a,
bez przepisywania. Zysk: spójność review między osobami i między dniami - dokładnie
ta sama checklista jest stosowana za pierwszym i za setnym razem, nie zależy od tego,
czy akurat ktoś jest zmęczony pod koniec dnia.

---

## 📎 Jak zweryfikować kod z tego wydania

Slash command i skill to pliki instrukcji dla Claude Code - nie da się ich "uruchomić"
bez samego Claude Code, więc zweryfikowano ich poprawność strukturalną (frontmatter
YAML, wymagane klucze) skryptem [`code/validate.py`](code/validate.py). Hook natomiast
jest zwykłym skryptem Pythona - **uruchomiono go naprawdę**, na czterech przykładowych
wywołaniach (`Write`/`Edit`, z rollbackiem i bez, migracja i nie-migracja). Pełne
komendy i prawdziwy output: [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #1 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
