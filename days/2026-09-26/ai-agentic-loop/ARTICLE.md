<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #3 — 26 września 2026

![AI/Agentic loop](https://img.shields.io/badge/AI_%2F_Agentic_loop-5A67D8?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Zweryfikowane](https://img.shields.io/badge/skrypty-7%2F7%20%2B%20p%C4%99tla-brightgreen?style=for-the-badge)
![Claude CLI](https://img.shields.io/badge/claude%20CLI-niedost%C4%99pne-lightgrey?style=for-the-badge)

## Własny subagent, pętla z weryfikacją i hooki, które przeżywają kompaktowanie

</div>

---

> _"Agent, który sam ocenia własną pracę, to student, który sam wystawia sobie ocenę.
> Zmień egzaminatora na `exit code`."_

Dwa wydania temu rozebraliśmy pętlę, wczoraj jej „drzwi” (`UserPromptSubmit`, `Stop`). Dziś
trzy rzeczy, które zamieniają zabawkę w narzędzie do codziennej pracy: **własny subagent**
(plik `.md` z ograniczonymi uprawnieniami), **pętla z weryfikacją** (kto naprawdę decyduje, że
zadanie jest skończone) i **hooki `PreCompact`/`SessionStart`** (jak nie zgubić stanu, gdy
kontekst się kompaktuje). Kod: [`code/`](code/).

> ⚠️ **Uczciwie na starcie:** próba uruchomienia `claude --version` została w tym środowisku
> **odrzucona** przez uprawnienia, więc **żadna** część tego artykułu nie była testowana w żywej
> sesji Claude Code. Zweryfikowałem to, co da się lokalnie (lint plików agentów, mechanikę pętli,
> skrypty hooków na JSON-ie ze stdin). Nazwy pól i flag pochodzą z pamięci — patrz tabela na końcu.

---

## 1️⃣ 🤖 Własny subagent — plik, który jest „pracownikiem”

### 🎯 Dlaczego to ważne

Dwa problemy, które rozwiązuje jeden mechanizm. Po pierwsze **kontekst**: gdy główny agent sam
przegląda 40 plików, każdy z nich zostaje w jego oknie do końca sesji i za każdym razem płacisz
za niego tokenami. Subagent robi to w **osobnym oknie**, a rodzicowi oddaje tylko końcową
odpowiedź (u nas: kilka linijek). Po drugie **uprawnienia**: reviewer nie potrzebuje `Edit`
ani `Bash`. Agent, który *nie może* zmodyfikować plików, nie zmodyfikuje ich nawet przy
najdziwniejszym prompt-injection z komentarza w kodzie. Bezpieczeństwo przez brak narzędzia
jest silniejsze niż przez prośbę w prompcie.

### Anatomia pliku

[`claude-agents/dotnet-reviewer.md`](code/claude-agents/dotnet-reviewer.md):

```markdown
---
name: dotnet-reviewer
description: Read-only code reviewer for C#/.NET changes. Use proactively after edits to .cs files, or when asked to "review", "check the diff" or "look for bugs" in .NET code. Returns a short list of findings with file:line; never modifies files.
tools: Read, Grep, Glob
model: sonnet
---

You are a strict but concise C#/.NET code reviewer working in an isolated context.
...
```

Cztery pola frontmattera (wg pamięci dokumentacji; ostatnie dwa opcjonalne):

| Pole | Rola | Pułapka |
|---|---|---|
| `name` | identyfikator, kebab-case | zgodność z nazwą pliku ułatwia życie |
| `description` | **mechanizm delegowania** — model głównego agenta czyta *tylko to*, żeby zdecydować „oddać temu agentowi czy zrobić samemu” | opis „Helps with code” nie zadziała nigdy |
| `tools` | lista dozwolonych narzędzi | **pominięte pole = agent dziedziczy WSZYSTKIE narzędzia rodzica**, w tym `Bash` i `Edit` |
| `model` | np. `sonnet`/`opus`/`haiku` lub odziedziczony | tani model do mechanicznych przeglądów to realna oszczędność |

Treść pod frontmatterem to **prompt systemowy** agenta. Ważny szczegół: agent nie widzi
rozmowy rodzica. Zna tylko to, co rodzic wpisał w zadaniu delegowania, plus swój prompt. Stąd
w naszym pliku pierwszy krok „zacznij od przeczytania plików, które wskazał rodzic”, i twardy
**format odpowiedzi** — rodzic dostaje *wyłącznie* ostatnią wiadomość agenta, więc to ona jest
całym „API” między nimi. Traktuj ją jak kontrakt zwracanego typu w C#: `path:line - problem - fix`
albo dokładnie `No findings.`

> 💡 **Analogia .NET:** subagent to metoda z własnym stosem wywołań, a `tools` to lista
> dozwolonych zależności wstrzykniętych do konstruktora. `description` to sygnatura, po której
> inni decydują, czy ją wywołać. Brak `tools` = wstrzyknięty cały `IServiceProvider`.

### Gdzie leży plik

Projektowo w `.claude/agents/*.md` (współdzielony przez git), osobiście w `~/.claude/agents/`.
Zapis do `.claude/` bywa w tym środowisku odrzucany, więc w repo agent leży w `claude-agents/`,
a README opisuje kopiowanie. Listę agentów sprawdzisz w sesji komendą `/agents` (niezweryfikowane).

### Lint — jedyne, co mogłem naprawdę sprawdzić

Skoro nie mogę zobaczyć, czy agent zostanie wybrany, sprawdzam to, co pod moją kontrolą
([`validate_agent.py`](code/validate_agent.py)): poprawny frontmatter, nazwa, opis mówiący **co
i kiedy**, literówki w `tools`, a z flagą `--read-only` — brak narzędzi zapisujących.

```
$ python3 validate_agent.py claude-agents/dotnet-reviewer.md --read-only
OK: dotnet-reviewer.md

$ python3 validate_agent.py claude-agents-bad/sloppy.md --read-only
WARN: nieznane narzedzie 'Reed' (literowka?)
WARN: tresc nie opisuje formatu odpowiedzi - rodzic dostanie wolny tekst
BLAD: name 'Sloppy Helper' musi byc kebab-case (male litery, cyfry, myslniki)
BLAD: description za krotki (15 zn.) - powiedz CO robi i KIEDY uzyc
BLAD: description nie mowi kiedy uzyc (brak 'use'/'when'/'after'...)
BLAD: agent ma byc read-only, a ma: Bash, Write
BLAD: tresc (prompt systemowy) za krotka - agent nie dostaje nic poza opisem
FAIL: sloppy.md (5 bledow)
```

Zwróć uwagę na `Reed` zamiast `Read`: literówka w `tools` w najgorszym wypadku po cichu
zostawia agenta *bez* narzędzia, którego chciałeś — a Ty nie dostaniesz żadnego błędu kompilacji.
Lint w CI to tani odpowiednik kompilatora dla plików konfiguracyjnych. (Lista „znanych narzędzi”
w skrypcie pochodzi z pamięci, dlatego nieznana nazwa to tylko ostrzeżenie.)

### Cztery zasady projektowania agenta

1. **Zawęź `tools` do minimum** — reviewer: `Read, Grep, Glob`. Agent do uruchamiania testów:
   dodaj `Bash`, ale (jeśli klient to wspiera) z wąskim wzorcem, nie gołym `Bash`.
2. **Jedno zadanie, jeden format wyniku.** „Zrób wszystko” to nie agent, to drugi rodzic.
3. **Opis pisz słowami, którymi prosisz** („review”, „check the diff”) i dopisz „proactively”,
   jeśli chcesz, by rodzic delegował bez wołania.
4. **Ogranicz wynik.** Cały zysk z izolacji ginie, jeśli agent zwraca 3000 tokenów prozy.
   Format „jedna linia na znalezisko” jest częścią projektu, nie kosmetyką.

> ⚠️ **Nie zmierzyłem** oszczędności kontekstu z izolacji (brak żywej sesji) — to wniosek z
> architektury, nie liczba. Nie zweryfikowałem też, czy `description` faktycznie wyzwala
> delegowanie w Twojej wersji.

---

## 2️⃣ 🔁 Pętla z weryfikacją — exit code jako egzaminator

### 🎯 Dlaczego to ważne

W wydaniu #2 bramka `Stop` zawracała agenta z czerwonymi testami. Tu ten sam pomysł, ale
**z zewnątrz**: skrypt (lub CI) uruchamia agenta w trybie nieinteraktywnym, sprawdza wynik
*własnym* weryfikatorem i, jeśli jest źle, uruchamia agenta jeszcze raz — z tekstem porażki.
Zaleta: weryfikator jest poza modelem, więc nie da się go „przekonać”. Wada: kosztuje kolejne
uruchomienie. Trzy elementy, bez których pętla jest niebezpieczna:

1. **Weryfikator o binarnym wyniku** (exit code testów, `dotnet build`, lint), nie „czy agent
   napisał, że działa”.
2. **Feedback = konkretny ogon błędu**, nie „spróbuj jeszcze raz”. Agent bez informacji powtórzy
   ten sam błąd.
3. **Twardy limit iteracji.** Bez niego jedna niemożliwa do spełnienia asercja pali tokeny bez końca
   (ten sam problem co `stop_hook_active`, tylko na zewnątrz).

### Mechanizm — [`verify_loop.py`](code/verify_loop.py)

```
kopia projektu → [ worker(FEEDBACK_FILE) → verify ] ── exit 0 ──► SUKCES
                        ▲                     │ exit ≠ 0
                        └── ogon błędu ───────┘   (max N razy, potem PORAZKA)
```

Petla pracuje na **kopii** projektu w katalogu tymczasowym (oryginał nietknięty),
worker dostaje poprzedni błąd w pliku z env `FEEDBACK_FILE`, a o wyniku decyduje wyłącznie
`returncode` weryfikatora.

### ⚠️ Kto tu jest „agentem”? Nikt.

Ponieważ `claude` nie był dostępny, w roli workera występuje
[`scripted_worker.py`](code/loop-demo/scripted_worker.py) — **zwykły skrypt**, nie model.
Celowo zachowuje się jak leniwy agent: bez feedbacku naprawia tylko `add`, dopiero po zobaczeniu
w feedbacku `test_sub` naprawia `sub`. To dowodzi mechaniki pętli (feedback faktycznie dociera do
workera, limit działa, sukces wg exit code), **nie** zdolności żadnego modelu.

### ▶️ Prawdziwy przebieg

```
$ python3 verify_loop.py --project loop-demo/project --max-iter 3 \
    --worker "python3 loop-demo/scripted_worker.py" --verify "python3 -m unittest -q"
=== iteracja 1/3
  worker: brak feedbacku -> naprawiam add (pierwsze co widze)
  weryfikacja: exit=1
  feedback dla nastepnej iteracji:
    ======================================================================
    FAIL: test_sub (test_calc.CalcTests)
    ...
    AssertionError: 8 != 2
    ...
    FAILED (failures=1)
=== iteracja 2/3
  worker: feedback wspomina test_sub -> naprawiam sub
  weryfikacja: exit=0
SUKCES po 2 iteracji(ach)
```

Ten sam zestaw z `--max-iter 1` kończy się `PORAZKA: limit 1 iteracji wyczerpany, testy dalej
czerwone` z exit 1 — i to jest **pożądane**: pętla ma umieć przyznać się do klęski, zamiast
udawać sukces. W CI ten exit 1 czerwieni build, zamiast wypuścić niezweryfikowaną zmianę.

### Podmiana workera na prawdziwego agenta

Do trybu headless Claude Code służy `claude -p "<prompt>"` (drukuje wynik i kończy). Z pamięci
znam flagi ograniczające pracę: `--max-turns` (limit tur), `--allowedTools` (whitelista narzędzi,
żeby nieinteraktywny agent nie zawisł na pytaniu o zgodę) i `--output-format json`. **Nie
uruchomiłem żadnej z nich** — sprawdź `claude --help` w swojej wersji. Integracja jest banalna:
`--worker` wskazuje skrypt-opakowanie, który dokleja zawartość `$FEEDBACK_FILE` do promptu.

> 💡 **Pułapka bezpieczeństwa:** pętla headless nie ma człowieka, który kliknie „nie”. Dlatego
> `allowedTools` ma być wąskie (`Read, Edit, Bash(dotnet test*)`), a katalog roboczy — kopią lub
> gałęzią, nie Twoim jedynym egzemplarzem repo. Dokładnie po to nasza pętla kopiuje projekt.

---

## 3️⃣ 🧠 `PreCompact` i `SessionStart` — stan, który przeżywa kompaktowanie

### 🎯 Dlaczego to ważne

Długa sesja w końcu zapełnia okno kontekstu. Wtedy (automatycznie albo na Twoje `/compact`)
historia jest zastępowana streszczeniem. Streszczenie jest stratne: lista „co zostało do zrobienia”,
zasady „tej migracji nie ruszamy” i decyzje z godziny 2 sesji mogą zniknąć albo się zniekształcić.
Rozwiązanie: **nie ufaj streszczeniu w rzeczach, które muszą być dokładne**. Trzymaj je w pliku
(`TASKS.md`), a hooki dopilnują, żeby po kompaktowaniu model *ten plik znów zobaczył*.

### Dwa hooki, jedna para

- **`PreCompact`** — odpala się tuż przed kompaktowaniem. Payload (z pamięci): `session_id`, `cwd`,
  `trigger` = `manual` | `auto`. [`precompact_snapshot.py`](code/hooks/precompact_snapshot.py)
  zapisuje na dysk kopię pliku zadań. Niczego nie wstrzykuje do kontekstu — po prostu **utrwala**.
  Zawsze kończy się `exit 0`: nieudany snapshot nie może blokować kompaktowania.
- **`SessionStart`** — odpala się na starcie/wznowieniu sesji, a (z pamięci) także po kompaktowaniu,
  z polem `source` = `startup` | `resume` | `clear` | `compact`. Jak w `UserPromptSubmit`, stdout
  przy exit 0 trafia do kontekstu. [`sessionstart_restore.py`](code/hooks/sessionstart_restore.py)
  dla `compact` wczytuje snapshot i drukuje go; dla `startup`/`resume` tylko datę; dla `clear`
  milczy (użytkownik chciał czystego kontekstu — nie wciskaj mu starego).

```
              PreCompact                       kompaktowanie              SessionStart(source=compact)
TASKS.md ──► claude-state/precompact-<id>.md ──► (historia → streszczenie) ──► stdout → kontekst
```

### ▶️ Prawdziwy przebieg

[`demo_hooks.py`](code/demo_hooks.py) odpala hooki na JSON-ach z `fixtures/` w katalogu tymczasowym:

```
### PreCompact (auto): zapisuje snapshot pliku zadan
    stderr: precompact_snapshot: zapisano precompact-abc-123.md (245 znakow)
### SessionStart (compact): stdout = odtworzony stan zadan
    stdout: [hook] Kontekst zostal skompaktowany. Stan zadan sprzed kompaktowania:
            ...
            - [ ] Naprawic N+1 w OrderRepository.GetWithLines  <- W TOKU
            ...
### SessionStart (compact) z MAX_CHARS=60: obciete
    stdout: ... # Zadania (pr
            [...obciete...]
### SessionStart (startup): tylko data
    stdout: [hook] Dzisiejsza data: 2026-09-26. Zrodlo sesji: startup.
### SessionStart (clear): cisza
### SessionStart (compact) bez snapshotu: komunikat awaryjny
### PreCompact: session_id '../../evil' nie wychodzi poza katalog snapshotow
    zapisano: proj/claude-state/precompact-evil.md; poza katalogiem: 0 plikow
WYNIK: 7/7 zgodnych
```

Trzy decyzje warte skopiowania:

1. **Limit długości (`MAX_CHARS`).** Stdout hooka to zwykły tekst w kontekście, który potem trzeba
   nosić do końca sesji. Odtwarzanie 50 KB „na wszelki wypadek” rozbija sens kompaktowania. Snapshot
   ma być krótką listą zadań i decyzji, nie zrzutem rozmowy.
2. **Sanityzacja `session_id`.** Wartość trafia do nazwy pliku, a payload to dane z zewnątrz —
   `../../evil` zamienia się w `precompact-evil.md` wewnątrz katalogu snapshotów (test w demo).
   Zasada ogólna: nigdy nie składaj ścieżki z pola payloadu bez filtra.
3. **Wersja awaryjna.** Brak snapshotu → jedna linia „odtwórz stan z TASKS.md”, a nie pusta cisza.

Katalog `claude-state/` to stan lokalny — dodaj do `.gitignore`.

> ⚠️ **Nie wiem na pewno**, czy `PreCompact` w Twojej wersji może dopisać własny tekst do
> streszczenia (stąd podział na dwa hooki zamiast jednego) ani czy `SessionStart` z `source=compact`
> odpala się dokładnie tak, jak zakładam. Skrypty są przetestowane wyłącznie na fixturach.
> Rejestracja w [`settings.example.json`](code/hooks/settings.example.json) (`matcher` po `source`)
> to składnia z pamięci.

---

## 4️⃣ Całość w jednym kadrze

```
CI / skrypt ─► verify_loop ─► claude -p (worker) ─► [subagent dotnet-reviewer: Read,Grep,Glob]
                   ▲                 │                         │ zwraca 5 linijek, nie 40 plików
                   │ ogon błędu      ▼ (sesja)                 ▼
                   └── verify ◄── zmiany ─── PreCompact ─ snapshot ─ SessionStart(compact) ─ odtworzenie
```

Trzy warstwy, trzy odpowiedzi na trzy pytania: *co agent może* (`tools`), *kto stwierdza
sukces* (exit code), *co przeżywa długą sesję* (plik + hooki).

---

## 📎 Co zweryfikowano, a czego nie

| ✅ Uruchomione naprawdę | ⚠️ Niezweryfikowane |
|---|---|
| Lint agenta: poprawny plik OK, zły plik 5 błędów + 2 ostrzeżenia (`validate_agent.py`) | Wszystko w żywej sesji Claude Code: wybór agenta po `description`, faktyczne egzekwowanie `tools`, `/agents` |
| Pętla worker→verify→feedback: sukces w 2. iteracji, porażka przy limicie 1 (exit 1) | `claude -p` i jego flagi (`--max-turns`, `--allowedTools`, `--output-format`) — polecenie `claude` odrzucone w środowisku |
| 7/7 przypadków hooków `PreCompact`/`SessionStart` (snapshot, odtworzenie, limit, `clear`, brak snapshotu, path traversal) | Kształt payloadów (`trigger`, `source`) i moment odpalenia `PreCompact`/`SessionStart` — fixtury z pamięci |
| Kod bez zależności, Python 3.10.4 | Oszczędność kontekstu z izolacji subagenta; to, że worker skryptowy zastępuje model (nie zastępuje — to stub) |

Nie mogłem zajrzeć do dokumentacji online — kontrakt pól to pamięć; sprawdź go w dokumentacji
subagentów i hooków swojej wersji przed wdrożeniem.

---

<div align="center">

[← wróć do wydania #3 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
