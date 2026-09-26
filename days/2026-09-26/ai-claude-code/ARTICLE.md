<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #3 — 26 września 2026

![AI](https://img.shields.io/badge/AI_%2F_Claude_Code-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Zweryfikowane](https://img.shields.io/badge/hook-5%2F5%20na%20prawdziwym%20dotnet%2010-brightgreen?style=for-the-badge)

## Agent edytuje C#, a hook sam formatuje i buduje — oraz `.claude/` dla całego zespołu

</div>

---

> _"Najdroższy błąd kompilacji to taki, który agent odkryje dopiero po dziesięciu
> kolejnych edycjach."_

Wydania #1 i #2 to były hooki **`PreToolUse`** — bramki *przed* akcją. Dziś druga
strona: **`PostToolUse`**, czyli reakcja *po* edycji pliku. Do tego jak spiąć wszystko
w jeden plik `settings.json`, który trafia do repo i obowiązuje cały zespół.
Kod: [`code/`](code/).

---

## 1️⃣ 🪝 Hook `PostToolUse`: po każdej edycji `.cs` — format + build

### 🎯 Dlaczego to ważne

Agent edytuje plik i idzie dalej *z założeniem*, że się kompiluje. Jeśli nie — błąd
wychodzi kilka kroków później, zwykle przy `dotnet test`, i model łata objaw zamiast
przyczyny. Hook po edycji skraca pętlę sprzężenia zwrotnego do jednej edycji: błąd
kompilacji wraca do modelu **natychmiast**, razem z linią i kodem `CSxxxx`. Przy okazji
formatowanie przestaje być tematem review ("popraw wcięcia").

### Jak to działa

Konfiguracja ([`settings.snippet.json`](code/claude-hooks/settings.snippet.json)):
`PostToolUse`, matcher `Write|Edit|MultiEdit`, komenda
`python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/dotnet-post-edit.py"`, `timeout: 150`.

[`dotnet-post-edit.py`](code/claude-hooks/dotnet-post-edit.py) robi na payloadzie ze stdin:

1. Filtr: tylko `Write`/`Edit`/`MultiEdit`, tylko `*.cs`, nie `bin/`/`obj/`.
2. Idzie w górę od pliku do katalogu z **dokładnie jednym** `.csproj` (dwa → nie zgaduje, wychodzi z 0).
3. `dotnet format whitespace <csproj> --include <plik> --no-restore` — poprawia białe znaki wg
   `.editorconfig`, **tylko ten jeden plik**, żeby nie generować diffa na pół repo.
4. `dotnet build <csproj> --no-restore -nologo -v q` — przy błędzie: unikalne linie `error CSxxxx` na
   stderr, **exit 2**. Tak samo jak w `PreToolUse` kod 2 oznacza "stderr wraca do Claude" — tyle że
   tu akcja już się wykonała, więc to nie blokada, tylko *informacja zwrotna*.

Testów hook celowo **nie** uruchamia: na każdą edycję byłoby to zbyt wolne. Testy to
robota dla hooka `Stop` (patrz rubryka o pętli agentowej, wydanie #2).

### ▶️ Prawdziwy przebieg (.NET SDK 10.0.400)

[`demo.py`](code/demo.py) kopiuje [`sample-app`](code/sample-app) (mały projekt `net10.0`)
do katalogu tymczasowego, podmienia `Order.cs` i woła hook z payloadem takim, jak wysłałby
`Edit`/`Write`:

```
OK   exit=0 (oczekiwano 0)  czysty plik, buduje sie
     plik zmieniony przez hook: nie
OK   exit=0 (oczekiwano 0)  brzydkie formatowanie -> auto-format
     plik zmieniony przez hook: tak
     stdout| dotnet-post-edit: sformatowano Order.cs wg .editorconfig - wczytaj plik ponownie przed kolejna edycja
OK   exit=2 (oczekiwano 2)  blad kompilacji -> blokada
     stderr| BUILD NIE PRZECHODZI po edycji Order.cs (1 bledow):
     stderr|   .../sample-app/Orders.App/Order.cs(7,67): error CS1061: 'Order' does not contain a definition for 'GrossAmount' and no accessible extension method 'GrossAmount' accepting a first argument of type 'Order' could be found (are you missing a using directive or an assembly reference?)
     stderr| Napraw bledy kompilacji zanim przejdziesz dalej.
OK   exit=0 (oczekiwano 0)  inne narzedzie niz edycja
OK   exit=0 (oczekiwano 0)  plik nie-.cs

WYNIK: 5/5 przypadkow zgodnych
```

Formatowanie zamienia tabulatory i klamry "w tej samej linii" na styl z `.editorconfig`
(pełny plik przed/po: [`code/README.md`](code/README.md)).

### 🕳️ Pułapka, która naprawdę mi się przytrafiła: cichy no-op

Pierwsza wersja hooka przekazywała `--include` ze ścieżką **bezwzględną**. Efekt:
`dotnet format` zwrócił kod **0**, bez żadnego komunikatu — i **nic nie sformatował**.
Test "brzydkie formatowanie" przeszedł, bo sprawdzałem tylko kod wyjścia hooka. Wyszło
dopiero po obejrzeniu pliku. Poprawka: ścieżka **względna** do katalogu projektu
(`os.path.relpath`), a w `demo.py` asercja, że plik faktycznie się zmienił.
Wniosek ogólny: hook, który kończy się zielono, nie znaczy, że coś zrobił — testuj
*skutek* (zmieniony plik), nie tylko kod wyjścia.

> ⚠️ **Świadomy kompromis.** Formatter zmienia plik na dysku *po* edycji modelu. Model może
> mieć w głowie starą treść, więc hook wypisuje notkę "wczytaj plik ponownie". Czy ta notka
> ze stdout (przy exit 0) trafia do modelu, czy tylko do logu — **nie zweryfikowałem**
> (patrz tabela na dole).

---

## 2️⃣ 🧰 `.claude/` w zespole: jeden `settings.json` w repo

### 🎯 Dlaczego to ważne

Hook, który działa tylko na Twoim laptopie, to hobby. Wartość pojawia się, gdy **każdy**
w zespole (i każdy agent w CI) dostaje te same bariery po `git clone`. Do tego uprawnienia:
zamiast klikać "Allow" przy każdym `dotnet build`, zapisujesz to raz — a rzeczy groźne
(`git push`, `dotnet ef database update` na produkcję, odczyt `.env`) wpisujesz na czarną listę.

### Podział plików

| Plik | W git? | Po co |
|---|---|---|
| `.claude/settings.json` | ✅ tak | reguły zespołu: uprawnienia + hooki |
| `.claude/settings.local.json` | ❌ `.gitignore` | Twoje osobiste ustawienia |
| `.claude/hooks/*.py` | ✅ tak | skrypty hooków (ścieżka przez `$CLAUDE_PROJECT_DIR`) |
| `.claude/skills/`, `.claude/commands/` | ✅ tak | skille i komendy z wydań #1 i #2 |

Zespołowy [`settings.json`](code/claude-config/settings.json): allow na `dotnet build/test/format`
i read-only `git`; **deny** na `git push`, `dotnet ef database update`, `.env`
i `appsettings.Production.json`; do tego hook z części 1.

Konfigurację łatwo popsuć bez wyraźnego błędu (literówka w regule = reguła nie działa),
więc [`validate_settings.py`](code/validate_settings.py) to lint, który można wpiąć w CI:

```
$ python3 validate_settings.py
[json] claude-config/settings.json
    OK  poprawny JSON, klucze: permissions, hooks
[permissions]
    OK  allow: 6 regul o poprawnej skladni
    OK  deny: 4 regul o poprawnej skladni
    OK  brak regul wystepujacych w allow i w deny
[hooks]
    OK  PostToolUse matcher 'Write|Edit|MultiEdit' to poprawny regex
    OK  plik hooka istnieje: claude-hooks/dotnet-post-edit.py
[gitignore]
    OK  settings.local.json jest ignorowany

WYNIK: konfiguracja poprawna.
```

> ⚠️ **Uczciwie o zakresie.** Lint sprawdza *kształt* pliku (JSON, składnia reguł,
> istnienie skryptu). **Nie** sprawdza, czy Claude Code faktycznie interpretuje daną
> regułę tak, jak zakładasz — składnię reguł (`Bash(cmd:*)`, `Read(./.env)`) i pierwszeństwo
> deny nad allow zapisałem z pamięci i **nie potwierdziłem w dokumentacji** (próba
> pobrania dokumentacji w tym środowisku została odrzucona). Sprawdź w oficjalnych docs,
> zanim oprzesz na tym politykę bezpieczeństwa. Nie traktuj też `deny` jako jedynej
> ochrony sekretów — sekrety nie powinny leżeć w repo w ogóle.

---

## 📎 Co zweryfikowano, a czego nie

| ✅ Uruchomione naprawdę | ⚠️ Niezweryfikowane |
|---|---|
| Hook na `dotnet` SDK 10.0.400: 5 scenariuszy (czysty plik, auto-format, błąd CS1061 → exit 2, obce narzędzie, plik nie-.cs) | Wpięcie w żywej sesji Claude Code; to, czy stdout przy exit 0 widzi model |
| `sample-app` uruchomiony: `dotnet run` → `148.22` | Dokładny kształt payloadu `PostToolUse` (używam tylko `tool_name` i `tool_input.file_path`; z pamięci) |
| `validate_settings.py` na `settings.json` | Semantyka reguł `permissions` i pierwszeństwo deny/allow |
| | Czas na dużych solucjach (build jednego `.csproj` może być wolny; brak pomiarów) |
| | `sqlcmd` niedostępny w środowisku — skill do przeglądu SQL/indeksów zostaje na kolejne wydanie |

Środowisko: .NET SDK 10.0.400, Python 3.10.4 (tylko stdlib).

---

<div align="center">

[← wróć do wydania #3 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
