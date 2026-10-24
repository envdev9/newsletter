<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #2 — 25 września 2026

![AI/Agentic loop](https://img.shields.io/badge/AI_%2F_Agentic_loop-5A67D8?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-%C5%9Brednio%20zaawansowany-orange?style=for-the-badge)
![Zweryfikowane](https://img.shields.io/badge/skrypty-7%2F7%20przypadk%C3%B3w-brightgreen?style=for-the-badge)

## Drzwi wejściowe i wyjściowe pętli: `UserPromptSubmit`, `Stop`, `SubagentStop` — i co, gdy hooków jest kilka

</div>

---

> _"`PreToolUse` pilnuje pojedynczego kroku. `Stop` pilnuje tego, czy w ogóle wolno
> Ci skończyć. To różnica między kontrolą biletów a kontrolą wyjścia z lotniska."_

Wczoraj ([#1](../../2026-09-24/ai-agentic-loop/ARTICLE.md)) rozłożyliśmy pętlę i jej
punkty wpięcia na czynniki pierwsze, ale hooki, które testowaliśmy, siedziały **w środku**
tury (`PreToolUse`/`PostToolUse`). Dziś **brzegi**: co dzieje się, zanim model w ogóle
zobaczy prompt, i co, zanim wolno mu oddać sterowanie. Do tego trzy rzeczy, o które
pytacie najczęściej: jak **napisać skill od zera**, jak działa **kilka hooków na jednym
evencie** i czego **nie** wolno zakładać. Kod: [`code/`](code/).

---

## 1️⃣ 🚪 `UserPromptSubmit` — zanim model cokolwiek zobaczy

### 🎯 Dlaczego to ważne

To jedyny hook, który widzi Twój prompt **surowy**, przed modelem. Można tu zrobić dwie
zupełnie różne rzeczy: **odrzucić** prompt (np. bo wkleiłeś do niego hasło do bazy — które
inaczej poleciałoby do API i zostało w transkrypcie na dysku) albo **dokleić kontekst**,
którego model nie ma (data, branch, przypomnienie o zasadach). Instrukcja w `CLAUDE.md` jest
statyczna; ten hook potrafi być *dynamiczny*.

### Kontrakt (wg dokumentacji, z pamięci — patrz ramka niepewności niżej)

- stdin: JSON ze wspólnymi polami (`session_id`, `transcript_path`, `cwd`,
  `hook_event_name`, …) plus **`prompt`**.
- **exit 0 + stdout** → tekst ze stdout jest **dopisywany do kontekstu** modelu (to wyjątek:
  przy większości eventów stdout przy exit 0 widzi tylko człowiek w trybie verbose).
- **exit 2** → prompt jest **odrzucony i wymazany**; **stderr widzi użytkownik**, model nie
  dostaje niczego. (Kontrast z `PreToolUse`, gdzie stderr trafia do *modelu*.)
- Alternatywa: JSON na stdout (`{"decision":"block","reason":...}` albo
  `hookSpecificOutput.additionalContext`) przy exit 0.

### ▶️ Prawdziwy przebieg

Dwa hooki: [`ups_secret_guard.py`](code/hooks/ups_secret_guard.py) (regexy: klucz AWS,
PEM, token GitHub, `password=...`) i [`ups_context.py`](code/hooks/ups_context.py) (data +
przypomnienie o skillu, gdy prompt mówi o migracji). Wejście `Polacz sie z baza,
password=Sup3rTajne123 i sprawdz migracje`:

```
### UserPromptSubmit: haslo w prompcie -> guard blokuje
    exit  : 2 (oczekiwano 2) OK
    stderr: Prompt odrzucony: wykryto haslo w postaci jawnej. Usun sekret z promptu (podaj nazwe zmiennej srodowiskowej zamiast wartosci) i wyslij ponownie.
```

Zwróć uwagę: komunikat **nie powtarza sekretu** (trafiłby do logów/terminala). Czysty
prompt o migracji → guard: exit 0 w ciszy; `ups_context.py`: exit 0 i na stdout:

```
[hook] Dzisiejsza data: 2026-09-25
[hook] Zadanie dotyczy migracji: przed zmiana uzyj skilla ef-migration-review i nie edytuj wygenerowanych plikow *.Designer.cs.
```

> 💡 **Haczyk dla .NET-owca:** stdout doklejony przez hook to *zwykły tekst w kontekście* —
> model nie odróżni go od Twoich słów (chyba że sam się podpiszesz prefiksem, jak `[hook]`
> wyżej; polecam). Każdy bajt kosztuje tokeny **przy każdej turze**, więc doklejaj
> krótko: datę tak, cały `git status` — nie.

---

## 2️⃣ 🛑 `Stop` i `SubagentStop` — "nie skończysz, dopóki testy są czerwone"

### 🎯 Dlaczego to ważne

Najczęstsza wada agentów: **ogłaszają sukces bez sprawdzenia**. "Gotowe, wszystko działa"
— a testy nie były odpalane. Instrukcją tego nie wyleczysz. `Stop` odpala się w momencie,
gdy model *chce oddać sterowanie*; hook może powiedzieć: **nie, wróć do pracy**, i podać
powód, który model dostaje jak nową instrukcję. To zamienia "prośbę o testy" w bramkę
jakości, której nie da się pominąć. `SubagentStop` robi to samo dla subagenta — ważne,
bo subagent zwraca wynik do głównego agenta, który zwykle mu ufa.

### Mechanizm

[`stop_gate.py`](code/hooks/stop_gate.py) uruchamia `python3 -m unittest discover -s <katalog>`
(u Ciebie: `dotnet test`). Zielone → cisza, exit 0 → agent kończy. Czerwone → na stdout JSON
`{"decision":"block","reason":"..."}` z ogonem wyniku testów → agent **nie kończy**,
`reason` wraca do niego, naprawia, próbuje skończyć ponownie.

Uwaga na pętlę: skoro hook może zawracać agenta, a agent może znów nie umieć naprawić,
grozi **nieskończona pętla**. Stąd pole **`stop_hook_active`** w stdin — `true` oznacza
"ten stop już raz został przez hook zawrócony". Nasz skrypt wtedy przepuszcza. To
konwencja, którą polecam kopiować zawsze; bez niej jedna czerwona flaky-asercja pali tokeny
w nieskończoność.

### ▶️ Prawdziwy przebieg

```
### Stop: testy czerwone -> decision=block
    exit  : 0 (oczekiwano 0) OK
    stdout: {"decision": "block", "reason": "[Stop] Testy sa czerwone - nie konczysz. Napraw i uruchom ponownie:\n=====...\nFAIL: test_add (test_calc.CalcTests)\n...\nAssertionError: 4 != 5\n...FAILED (failures=1)"}

### Stop: testy czerwone, ale stop_hook_active=true -> przepuszcza
    stdout: stop_gate: stop_hook_active=true - przepuszczam (bezpiecznik przed petla)

### Stop: testy zielone -> cicho, przepuszcza
    exit  : 0 (oczekiwano 0) OK

### SubagentStop: testy czerwone -> decision=block
    stdout: {"decision": "block", "reason": "[SubagentStop] Testy sa czerwone - nie konczysz. ..."}
```

Ten sam skrypt obsługuje oba eventy (różni je tylko `hook_event_name` w komunikacie).
Alternatywa dla decyzji w JSON: **exit 2 + stderr** też blokuje zatrzymanie (stderr → model).

> ⚠️ **Nie zweryfikowałem** w żywej sesji, że model po `decision: block` faktycznie wznawia
> pracę i jak dokładnie formułuje to interfejs — sprawdzałem tylko kontrakt wejście/wyjście
> skryptu. Również: nie wiem, które inne pola (poza `stop_hook_active`) niesie
> `SubagentStop` — skrypt świadomie czyta tylko `stop_hook_active` i `hook_event_name`.

---

## 3️⃣ 🧩 Kilka hooków na jednym evencie — kompozycja

To część, w której intuicja z programowania ("middleware, jeden po drugim") **myli**.

### Zasady (wg dokumentacji — z pamięci)

| Kwestia | Co wiem | Konsekwencja dla projektu |
|---|---|---|
| **Równoległość** | Wszystkie pasujące hooki dla eventu startują **równolegle** | Hook B **nie widzi** wyniku hooka A. Nie buduj łańcucha "A przygotowuje dane dla B" |
| **Kolejność** | Nie jest kontraktem | Nie licz na to, że guard zadziała "przed" kontekstem |
| **Blokada** | Wystarczy **jeden** hook z exit 2 / `decision: block`, żeby zablokować | To "OR" na blokadach: najostrożniejszy wygrywa |
| **Czas** | Ściana ≈ najwolniejszy hook, nie suma | Dokładaj hooki taniej niż intuicja podpowiada |
| **Duplikaty** | Identyczne polecenia są (wg dok.) deduplikowane | Nie licz na to, że dwa razy ten sam wpis policzy dwa razy |
| **Timeout** | Każdy hook ma limit czasu (domyślny — sprawdź w dokumentacji swojej wersji) | Wolny hook = opóźnienie *każdego* promptu/kroku |

Dokładne reguły łączenia bardziej wymyślnych decyzji (np. `allow` z jednego hooka `PreToolUse`
kontra `ask` z drugiego, wielokrotne `additionalContext`) **pamiętam niepewnie** —
nie opisuję ich jako faktu. Kto chce na tym polegać, niech sprawdzi w dokumentacji swojej
wersji albo... zmierzy.

### 🔬 Symulator, nie harness

Do zilustrowania skutków napisałem [`run_hooks.py`](code/run_hooks.py): odpala hooki
równolegle w `ThreadPoolExecutor`, podaje ten sam JSON i łączy wyniki wg zasad z tabeli.
**To symulacja mojego rozumienia kontraktu, nie dowód, że Claude Code robi identycznie.**
Pokazuje jednak konsekwencje:

**Prompt czysty, oba hooki z sztucznym opóźnieniem 1 s:**

```
- ...ups_secret_guard.py
    exit=0 czas=1.05s
- ...ups_context.py
    exit=0 czas=1.05s
    stdout: [hook] Dzisiejsza data: 2026-09-25 ...

CZAS scienny: 1.05s (suma czasow hookow: 2.10s)
WYNIK POLACZONY: PRZEPUSZCZONE
  kontekst do modelu: '[hook] Dzisiejsza data: 2026-09-25\n[hook] Zadanie dotyczy migracji: ...'
```

**Prompt z hasłem** — guard blokuje, ale `ups_context.py` *też się wykonał* (kosztował czas i
mógłby mieć skutki uboczne):

```
- ...ups_secret_guard.py   exit=2 czas=1.05s
- ...ups_context.py        exit=0 czas=1.05s  (stdout: kontekst...)
CZAS scienny: 1.05s (suma czasow hookow: 2.10s)
WYNIK POLACZONY: BLOK
```

### Trzy wnioski projektowe

1. **Hooki bez skutków ubocznych albo idempotentne.** Skoro równoległość, to guard nie
   "chroni" przed odpaleniem drugiego hooka — obaj wystartowali. Jeśli `ups_context.py`
   zapisywałby cokolwiek na dysk albo strzelał do sieci, zrobiłby to także dla odrzuconego
   promptu.
2. **Jedna odpowiedzialność na hook** + **jeden wspólny bezpiecznik**. Dwa hooki `Stop`
   (np. testy i lint) zawrócą agenta *oba naraz*, każdy ze swoim `reason` — model dostanie
   (wg zasady "OR") powody do naprawy; projektuj komunikaty tak, żeby się nie wykluczały.
   Każdy musi sam respektować `stop_hook_active`.
3. **Kolejność wymusza się w jednym skrypcie**, nie w konfiguracji. Chcesz "najpierw walidacja,
   potem dokładka" — zrób z tego jeden hook-orkiestrator (jak `run_hooks.py`, tylko
   sekwencyjnie). To jedyny sposób na deterministyczną kolejność.

Analogia dla .NET-owca: to nie `IMiddleware` w pipeline, tylko `Task.WhenAll` na handlerach
tego samego zdarzenia — bez wspólnego stanu i bez gwarancji kolejności zakończenia.

Ostatni przypadek z symulatora — dwa hooki `Stop`, jeden na czerwonym, drugi na zielonym
zestawie testów: wystarczy jeden `block`, wynik łączny = **BLOK** (czas ściany 0.15 s, suma
0.29 s).

---

## 4️⃣ 🧙 Własny skill od zera — `changelog-entry`

### 🎯 Dlaczego to ważne

Skill to najtańszy sposób, żeby *nauczyć* agenta procedury, której nie zna: nie płacisz
kontekstem, dopóki nie jest potrzebna (w kontekście siedzi tylko `name` + `description`).
Ale skill napisany "na oko" się **nie aktywuje** albo aktywuje w złych momentach. Poniżej
kolejność, którą polecam.

### Krok po kroku

**1. Wybierz zadanie z częścią deterministyczną.** Changelog z commitów: grupowanie po
typie to fakty (skrypt), redakcja zdań to osąd (model). Tę samą zasadę "fakty przed osądem"
pokazywał wczorajszy skill do migracji EF.

**2. Katalog i frontmatter** ([`SKILL.md`](code/skills/changelog-entry/SKILL.md)):

```yaml
---
name: changelog-entry
description: Generuje wpis do CHANGELOG.md (format Keep a Changelog) z listy commitow ... Uzyj, gdy ktos prosi o changelog, release notes, notatki do wydania albo pyta "co weszlo od ostatniego taga".
allowed-tools: Read, Edit, Bash(git log *), Bash(git describe *), Bash(python3 *group_commits.py*)
---
```

- **`description` jest mechanizmem aktywacji.** Model widzi *tylko to*, gdy decyduje, czy
  skill pasuje. Musi mówić **co** robi i **kiedy** go użyć, słowami, którymi ludzie faktycznie
  proszą ("release notes", "co weszło od taga"). Opis w stylu "Helper do changelogów" nie
  aktywuje się nigdy.
- `name` = nazwa katalogu.
- `allowed-tools` zawęża uprawnienia na czas skilla (wąskie wzorce `Bash(...)` zamiast gołego
  `Bash`). Semantykę wzorców i to, czy pole działa w każdym kliencie, traktuję jako
  niezweryfikowane.

**3. Treść = instrukcja dla modelu, nie dokumentacja dla człowieka.** Numerowane kroki,
dokładne komendy, jasny podział "to robi skrypt / to robisz Ty", format wyniku.

**4. Skrypt obok** ([`group_commits.py`](code/skills/changelog-entry/group_commits.py)),
bez zależności, z sensownymi kodami wyjścia (3 = brak commitów).

**5. Przetestuj skrypt i zlintuj skill** — dwie rzeczy, które da się zweryfikować offline.

### ▶️ Prawdziwy przebieg

Lint ([`validate_skill.py`](code/validate_skill.py): frontmatter, pola, "kiedy użyć" w
opisie, istnienie wspomnianych skryptów):

```
$ python3 validate_skill.py skills/changelog-entry
OK: changelog-entry (opis: 216 znakow)
```

Skrypt na 6 commitach z [`commits.txt`](code/skills/changelog-entry/test-fixtures/commits.txt):

```
## [1.4.0] - 2026-09-25

### Breaking
- **auth**: usun stary endpoint /login

### Added
- **orders**: dodaj filtrowanie po statusie
- **auth**: usun stary endpoint /login

### Fixed
- **api**: napraw NullReference przy pustym koszyku

### Changed
- wydziel OrderMapper

### Other
- Poprawki po review
- aktualizacja zaleznosci
```

Zauważ dwie decyzje: commit z `!` (`feat(auth)!:`) trafia **i** do *Breaking*, **i** do
*Added*; a commit niezgodny z konwencją ("Poprawki po review") ląduje w *Other* zamiast być
zgadywanym — skill każe go przejrzeć ręcznie. Skrypt **nie zgaduje**, model ma redagować.

### Czego skill NIE gwarantuje

Nie mam możliwości sprawdzić z poziomu tej sesji, czy Claude Code **sam wybierze** ten skill
po Twoim "zrób release notes". To zależy od klienta i modelu. Jedyne, co zmierzyłem: skill
jest poprawnie sformułowany, a skrypt działa. Sprawdź u siebie w praktyce: napisz "przygotuj
release notes" i zobacz, czy skill się załaduje — jeśli nie, poprawiaj `description`, nie
treść.

---

## 5️⃣ Całość w jednym kadrze

```
prompt ─► [UserPromptSubmit: guard ∥ kontekst]  ── exit 2 ──► prompt wymazany (stderr → Ty)
                       │ przepuszczone (+ stdout → kontekst)
                       ▼
                     model ⇄ narzędzia (PreToolUse/PostToolUse, wydanie #1)
                       │ "koniec"
                       ▼
        [Stop: testy ∥ lint]  ── decision:block ──► wraca do modelu (reason = nowa instrukcja)
                       │ (stop_hook_active chroni przed pętlą)
                       ▼
                  tura skończona        (subagent: to samo, ale SubagentStop)
```

`∥` = równolegle, bez wspólnego stanu.

---

## 📎 Co zweryfikowano, a czego nie

| ✅ Uruchomione naprawdę | ⚠️ Niezweryfikowane |
|---|---|
| 3 skrypty hooków w 7 przypadkach z JSON-em na stdin, 7/7 zgodnych z oczekiwanym exit code (`demo_hooks.py`) | Wpięcie w żywej sesji Claude Code i zachowanie modelu po `block`/exit 2 |
| Bezpiecznik `stop_hook_active`, ten sam skrypt jako `Stop` i `SubagentStop` | Pełny zestaw pól `SubagentStop` i kształt payloadu w Twojej wersji (fixtury zgodne z moją pamięcią kontraktu) |
| Równoległość i łączenie wyników **w symulatorze** (1.05 s vs 2.10 s sumy) | Że prawdziwy harness łączy decyzje dokładnie jak symulator; reguły dla sprzecznych `allow`/`ask`/`additionalContext` |
| Skrypt skilla na 6 commitach, lint skilla | Samoczynna aktywacja skilla, działanie `allowed-tools` w Twoim kliencie |

Nie mogłem zajrzeć do dokumentacji online (brak uprawnień do pobierania stron) — opis
kontraktu pochodzi z pamięci i wcześniejszego wydania; kluczowe pola sprawdź w
dokumentacji hooków Claude Code przed wdrożeniem. Środowisko: Python 3.10.4, kod bez zależności.

---

<div align="center">

[← wróć do wydania #2 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
