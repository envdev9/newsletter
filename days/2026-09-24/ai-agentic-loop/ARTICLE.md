<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #1 — 24 września 2026

![AI/Claude Code](https://img.shields.io/badge/AI_%2F_Claude_Code-D97757?style=for-the-badge&logo=anthropic&logoColor=white)

## Agenci, skille, komendy, hooki - jak to się w ogóle ze sobą łączy

</div>

---

> _"Model nie 'wie', że uruchamia hook. On po prostu prosi o wykonanie narzędzia - a to,
> że ktoś po drodze podsłuchał to żądanie, zablokował je albo dopisał do logu, dzieje się
> całkowicie poza jego świadomością."_

Cztery mechanizmy - subagenci, skille, komendy, hooki - brzmią jak cztery niezależne
funkcje do nauczenia się osobno. Nie są. To **jeden mechanizm** (pętla tool-use) plus
**trzy sposoby, żeby do niej coś dopisać**, każdy uruchamiany przez kogoś innego (user /
model / harness) w innym momencie. Dziś rozkładamy to na czynniki pierwsze - łącznie z
działającym hookiem, który realnie blokuje niebezpieczne komendy, sprawdzonym na żywo.

---

## 1️⃣ Baza: co to w ogóle jest "pętla agentowa"

Claude Code (i każdy inny "agent" oparty o LLM z narzędziami) działa w prostej pętli:

1. Model dostaje kontekst (system prompt + historia + definicje dostępnych narzędzi).
2. Model albo zwraca czysty tekst (koniec tury), albo prosi o wykonanie jednego lub
   więcej narzędzi (`tool_use` w odpowiedzi API).
3. Harness (czyli sam Claude Code, nie model) **faktycznie wykonuje** te narzędzia -
   model nigdy nie dotyka dysku ani sieci bezpośrednio, tylko prosi "wykonaj `Bash` z
   command=...".
4. Wynik wraca do kontekstu jako `tool_result` i pętla wraca do punktu 2 - model widzi
   wynik i decyduje, co dalej.

To wszystko. Cała "inteligencja" agenta to nic innego niż wielokrotne powtórzenie kroków
2-4, aż model uzna, że nie potrzebuje już żadnego narzędzia. Subagenci, skille, komendy i
hooki nie zmieniają tej pętli - **dopisują się do niej w konkretnych punktach**.

---

## 2️⃣ Cztery mechanizmy - i KTO je uruchamia

Kluczowe pytanie, które odróżnia te cztery rzeczy od siebie, brzmi: **kto podejmuje
decyzję o ich użyciu?**

### 🧑 Komendy (slash commands) - decyduje **user**

Plik `.md` w `.claude/commands/` (albo `~/.claude/commands/` dla komend osobistych).
Użytkownik jawnie wpisuje `/nazwa-komendy argumenty` - treść pliku podmienia się w
prompt (z podstawieniem `$1`, `$2`, `$ARGUMENTS`, `@plik` na zawartość pliku, `` !`cmd` ``
na wynik komendy bash). To **skrót klawiszowy na prompt**, nic więcej - nie ma żadnej
"inteligencji" wykrywającej, kiedy komenda powinna się uruchomić, bo user decyduje o tym
ręcznie, pisząc `/`.

### 🤖 Skille - decyduje **model**, na podstawie opisu

Plik `SKILL.md` w `.claude/skills/<nazwa>/`. W przeciwieństwie do komend, skilli **user
nie wywołuje z nazwy** (chociaż może, pisząc np. `/nazwa-skilla` jeśli klient to
wspiera) - zamiast tego **metadata skilla (samo `name` + `description`, ok. 100 słów)
siedzi cały czas w kontekście modelu**, a model sam decyduje, czy pasuje do aktualnego
zadania. Jeśli tak - dopiero wtedy ładuje się pełna treść `SKILL.md` (i ewentualnie
pliki z `references/`, `scripts/`, `assets/`) - to jest właśnie "progressive disclosure":
nie płacisz kontekstem za skille, których akurat nie używasz, tylko za ich krótkie opisy.
Część skilli (jak np. `docs-writer` czy `code-review` widoczne w tym repo) faktycznie
uruchamia się jako **osobny subagent w tle** i wraca z gotowym wynikiem - więc skill i
subagent to nie są wykluczające się kategorie, skill może być "opakowaniem", które
deleguje dalej.

### 🧵 Subagenci - decyduje **model**, przez wywołanie narzędzia

Plik `.md` w `.claude/agents/<nazwa>.md` z frontmatterem (`name`, `description`, `model`,
`tools`). Model **wywołuje subagenta dokładnie tak samo, jak wywołuje każde inne
narzędzie** (`Agent`/`Task`) - to znaczy: ten sam `PreToolUse`/`PostToolUse` co dla
`Bash` czy `Write` też tu zadziała. Różnica jest w tym, co się dzieje **w środku**:
subagent dostaje **własny, świeży kontekst** (nie widzi historii rozmowy głównego
agenta - widzi tylko to, co dostał w promptcie zlecenia), uruchamia **własną, zagnieżdżoną
pętlę tool-use** (własne wywołania narzędzi, własne `PreToolUse`/`PostToolUse`), i kiedy
kończy pracę, jego **finalna wiadomość tekstowa** wraca do głównego agenta jako
`tool_result` wywołania `Agent`. Cała "bebechowa" praca subagenta (dziesiątki wywołań
`Grep`, `Read`, próby i błędy) **nigdy nie trafia do kontekstu głównego agenta** - to
jest najważniejszy mechanizm ochrony kontekstu głównej rozmowy (więcej o tym w dzisiejszej
rubryce 🧠 [AI - zarządzanie kontekstem](../ai-context/ARTICLE.md)).

Subagent kończy swoją turę przez `SubagentStop` (odpowiednik `Stop` głównego agenta) - i
tak jak `Stop`, `SubagentStop` może go "zawrócić" ("jeszcze nie skończyłeś, testy nie
przeszły") zamiast pozwolić mu zakończyć.

### 🪝 Hooki - decyduje **harness**, deterministycznie

Konfiguracja w `.claude/settings.json` (albo `hooks/hooks.json` w pluginie). To jedyny z
czterech mechanizmów, którego **model nie wybiera i nie widzi z wyprzedzeniem**. Hook
odpala się **zawsze**, kiedy nadejdzie jego zdarzenie (np. `PreToolUse` dla narzędzia
pasującego do `matcher`) - niezależnie od tego, czy model "chciałby", żeby się odpalił.
To czyni hooki jedynym miejscem, w którym można **naprawdę wymusić** politykę (np. "nigdy
nie pushuj force na main"), bo nie polega to na tym, że model się do czegoś zastosuje -
polega na tym, że proces w ogóle nie dostanie szansy się wykonać.

Hook to **skrypt** (`type: "command"` - bash/python/cokolwiek wykonywalnego) albo
**prompt** (`type: "prompt"` - osobne zapytanie do LLM z pytaniem "czy to bezpieczne?").
Skrypty są deterministyczne i szybkie (dobre do twardych reguł), prompty rozumieją
kontekst i niuanse (dobre do "oceń, czy to wygląda podejrzanie"), kosztem czasu i
przewidywalności.

---

## 3️⃣ Kolejność wykonania - dokładny przebieg jednej tury

Rozpiszmy to krok po kroku, tak jak faktycznie się dzieje, gdy model chce wykonać jedno
wywołanie narzędzia `Bash`:

```
Użytkownik wysyła prompt
        │
        ▼
  UserPromptSubmit hook   ← harness, przed pokazaniem promptu modelowi
  (może dopisać kontekst, może zablokować cały prompt)
        │
        ▼
   Model dostaje kontekst, generuje odpowiedź
        │
        ├── model zwraca czysty tekst ──────────────► Stop hook ──► koniec tury
        │                                              (może kazać kontynuować)
        │
        └── model prosi o wywołanie narzędzia (np. Bash)
                    │
                    ▼
            PreToolUse hook(i)          ← harness, PRZED wykonaniem
            (mogą: allow / deny / ask / zmodyfikować tool_input)
                    │
          ┌─────────┴─────────┐
          │ deny (exit 2)     │ allow (exit 0 / brak hooka)
          ▼                   ▼
   model dostaje         narzędzie się WYKONUJE
   powód odmowy                    │
   (bez uruchomienia)              ▼
                          PostToolUse hook(i)   ← harness, PO wykonaniu
                          (mogą dodać feedback, logować, nic nie blokują
                           samego już-wykonanego narzędzia)
                                    │
                                    ▼
                          tool_result trafia do kontekstu
                                    │
                                    ▼
                          pętla wraca do modelu (krok wyżej)
```

**Kluczowy szczegół:** `PreToolUse` i `PostToolUse` to punkty w cyklu życia **pojedynczego
wywołania narzędzia**, nie całej tury. Jeśli w jednej turze model wywoła 5 narzędzi
(równolegle albo po kolei), każde z nich osobno przechodzi przez swój własny
`PreToolUse → wykonanie → PostToolUse`. Hooki pasujące do tego samego zdarzenia i
matchera wykonują się **równolegle względem siebie i nie widzą nawzajem swojego wyjścia**
- projektuj je tak, żeby były niezależne.

**Zagnieżdżenie subagenta w tym diagramie:** wywołanie narzędzia `Agent` (uruchomienie
subagenta) przechodzi przez `PreToolUse`/`PostToolUse` **głównego** kontekstu jak każde
inne narzędzie. Ale w środku, między jego własnym `PreToolUse` a `PostToolUse`, subagent
odpala **cały powyższy diagram jeszcze raz, od zera, dla siebie** - własne wywołania
narzędzi, własne hooki na nie, i własny `SubagentStop` zamiast `Stop`. Główny kontekst
widzi to wszystko jako jedno zdarzenie: "narzędzie `Agent` się wykonało, oto wynik".

---

## 4️⃣ Kiedy skill, kiedy komenda, kiedy subagent, kiedy hook

| Chcesz... | Użyj |
|---|---|
| Użytkownik ma jawnie, z klawiatury, wywoływać dokładnie tę operację | **Komenda** (`/nazwa`) |
| Model ma **sam rozpoznać**, że dana wiedza/procedura jest tu potrzebna, bez pytania usera | **Skill** |
| Odizolować hałaśliwą, wieloetapową robotę (dużo eksploracji, mało wniosku) od głównej rozmowy | **Subagent** |
| Wymusić twardą regułę, której model **nie może** obejść, nawet jeśli "zapomni" albo się pomyli | **Hook** (`PreToolUse` z `deny`) |
| Zareagować na coś **po fakcie** (zalogować, odpalić formatter, powiadomić) bez wpływu na decyzję modelu | **Hook** (`PostToolUse`) |

Skille i komendy często się mylą, bo oba to pliki Markdown z frontmatterem - różnica jest
wyłącznie w tym, **kto naciska spust**. Komenda = user mówi "zrób X teraz". Skill = model
sam wie, że akurat teraz potrzebuje wiedzieć, jak się robi X.

---

## 5️⃣ Działający przykład: hook, który naprawdę blokuje

W [`code/hooks/`](code/hooks/) są dwa hooki, oba realnie przetestowane (patrz
[`code/README.md`](code/README.md) po dokładne komendy i prawdziwy output):

- **`pretooluse_guard.sh`** - `PreToolUse` na narzędzie `Bash`. Sprawdza komendę wzorcami
  (rekurencyjne `rm -rf` na `/` lub `~`, operacje na urządzeniach blokowych, `git push
  --force` na `main`/`master`, `curl|bash`). Jeśli któryś pasuje - drukuje JSON z decyzją
  `deny` na `stderr` i kończy się kodem **2** (kontrakt Claude Code: exit 2 = zablokuj,
  pokaż modelowi treść stderr jako powód). W przeciwnym razie exit **0** = zezwól.
- **`posttooluse_logger.sh`** - `PostToolUse` na dowolne narzędzie (`matcher: "*"`).
  Dopisuje jeden wiersz audytu do pliku logu z każdym zakończonym wywołaniem narzędzia -
  demonstruje, że `PostToolUse` widzi już **wynik** narzędzia (`tool_result`), czego
  `PreToolUse` jeszcze nie widzi (bo narzędzie jeszcze się nie wykonało).

Oba przetestowane bezpośrednio z linii poleceń, podając im na `stdin` dokładnie taki JSON,
jaki faktycznie wysyła Claude Code - pełne komendy i prawdziwe wyjście w
[`code/README.md`](code/README.md).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) - dokładne komendy i prawdziwy, uruchomiony output
obu hooków.

---

<div align="center">

[← wróć do wydania #1 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
