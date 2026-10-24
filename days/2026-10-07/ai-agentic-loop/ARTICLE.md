<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #14 — 7 października 2026

![AI/Agentic loop](https://img.shields.io/badge/AI_%2F_Agentic_loop-5A67D8?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10.4-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Testy](https://img.shields.io/badge/testy_lokalne-25%2F25-brightgreen?style=for-the-badge)
![Claude CLI](https://img.shields.io/badge/claude%20CLI-niezweryfikowane-lightgrey?style=for-the-badge)

## Pętla, która umie się zatrzymać i wznowić: budżet, wykrywanie zapętlenia, retry, idempotencja

</div>

---

> _"Pętla agentowa to `while (true)` z modelem w środku. Każdy .NET-owiec wie, co jest
> najważniejsze w `while (true)`: warunek wyjścia, którego nie napisał model."_

Przez trzynaście wydań budowaliśmy to, **co agent może zrobić** (hooki, skille, subagenci,
worktree). Dziś o tym, **kiedy musi przestać** i **co, gdy proces padnie w połowie**.
To rzeczy, których nie widać w demo, a które decydują, czy agent na nocnym zadaniu
spali budżet na powtarzaniu jednego polecenia albo wyśle klientowi dwa maile. Kod: [`code/`](code/).

> ⚠️ **Uczciwie na starcie:** rolę modelu gra tu **deterministyczna funkcja Pythona**
> `policy(historia) -> Action | Done`. To nie jest LLM ani Claude Code. Realny i uruchomiony
> jest **nadzorca** (supervisor): budżety, detektory, retry, dziennik, wznawianie.
> Python 3.10.4, `python3 code/run_tests.py` → **25 testów OK**. Komenda `claude` jest w tym
> środowisku odrzucana przez uprawnienia (`claude --version` odrzucone także dziś) i nie
> próbowałem tego obchodzić — co Claude Code robi sam w tych sprawach, nie jest tu zweryfikowane.

---

## 1️⃣ 🧭 Model mentalny: nadzorca to nie część modelu

Pętla z #1 wygląda tak: model proponuje wywołanie narzędzia → **harness** je wykonuje →
wynik wraca do modelu → powtórz, aż model powie „koniec". Zauważ, że jedyny warunek
zakończenia należy do modelu. A model potrafi się mylić **konsekwentnie**: dostaje błąd
kompilacji, „naprawia", dostaje ten sam błąd, „naprawia"...

Dlatego między modelem a światem stoi kod, który model **kontroluje, ale którym nie jest**:

| Warstwa | Pytanie, na które odpowiada | Analogia z .NET |
|---|---|---|
| Budżet | czy wolno jeszcze iść dalej? | `CancellationTokenSource(timeout)`, limit rekordów |
| Detektor zapętlenia | czy to jeszcze postęp? | circuit breaker (Polly), watchdog |
| Retry z backoffem | czy błąd jest przejściowy? | `WaitAndRetryAsync` |
| Klucz idempotencji | czy powtórka zrobi to samo, co raz? | `Idempotency-Key`, deduplikacja w MassTransit Outbox |
| Dziennik (WAL) | co już się stało po restarcie? | event store / Outbox / write-ahead log |

W kodzie to klasa `Supervisor` (`agentloop.py`), a pętla ma po drodze sześć miejsc, w których
może się skończyć: `DONE`, `BUDGET_STEPS`, `BUDGET_COST`, `BUDGET_WALL`, `LOOP`,
`NO_PROGRESS` (plus `NEEDS_HUMAN` przy wznawianiu). Każde zakończenie ma **nazwany powód**
— to ważne, bo `claude -p` w CI (#4) musi umieć rozróżnić „skończyłem" od „utknąłem".

---

## 2️⃣ 💸 Budżet: trzy osie, nie jedna

`Budget` ma trzy limity i sprawdza je **przed** każdym krokiem:

- **kroki** (`max_steps`) — najprostszy bezpiecznik,
- **koszt** (`max_cost`) — tu umowne „tokeny" (`len(tekst)//4`, akcja + wynik). To przybliżenie
  *wyłącznie na potrzeby symulacji*; prawdziwe rozliczenie tokenów robi API i nie jest tu
  odtwarzane,
- **czas ścienny** (`max_wall`) — liczony zegarem **wirtualnym** (`VirtualClock`), więc
  testy nie czekają na `sleep`, a backoff realnie zjada budżet czasu.

Dlaczego trzy? Bo każda oś łapie co innego: pętla krótkich kroków łapie się na krokach,
pętla kroków z wielkimi wynikami (czytanie dużych plików) na koszcie, a seria
timeoutów na czasie. Test `test_wall_budget_consumed_by_backoff` pokazuje ostatni
przypadek: serwer stale zwraca 503, a budżet czasu kończy pętlę (`BUDGET_WALL`), mimo że
liczba kroków jest daleko od limitu.

Rzeczywisty przebieg „agent czyta plik w kółko z różnymi parametrami" (limit 5 kroków):

```
== 4. budzet krokow
  krok 1: read_file  ok=True  proby=1 class Foo { int X() => y; }
  ...
  krok 5: read_file  ok=True  proby=1 class Foo { int X() => y; }
  => BUDGET_STEPS: limit 5 krokow (koszt=65, wznowiono_od=0)
```

> 💡 **Haczyk — dlaczego to ważne:** budżet musi być twardy i **poza** modelem. Prośba w
> prompcie „nie rób więcej niż 10 kroków" to życzenie, nie `if`. A koszt/czas muszą się
> **kumulować przy wznowieniu** (test `test_budget_accumulates_across_resume`) — inaczej
> restart zeruje licznik i „limit" staje się „limitem na próbę". Jedno zastrzeżenie:
> licznik czasu ściennego **nie** jest zapisywany w dzienniku; po wznowieniu startuje od zera.

---

## 3️⃣ 🔁 Zapętlenie: trzy detektory, bo jeden nie wystarczy

Oczywiste „to samo polecenie trzy razy" łapie tylko najgłupszą pętlę. Zbudowałem trzy
detektory na **odcisku akcji** (`fingerprint` = nazwa narzędzia + argumenty w postaci
kanonicznej: klucze posortowane, więc `{"a":1,"b":2}` == `{"b":2,"a":1}`):

**1. `LOOP_EXACT`** — N identycznych odcisków z rzędu:

```
== 1. zapetlenie: ta sama akcja
  krok 1: run_tests  ok=False proby=1 AssertionError: FAIL CS0103: name 'y' does not exist at Foo.
  krok 2: run_tests  ...
  krok 3: run_tests  ...
  => LOOP: LOOP_EXACT: 3x ta sama akcja z rzedu (koszt=51, wznowiono_od=0)
```

**2. `LOOP_CYCLE`** — ogon historii to cykl o okresie 2 lub 3 powtórzony 3 razy
(edit → test → edit → test → ...). Pętla „ping-pong" nie ma dwóch identycznych kroków
z rzędu, więc detektor 1 jej nie widzi:

```
== 2. cykl edit/test
  krok 1: edit_file ... krok 6: run_tests
  => LOOP: LOOP_CYCLE: cykl okresu 2 powtorzony 3x (koszt=75, wznowiono_od=0)
```

**3. `NO_PROGRESS`** — to najciekawszy przypadek. Agent za każdym razem zmienia *treść*
edycji (np. dopisuje inny komentarz), więc **żaden odcisk się nie powtarza** — a test
pada tym samym błędem. Detektor patrzy więc nie na akcje, tylko na **sygnaturę błędu**:
pierwsza linia wyniku z wyzerowanymi liczbami (numer linii czy czas nie mogą rozróżniać
błędów). Cztery takie same błędy → stop:

```
== 3. rozne akcje, ten sam blad
  krok 1: edit_file  ok=True ...   krok 2: run_tests  ok=False ... (x4 pary)
  => NO_PROGRESS: 4x ten sam blad 'AssertionError: FAIL CSN: name 'y' does not exist at Foo.cs:N' ...
```

Test `test_varied_actions_caught_by_no_progress` sprawdza też **kontrolę**: przy tych
samych krokach detektory odcisków nic nie wykrywają (cztery różne edycje) — czyli
trzeci detektor jest naprawdę potrzebny, nie dubluje pozostałych.

Dwie świadome decyzje, o których trzeba wiedzieć:

- W `NO_PROGRESS` udane kroki pośrednie (edycje) są **pomijane** — liczą się tylko
  błędy. Inaczej naprzemienność OK/błąd zawsze by „resetowała" licznik.
- Błędy narzędzi to **obserwacje**, nie wyjątki: `AssertionError` z testów trafia do
  historii jako `ok=False` i agent ma go zobaczyć (inaczej nie naprawi). Nieznane
  narzędzie też. Dlatego zapętlenie jest wykrywalne tylko na poziomie nadzorcy.

> 💡 **Haczyk:** progi (3 powtórzenia, 4 błędy) to **heurystyki dobrane przeze mnie**,
> nie wartości z jakiejkolwiek dokumentacji. Za niski próg ucina uczciwe „spróbuj ponownie
> po zmianie"; za wysoki — palisz budżet. W realnym systemie dostrajasz je na danych.

---

## 4️⃣ ⏱️ Retry z backoffem: tylko przejściowe, tylko tam, gdzie wolno

Każde wywołanie narzędzia przechodzi przez `_execute`, który rozróżnia:

| Błąd | Zachowanie | Dlaczego |
|---|---|---|
| `TransientError` (503, timeout) | ponów, max 4 próby, z odstępem | zmieni się za chwilę bez udziału agenta |
| każdy inny wyjątek | **bez retry**, wynik wraca do agenta jako `ok=False` | powtórka da to samo; agent ma zmienić podejście |
| wyczerpane próby | `ok=False` + „TransientError po 4 próbach" | agent (lub człowiek) decyduje dalej |

Odstęp to **exponential backoff z full jitter**: `uniform(0, min(cap, base·2^k))`. Jitter
nie jest ozdobą — bez niego N agentów, którzy dostali 503 jednocześnie, ponawia
jednocześnie i znów kładzie serwer (thundering herd). Realne opóźnienia z demo (`seed=7`,
3 awarie, sukces w 4. próbie):

```
== 5. retry z backoffem (3 awarie 503)
  krok 1: fetch      ok=True  proby=4 payload
  opoznienia (full jitter, seed=7): [0.324, 0.302, 2.604]
```

Zwróć uwagę: drugie opóźnienie (0,302) jest **krótsze** niż pierwsze mimo że górna granica
rośnie (1 → 2 → 4 s). Tak działa full jitter i testy sprawdzają tylko to, co
gwarantuje: wartość w `[0, min(cap, base·2^k)]` oraz powtarzalność przy tym samym ziarnie.
Czas jest wirtualny — nic tu realnie nie spało.

> ⚠️ **Pułapka:** retry jest bezpieczny dla operacji **idempotentnych**. Ponowienie
> `POST /charge` po timeoucie to klasyczny sposób na podwójne obciążenie — timeout nie
> znaczy, że serwer nic nie zrobił. W tej symulacji retry dotyczy tylko `TransientError`,
> który *deklaruje* narzędzie; nie próbuje zgadywać po tekście błędu.

---

## 5️⃣ 💥 Dziennik i wznawianie: at-least-once + klucz = „prawie exactly-once"

Co, gdy proces padnie w trakcie zadania? `Supervisor` pisze **write-ahead log** (JSONL,
`fsync` po każdym wpisie): rekord `intent` **przed** wykonaniem narzędzia i `result` **po**.
Agent (`policy`) jest funkcją *historii*, więc wznowienie to po prostu wczytanie dziennika
i odtworzenie historii — model niczego „nie pamięta", dostaje ten sam kontekst.

Najgorszy moment awarii jest **między efektem a zapisem wyniku**. Realny dziennik po
symulowanym crashu w tym punkcie (narzędzie `notify`, krok 2):

```
{'t': 'intent', 'step': 1, 'tool': 'notify', 'args': {'msg': 'start'}, 'key': 'f48a2478480a4a56'}
{'t': 'result', 'step': 1, 'ok': True, 'out': 'sent', 'attempts': 1}
{'t': 'intent', 'step': 2, 'tool': 'notify', 'args': {'msg': 'koniec'}, 'key': '45984da001f53546'}
```

Krok 2 ma `intent` bez `result`. Czy wiadomość wyszła? **Z dziennika nie wiadomo** — i to jest sedno.
Są tylko dwie uczciwe odpowiedzi:

1. **Narzędzie honoruje klucz idempotencji** (`key = sha256(run_id|krok|odcisk)`): wykonujemy
   krok ponownie **z tym samym kluczem**, a odbiorca deduplikuje.
2. **Nie honoruje** → nadzorca **odmawia zgadywania** i zwraca `NEEDS_HUMAN`.

Wyniki z uruchomienia:

```
== 6. crash po efekcie, przed zapisem wyniku (notify z kluczem)
==    wznowienie
  krok 1: notify     ok=True  proby=1 sent
  krok 2: notify     ok=True  proby=1 dedup (already sent)
  => DONE: ok (koszt=15, wznowiono_od=1)
  wywolan notify=3, efektow w outbox=2

== 7. crash po 'charge' (narzedzie bez klucza)
  krok 1: fetch      ok=True  proby=1 payload
  => NEEDS_HUMAN: krok 2 (charge) mogl sie wykonac, narzedzie nie honoruje klucza idempotencji
  obciazenia: [100]
```

Trzy wywołania `notify`, ale **dwa efekty** — to dokładnie „at-least-once delivery +
idempotentny odbiorca = efekt raz" (ten sam wzorzec co Inbox/Outbox w MassTransit z
wydań o brokerach). W scenariuszu 7 obciążenie nie zostało podwojone.

Testy dopowiadają pozostałe przypadki:

| Test | Co dowodzi |
|---|---|
| `crash_after_effect_with_key_dedups` | wywołań 3, efektów 2 |
| `control_restart_without_journal_duplicates` | **kontrola:** restart od zera z nowym `run_id` → 4 efekty zamiast 2 |
| `crash_after_intent_executes_once` | crash przed efektem: po wznowieniu dokładnie raz |
| `unsafe_tool_crash_after_intent_also_needs_human` | tu nic się nie wykonało (`charges == []`), ale dziennik **nie odróżnia** tego od poprzedniego przypadku → i tak `NEEDS_HUMAN` |
| `read_only_pending_is_reexecuted` | narzędzie bez efektów ubocznych: po prostu powtórz |
| `torn_journal_tail_ignored` | urwana ostatnia linia JSON nie wywraca wznowienia |
| `resumed_history_equals_uninterrupted` | po wznowieniu agent widzi tę samą historię akcji co bez awarii |

Dwie rzeczy, które testy ujawniły i które uczciwie trzeba nazwać:

- **Wynik kroku 2 po wznowieniu to `dedup (already sent)`, a nie oryginalne `sent`.**
  Agent dostaje inną *obserwację* niż w przebiegu bez awarii. Tu nieszkodliwe, ale
  w ogólności „idempotentne" nie znaczy „ta sama odpowiedź" — dobry odbiorca powinien
  zwracać oryginalny wynik dla powtórzonego klucza.
- `resumed_from` liczy tylko kroki z kompletnym wynikiem; krok `pending` jest wykonywany
  ponownie i nie wchodzi do tej liczby (to była moja błędna asercja, którą test wyłapał).

> 💡 **Haczyk — dlaczego to ważne:** model *nie jest* gwarancją exactly-once i nie
> będzie. Gwarancję dają: dziennik zapisywany **przed** efektem + klucz idempotencji +
> narzędzia, które go respektują. Każde narzędzie z efektem ubocznym, które dajesz agentowi
> (wysyłka maila, `kubectl apply`, płatność), powinno mieć odpowiedź na pytanie „co, jeśli
> wywołam je drugi raz z tym samym kluczem?". Naturalnie idempotentne (`edit_file` =
> „ustaw zawartość") jest łatwe; `append` i `charge` — nie.

---

## 6️⃣ 🧪 Co jest, a czego nie ma

**Zweryfikowane (realne uruchomienie, Python 3.10.4):**
- 25 testów `unittest` przechodzi (`Ran 25 tests ... OK`), `demo.py` wygenerował cały output powyżej.
- Budżety (kroki/koszt/czas wirtualny), trzy detektory zapętlenia z kontrolą, retry+full jitter
  (granice i powtarzalność), wznawianie z dziennika, dedup po kluczu, `NEEDS_HUMAN`,
  urwany ogon dziennika.

**Niezweryfikowane / uproszczone — wprost:**
- **Żywa sesja Claude Code i `claude -p`** — `claude` odrzucone przez uprawnienia; nie wiem
  (tu), jakie limity i detekcję pętli ma sam harness ani czy `claude -p` ma flagi budżetowe.
  Nie zakładaj, że to, co zbudowałem, jest tym, co robi Claude Code.
- „Model" to deterministyczny skrypt; realny LLM bywa niedeterministyczny, więc wznowienie
  odtwarza **historię**, ale jego *następna* decyzja może się różnić.
- „Tokeny" to `len/4`, nie rozliczenie API. Progi detektorów to moje heurystyki.
- Zapis do dziennika jest `fsync` na jednym pliku lokalnym; nie testowałem awarii dysku,
  współbieżnych zapisów z wielu procesów ani Windows. Po `NEEDS_HUMAN`/`DONE` ponowne
  uruchomienie na tym samym dzienniku nie jest obsłużone specjalnie (brak rekordu „zamknięty").
- Czas ścienny nie jest persystowany przy wznowieniu.

**Następne kroki:** `permissionMode` w frontmatterze agenta i hooki w trybie headless
(po weryfikacji CLI); persystencja czasu i „zamknięcie" biegu w dzienniku; kompaktowanie
dziennika (snapshoty zamiast pełnej historii); zwracanie oryginalnego wyniku przy dedupie;
detektor oparty o zmianę stanu repo (hash drzewa) zamiast tekstu błędu.
