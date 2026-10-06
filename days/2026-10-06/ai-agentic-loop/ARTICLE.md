<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #13 — 6 października 2026

![AI/Agentic loop](https://img.shields.io/badge/AI_%2F_Agentic_loop-5A67D8?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Git](https://img.shields.io/badge/git_worktree-realnie_uruchomione-F05032?style=for-the-badge&logo=git&logoColor=white)
![Testy](https://img.shields.io/badge/asercje_lokalne-25%2F25-brightgreen?style=for-the-badge)
![Claude CLI](https://img.shields.io/badge/claude%20CLI-niezweryfikowane-lightgrey?style=for-the-badge)

## Równoległe agenty bez bijatyki: `git worktree` jako izolacja systemu plików

</div>

---

> _"Subagent ma izolowany **kontekst**. Ale nie ma izolowanego **dysku**. Dwóch agentów
> w jednym katalogu roboczym to dwóch programistów piszących w tym samym pliku w tym samym
> edytorze — tylko szybszych."_

W #4 zrobiliśmy wachlarz (fan-out) czterech reviewerów równolegle — ale to były reviewerzy:
`tools: Read, Grep, Glob`, nic nie piszą, więc nie mają o co się bić. Dziś **agenci, którzy
edytują kod**. Tu izolacja kontekstu (#3) nie wystarcza, bo kolizja dzieje się poziom niżej:
na plikach. Rozwiązanie jest starsze niż cały temat LLM i siedzi w gicie: `git worktree`.
Kod: [`code/`](code/).

> ⚠️ **Uczciwie na starcie:** rolę agentów gra tu **skrypt Pythona** (`worktree_fanout.py`
> edytuje pliki i robi commit), nie model i nie Claude Code. Realny jest **cały git**:
> worktree, branche, merge, konflikt, odmowy, sprzątanie — git 2.34.1, Python 3.10.4,
> `python3 code/worktree_fanout.py` → **25/25**. Komendy z `claude` w tym środowisku były
> dotąd odrzucane przez uprawnienia (#3, #4, #6) i nie próbowałem tego obchodzić — wszystko
> o żywej sesji poniżej jest oznaczone jako niezweryfikowane.

---

## 1️⃣ 💥 Problem: izolacja kontekstu to nie izolacja plików

Agent A poprawia zaokrąglenie w `Pricing.cs`. Agent B, który odczytał ten plik chwilę
wcześniej, zapisuje własną wersję całego pliku. Wynik z realnego uruchomienia (sekcja 1 skryptu):

```
class Pricing {
    decimal Net(decimal gross) => gross / (1 + VatRate);
}
  [OK]   lost update: zaokraglenie agenta A zniknelo, git nic nie zglosil
```

Zmiana A **zniknęła bez żadnego błędu**. To klasyczny *lost update*: nie ma tu
transakcji, blokady ani optymistycznej kontroli współbieżności (`rowversion` z EF Core to
dokładnie to, czego brakuje systemowi plików). Narzędzie `Edit` agenta zwykle wymaga
dokładnego dopasowania `old_string`, co częściowo chroni przed nadpisaniem cudzej linii —
ale (z pamięci, niezweryfikowane) nie chroni przed sytuacją, w której dwaj agenci budują
na rozbieżnych założeniach: testy jednego przechodzą na kodzie, który drugi właśnie zmienił;
`dotnet build` obu agentów walczy o ten sam `obj/`.

> 💡 **Haczyk — dlaczego to ważne:** im lepsza pętla z weryfikacją (#3), tym gorszy
> współdzielony katalog. Agent po każdej edycji odpala `dotnet test`; jeśli obok edytuje
> drugi, czerwony test może pochodzić z cudzej, **niedokończonej** zmiany. Pętla goni
> własny ogon, a Ty debugujesz poprawny kod.

---

## 2️⃣ 🔧 Mechanizm: czym jest worktree (i czym nie jest)

`git worktree add -b agent-a ../wt-a main` tworzy **drugi katalog roboczy** podpięty do
**tego samego repozytorium**. Z wyjścia skryptu:

```
<TMP>/repo        9e2e897 [main]
<TMP>/wt-agent-a  9e2e897 [agent-a]
<TMP>/wt-agent-b  9e2e897 [agent-b]
...
zawartosc wt-agent-a/.git (to PLIK, nie katalog): gitdir: <TMP>/repo/.git/worktrees/wt-agent-a
```

Co z tego wynika:

| Współdzielone (jedna baza obiektów) | Własne dla każdego worktree |
|---|---|
| historia, obiekty, `refs`, konfiguracja | pliki robocze, `HEAD`, **indeks** (staging) |
| **brak** kosztu pełnego `git clone` — nie kopiujesz historii | `obj/`, `bin/`, `node_modules/` (jeśli nie są w gicie — patrz niżej) |

`.git` w worktree jest **plikiem** wskazującym na `.git/worktrees/<nazwa>/` w głównym
repo — tam leży per-worktree `HEAD` i indeks. Dzięki temu `git add`/`commit` agenta A nie
dotyka stagingu agenta B. W artykule z #4 pisałem o izolacji kontekstu; to jest jej odpowiednik
dla dysku, i kosztuje tyle co checkout plików.

**Reguła, która wymusza porządek:** ten sam branch nie może być wystawiony w dwóch worktree.
Realny komunikat gita:

```
fatal: 'agent-a' is already checked out at '<TMP>/wt-agent-a'
```

Każdy agent dostaje więc **własny branch** — i to jest feature: git nie pozwoli, byś
przypadkiem uruchomił dwóch agentów na tej samej gałęzi.

### Równoległość naprawdę zachodzi

Cztery "agenci" (wątki, każdy "pracuje" 0,4 s i commituje): czas ściany **0,44 s** przy sumie
pracy 1,75 s. Przez cały ten czas `git status` w głównym katalogu był **czysty**, a agent A nie
widział zmiany agenta B. Graf po pracy:

```
* d95f553 agent agent-a
| * 0e85cec agent agent-b
|/
| * 8e93ce4 agent agent-c
|/
* 9e2e897 seed
```

(Hashe zmieniają się między uruchomieniami — zależą od czasu commitu.)

> ⚠️ **Pułapka .NET:** worktree to **świeży checkout**: bez `obj/`, `bin/`, bez przywróconych
> pakietów. Pierwszy `dotnet build` w każdym worktree robi pełny restore (cache NuGet w
> katalogu użytkownika jest wspólny, więc pobieranie nie powtarza się, ale kompilacja tak).
> Pliki spoza gita (`appsettings.Development.json`, user-secrets, `.env`) **nie pojawią się**
> w worktree — agent odpali aplikację bez konfiguracji. Tego w skrypcie nie sprawdzałem
> (fixture to dwa pliki `.cs`, bez `dotnet`); to wniosek z mechaniki checkoutu.

---

## 3️⃣ ⚔️ Izolacja nie usuwa konfliktu — przesuwa go na merge

Worktree nie sprawia, że agenci nie kolidują. Sprawia, że kolizja jest **jawna, późna i
odwracalna** zamiast cicha. Scenariusz skryptu: A zmienia `Pricing.cs` + dopisuje wpis do
`CHANGELOG.md`; B zmienia tylko `Orders.cs`; C dopisuje wpis do `CHANGELOG.md` pod tym samym
nagłówkiem co A.

| Merge | Wynik (realny) | Dlaczego |
|---|---|---|
| `agent-a` | kod 0 | pierwszy |
| `agent-b` | kod 0 | rozłączne pliki |
| `agent-c` | **kod 1, `CONFLICT (content): Merge conflict in CHANGELOG.md`** | oba dopisały w tym samym miejscu |

```
<<<<<<< HEAD
- Pricing: zaokraglenie do groszy
=======
- Orders: licznik z kolekcji
>>>>>>> agent-c
```

Wniosek projektowy ważniejszy niż sam git: **konflikt wzięty z pliku, który *wszyscy*
agenci dotykają z natury** (`CHANGELOG.md`, plik `.csproj` z listą pakietów, `Program.cs` z
rejestracją DI, migracje EF — snapshot modelu!) jest przewidywalny. Nie "debuguj" go —
zaprojektuj zadania tak, by nikt współdzielonego pliku nie dotykał, albo niech
**jeden agent-integrator** scala te wpisy po fakcie. W skrypcie integrator robi `git rebase
main` na gałęzi C, scala oba wpisy ręcznie, `rebase --continue`, a potem merge przechodzi
jako `--ff-only`. `git merge --abort` przywraca czyste drzewo (zweryfikowane asercją).

> 💡 **Analogia .NET:** to model *optimistic concurrency* z EF Core. Nie blokujesz wierszy
> (worktree = każdy pracuje na własnej kopii), a konflikt wykrywasz przy zapisie
> (`merge` = `DbUpdateConcurrencyException`). I tak jak tam: strategia rozwiązania musi
> być zaplanowana z góry, a nie wymyślana przy wyjątku.

---

## 4️⃣ 🧹 Sprzątanie: najczęściej pomijany etap — i tu git jest po Twojej stronie

Porzucone worktree to realne śmieci: katalogi w `/tmp`, wiszące branche, wpisy w
`.git/worktrees/`. Git ma trzy bezpieczniki, wszystkie zaobserwowane w skrypcie:

| Sytuacja | Realna odpowiedź gita |
|---|---|
| `worktree remove` na katalogu z niezacommitowanymi plikami | `fatal: '…' contains modified or untracked files, use --force to delete it` (kod 128) |
| `branch -d` na branchu wciąż wystawionym w worktree | `error: Cannot delete branch 'agent-b' checked out at '…'` |
| `branch -d` na branchu z niezmergowanym commitem | `error: The branch 'agent-b' is not fully merged.` |

Czyli praca agenta **nie ginie po cichu**: żeby ją stracić, trzeba świadomie dać `--force` /
`-D`. Reguła decyzyjna, którą implementuje skrypt (i którą warto skopiować do swojego
wrappera): worktree **bez commitów ponad bazę i z czystym drzewem** (`agent-d` — nic nie
zmienił) → zdejmij bez śladu; z commitami → merge lub zostaw do przeglądu; brudne → człowiek.
To, nawiasem, odpowiada opisowi parametru `isolation: "worktree"` narzędzia `Agent`, który widzę
w definicji narzędzi tej sesji: *tymczasowy worktree, automatycznie sprzątany, jeśli bez
zmian* — ten sam mechanizm, tylko po stronie harnessu. (Opis pochodzi z definicji narzędzia,
nie z uruchomienia: nie odpalałem subagenta z tą opcją.)

Końcowy stan po sprzątaniu: jeden worktree, jeden branch `main`, `.git/worktrees/` pusty,
katalog tymczasowy usunięty — każde z tych zdań to osobna asercja.

---

## 5️⃣ 🗺️ Checklista: równoległe agenty piszące kod

1. **Jeden agent = jeden branch = jeden worktree** (git i tak wymusza unikalność brancha).
2. **Dziel zadania po plikach**, nie po "funkcjach". Pliki współdzielone (rejestracje DI,
   changelog, migracje) → jeden właściciel albo faza integracji.
3. **Weryfikacja (`dotnet test`) w worktree agenta**, nie w głównym katalogu — inaczej
   wraca problem z sekcji 1.
4. **Merge sekwencyjnie**, po każdym uruchom testy na `main` — dwie zmiany zmergowane bez
   konfliktu tekstowego nadal mogą się rozjechać semantycznie (git tego nie wykryje).
5. **Sprzątaj według reguły**: czyste i bez commitów → usuń; reszta → człowiek.

---

## 📎 Co zweryfikowano, a czego nie

| ✅ Uruchomione naprawdę (git 2.34.1, Python 3.10.4, tymczasowe repo w `/tmp`) | ⚠️ Niezweryfikowane |
|---|---|
| `python3 code/worktree_fanout.py` — **25/25** asercji | Żywa sesja `claude` i `claude --version` — nie próbowano (odrzucane w #3/#4/#6) |
| lost update w jednym katalogu; 4 worktree równolegle (0,44 s vs 1,75 s) | Pole `permissionMode` we frontmatterze agenta i hooki w trybie headless (`-p`) — **nie omawiane dziś**, zostają na następne wydanie |
| `.git` jako plik `gitdir:`; odmowa drugiego checkoutu tego samego brancha | Zachowanie `isolation: "worktree"` narzędzia `Agent` (znane tylko z opisu narzędzia) |
| merge czysty ×2, konflikt w `CHANGELOG.md`, `merge --abort`, rebase + ff-only | `dotnet build`/`test` w worktree (fixture bez .NET), pliki spoza gita |
| trzy odmowy przy sprzątaniu; stan końcowy; usunięcie katalogu tymczasowego | Inne wersje gita (testowano 2.34.1); Windows (ścieżki, blokady plików) |

Rolę agentów gra skrypt, nie model. Czy prawdziwy agent poprawnie wybierze rozłączne pliki,
czy będzie potrafił sam rozwiązać konflikt — to pytania o model, na które ten kod nie odpowiada.

---

## 🎁 Bonus: prawdziwa specyfikacja całego procesu

Powyżej — mechanika jednego elementu (izolacja plików). Osobno, z rzeczywistej sesji
brainstormingowej, powstała pełna specyfikacja **całego szkieletu pętli agentowej** (bramki,
role agentów, budżety, powrót do specyfikacji przy luce) — bez symulacji, zero fikcji:
[`BONUS-spec-projektowy.md`](BONUS-spec-projektowy.md).

---

<div align="center">

[← wróć do wydania #13 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
