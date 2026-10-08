<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #15 — 8 października 2026

![AI/Agentic loop](https://img.shields.io/badge/AI_%2F_Agentic_loop-5A67D8?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10.4-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Testy](https://img.shields.io/badge/testy_lokalne-24%2F24-brightgreen?style=for-the-badge)
![Claude CLI](https://img.shields.io/badge/claude%20CLI-niezweryfikowane-lightgrey?style=for-the-badge)

## Dziennik ma początek, a nie miał końca: zamknięcie biegu, zegar po restarcie i człowiek jako rekord

</div>

---

> _"Write-ahead log, który mówi tylko „co zaczęliśmy", to dziennik z amnezją. Dobry dziennik mówi
> też „skończyliśmy", „ile to trwało" i „kto zdecydował za maszynę"."_

Wczoraj (#14) nadzorca dostał budżet, detektory zapętlenia, retry i dziennik write-ahead. Dziennik
rozwiązał problem „proces padł w połowie". Ale **nie rozwiązał pytania, co się dzieje, gdy proces
wstaje po biegu, który się już skończył**, ani co z czasem, ani jak człowiek ma wyciągnąć bieg z
`NEEDS_HUMAN`. Dziś trzy dziury, jedna poprawka błędu z wczoraj i dwie rzeczy z listy „następne". Kod: [`code/`](code/).

> ⚠️ **Uczciwie na starcie:** rolę modelu gra **deterministyczna funkcja Pythona**
> `policy(historia) -> Action | Done`. To nie jest LLM ani Claude Code. Realny i uruchomiony jest
> **nadzorca**. Python 3.10.4, `python3 -B code/run_tests.py` → **24 testy OK**. Komenda `claude` jest
> w tym środowisku odrzucana przez uprawnienia (`claude --version` odrzucone także dziś) i nie
> obchodziłem tego — co robi sam Claude Code w tych sprawach, **nie jest tu zweryfikowane**.

---

## 1️⃣ 🐛 Najpierw błąd z wczoraj: urwany ogon dziennika zatruwa wszystko po sobie

W #14 napisałem, że „urwana ostatnia linia JSON nie wywraca wznowienia" i test to potwierdzał.
Test sprawdzał jednak tylko **odczyt**. Nie sprawdzał tego, co dzieje się **potem** — gdy nadzorca
dopisuje kolejne rekordy do pliku, który kończy się połową wiersza bez `\n`.

Mechanizm: `open(..., "a")` dokleja tekst do końca pliku. Pierwszy nowy rekord ląduje **w tej samej
linii** co resztka (`{"t": "intent", "step": 2, "to{"t": "intent", ...}`). Taka linia nie jest
poprawnym JSON-em. Czytnik z #14 robił `break` na pierwszej złej linii, więc **wszystko, co
zapisano po niej, było niewidoczne**. Bieg wyglądał na udany, a dziennik po nim był kaleki.

Zreprodukowałem to, zostawiając w kodzie przełącznik `Journal(repair=False)` (zachowanie z #14).
Ten sam urwany plik (2 poprawne rekordy + `{"t": "intent", "step": 2, "to` bez nowej linii), dwa tryby:

```
== 1. urwany ogon, #14 (repair=False)
  bieg: DONE; rekordow czytelnych po zakonczeniu: 2; obcieto bajtow: 0
  rodzaje: ['intent', 'result']
  kolejne wznowienie: replayed=False, wywolan narzedzi=1

== 1. urwany ogon, v2  (repair=True)
  bieg: DONE; rekordow czytelnych po zakonczeniu: 5; obcieto bajtow: 30
  rodzaje: ['intent', 'result', 'intent', 'result', 'end']
  kolejne wznowienie: replayed=True, wywolan narzedzi=0
```

W trybie z #14 bieg zakończył się `DONE`, ale po restarcie czytelne są tylko 2 rekordy — **brak
zamknięcia, brak kroku 2** — więc kolejne wznowienie wykonuje krok 2 od nowa (`wywolan narzedzi=1`).
Dla narzędzia z kluczem to dedup, dla `charge` — podwójne obciążenie.

Naprawa (`Journal._repair_tail`) ma trzy reguły, które warto zapamiętać jako wzorzec dla każdego JSONL-a:

| Stan końca pliku | Decyzja | Dlaczego |
|---|---|---|
| ostatni wiersz bez `\n` i **nie** jest poprawnym JSON-em | `truncate` do końca ostatniego dobrego wiersza (tu: 30 bajtów) | to resztka niedokończonego `write` |
| ostatni wiersz bez `\n`, ale **poprawny** JSON | dopisz tylko `\n`, nic nie wyrzucaj | zapis się udał, zabrakło tylko separatora; wyrzucenie `result` kosztuje ponowne wykonanie |
| zły wiersz **w środku** (po nim są dane) | `JournalCorrupt`, **plik nietknięty** | to nie crash, tylko uszkodzenie; zgadywanie ukryłoby je |

Naprawa następuje **leniwie, przed pierwszym zapisem** (`append`), nie przy odczycie — odczyt powinien
być bez skutków ubocznych. Test `test_clean_journal_is_not_touched` pilnuje, że zdrowy plik nie jest zmieniany.

> 💡 **Haczyk — dlaczego to ważne:** w świecie append-only crash zostawia plik w stanie, który
> *następny zapis* musi umieć znieść. „Czytnik toleruje urwany ogon" to połowa kontraktu; druga
> połowa to „pisarz nie sklei się z resztką". W .NET zobaczysz to samo przy własnym
> `StreamWriter` na pliku logu: `FileMode.Append` po crashu nie zna granicy rekordu.

---

## 2️⃣ 🔒 Zamknięcie biegu: `end` to nie log, to stan

W #14 nadzorca na końcu dopisywał `{"t":"end", ...}`, ale **nikt go nie czytał**. Uruchomienie na
dzienniku zakończonego biegu wczytywało historię i pytało model „co dalej?". Dla deterministycznej
funkcji kończy się to znowu `Done`. Dla **LLM-a** niekoniecznie: ten sam stan wejściowy może dać
tym razem inną odpowiedź — „a właśnie, jeszcze wyślę jedno powiadomienie". Wznowienie zamkniętego
biegu staje się furtką do dodatkowej, niezaplanowanej pracy.

Rozwiązanie: stany mają **znaczenie** (`FINAL` w `agentloop.py`):

| Status | Znaczenie przy wznowieniu | Kto go zdejmuje |
|---|---|---|
| `DONE`, `LOOP`, `NO_PROGRESS` | **końcowy** — odtwórz wynik z dziennika, nie wołaj modelu ani narzędzi | nikt (nowy bieg = nowy `run_id`) |
| `NEEDS_HUMAN` | końcowy **do czasu** rekordu `resolve` | człowiek (sekcja 4) |
| `BUDGET_*` | **wznawialny** — zwiększasz budżet i bieg idzie dalej | zmiana `Budget` |

Cała semantyka żyje w jednej funkcji `fold(rekordy) -> State` (kroki, wiszący `intent`, ostatni
`end`, czas). Nowy rekord `intent` **unieważnia** poprzedni `end` — to jest moment, w którym
bieg „otwiera się" po zwiększeniu budżetu. Tylko `fold` zna reguły; `run()` pyta o stan.

Realne uruchomienie (`policy_tripwire` rzuca wyjątek, gdyby ktokolwiek ją zawołał):

```
== 2. wznowienie zamknietego biegu (policy rzuca wyjatek, gdyby ja wolano)
  krok 1: run_tests ok=False proby=1 AssertionError: FAIL CS0103: name 'y' does not e
  krok 2: edit_file ok=True  proby=1 ok
  krok 3: run_tests ok=True  proby=1 PASS 12 tests
  => DONE: testy zielone (replayed=True, vt=0.00s)
  rozmiar dziennika przed/po: 739/739 B; testow uruchomionych: 2
```

Wynik wraca (`replayed=True`), dziennik nie urósł ani o bajt, `policy` nie została wywołana
(inaczej `AssertionError`), a liczba uruchomień testów została 2. A teraz **kontrola** — scenariusz
„model zmienia zdanie po `DONE`" z rekordem `end` i bez niego:

```
== 3. kontrola: model zmienia zdanie po DONE
  z rekordem 'end': wywolan notify po pierwszym biegu = 2
  drugie wznowienie (replayed=True): wywolan notify = 2
  bez rekordu 'end': status=DONE, wywolan notify = 3 (model dorzucil krok)
```

Bez `end` (zachowanie z #14) trzecie wywołanie `notify` się pojawiło, choć nikt go nie zlecał.

Dwa detale, które testy wymusiły:

- **Budżetowy `end` nie może się dublować.** Wznowienie z tym samym, nadal wyczerpanym budżetem
  nie dopisuje identycznego `end` (`test_budget_end_is_resumable_and_not_duplicated`: po dwóch
  uruchomieniach z `max_steps=2` jest 1 rekord `end`, po zwiększeniu do 4 — 2). Dziennik to nie
  licznik prób.
- `LOOP` jest końcowy z tego samego powodu co `DONE`: wznowienie pętli, która właśnie została
  ucięta, bez zmiany *czegokolwiek* odtworzyłoby ją od zera. Zmiana podejścia = nowy bieg.

> 💡 **Haczyk:** to jest idempotencja **całego biegu**, nie pojedynczego kroku. Klucz z #14 chronił
> przed podwójnym efektem kroku; `end` chroni przed tym, że ktoś (cron, retry w CI, niecierpliwy
> operator) uruchomi „to samo zadanie" jeszcze raz. W CI z `claude -p` (#4) to realny scenariusz:
> job odpalony ponownie po timeoucie nie powinien dopisywać pracy do skończonego zadania.

---

## 3️⃣ ⏱️ Czas: budżet, który przeżywa restart

W #14 uczciwie zapisałem: „czas ścienny nie jest persystowany; po wznowieniu startuje od zera".
Skutek: `max_wall=60 s` znaczy „60 s **na proces**". Agent, który co kwadrans ginie i jest
podnoszony przez supervisora (systemd, Kubernetes), ma więc budżet czasu nieskończony.

Poprawka jest mała, a lekcja duża: **każdy rekord dostaje pole `vt`** (czas wirtualny nadzorcy w
chwili zapisu — `_w()` dokłada je w jednym miejscu), a `fold` bierze maksimum. Przy starcie
`clock.now = max(clock.now, vt_z_dziennika)`. Pole `restore_clock=False` zostawiłem wyłącznie
jako kontrolę. Scenariusz: serwer cały czas odpowiada 503, `max_wall` 10 s w pierwszym biegu i 20 s
w drugim (zwiększony budżet):

```
== 4. czas scienny po wznowieniu (serwer stale 503, max_wall 10 s -> 20 s)
  restore_clock=True : bieg 1 BUDGET_WALL vt=11.22s | bieg 2 BUDGET_WALL vt=22.45s, snu w biegu 2: 11.22s w 3 przerwach
  restore_clock=False: bieg 1 BUDGET_WALL vt=11.22s | bieg 2 NO_PROGRESS vt=30.60s, snu w biegu 2: 30.60s w 9 przerwach
```

Jak to czytać (liczby z jednego uruchomienia z `seed=3`, deterministyczne):

- Z przywróconym zegarem drugi bieg startuje od 11,22 s i **zjada 11,22 s** — do wyczerpania
  20 s brakowało mu ~8,8 s, ale jeden krok z 3 przerwami backoffu nie da się przerwać w połowie,
  więc budżet jest przekraczany do granicy kroku (22,45 s). To zachowanie *kontrolne*: budżet
  jest sprawdzany **przed** krokiem, nie w jego trakcie. Identyczne 11,22 s w obu biegach to nie
  przypadek, tylko to samo ziarno (te same opóźnienia jitteru).
- Bez przywrócenia zegar zaczyna od 0 i drugi bieg „śpi" **30,60 s w 9 przerwach** (3 kroki), czyli
  ponad 2,7× więcej. Zakończył go tym razem inny bezpiecznik (`NO_PROGRESS` po 4 identycznych
  błędach) — czyli bez zegara musiał uratować budżet inny detektor.

Co **nie** jest uratowane (świadomie): czas upłynięty między ostatnim zapisem a crashem i czas
samej awarii (nieobecność procesu) nie wchodzą do `vt`. To zegar **pracy** nadzorcy, nie zegar
ścienny — dla zegara ściennego potrzebny byłby znacznik czasu z `time.time()` i decyzja, czy
przestój liczy się do budżetu. Moje `vt` odpowiada raczej „ile agent się naczekał na narzędzia".

> 💡 **Haczyk:** każda zmienna, która ma pilnować limitu, musi być częścią **stanu odtwarzanego**
> (dziennika), a nie pola obiektu. To samo dotyczyło kosztu (zrobione w #14) — czas był tym, o
> czym zapomniałem.

---

## 4️⃣ 🧑‍⚖️ `resolve`: człowiek jako rekord w dzienniku

W #14 `NEEDS_HUMAN` był ślepą uliczką. Nadzorca odmawiał zgadywania, czy `charge` zaszedł — słusznie —
ale **nie dawał człowiekowi sposobu, żeby bieg dokończyć**. Człowiek mógł tylko ręcznie edytować JSONL
albo porzucić bieg. A to ten sam błąd co z czasem: decyzja człowieka zniknęłaby poza dziennikiem.

Rozwiązanie to rekord `resolve` w **tym samym dzienniku** i jedna funkcja:

```python
resolve(journal, step=2, outcome="executed", out="charged 100 (potwierdzone w panelu platnosci)")
resolve(journal, step=2, outcome="not_executed")
```

- `executed` — człowiek sprawdził w systemie płatności: efekt zaszedł. **Musi podać obserwację**
  (`out`), bo agent musi coś zobaczyć w historii. Krok trafia do historii z `attempts=0` (konwencja:
  „wynik od człowieka, nie z wywołania").
- `not_executed` — efektu nie było; nadzorca dostaje zgodę na jednokrotne powtórzenie kroku.

`resolve` waliduje (`ResolveError`): krok musi być *wiszący* (brak wyniku), `executed` wymaga `out`,
nieznany `outcome` jest odrzucany. Po żadnym z błędów dziennik nie zmienia się (test sprawdza 0
rekordów `resolve`). Dwa realne scenariusze z `demo.py`:

```
== 5. crash after_effect na 'charge' (bez klucza)
  krok 1: fetch    ok=True  proby=1 payload
  => NEEDS_HUMAN: krok 2 (charge) mogl sie wykonac, narzedzie nie honoruje klucza idempotencji (replayed=False, vt=0.00s)
  ponowne uruchomienie bez decyzji: NEEDS_HUMAN, replayed=True, obciazenia=[100]
  czlowiek: resolve(step=2, executed)

==    po decyzji czlowieka
  krok 1: fetch    ok=True  proby=1 payload
  krok 2: charge   ok=True  proby=0 charged 100 (potwierdzone w panelu platnosci)
  => DONE: ok (replayed=False, vt=0.00s)
  obciazenia: [100]; dziennik: ['intent', 'result', 'intent', 'end', 'resolve', 'end']

== 5. crash after_intent na 'charge' (bez klucza)
  ...
  ponowne uruchomienie bez decyzji: NEEDS_HUMAN, replayed=True, obciazenia=[]
  czlowiek: resolve(step=2, not_executed)
  krok 2: charge   ok=True  proby=1 charged 100
  => DONE: ok (replayed=False, vt=0.00s)
  obciazenia: [100]; dziennik: ['intent', 'result', 'intent', 'end', 'resolve', 'result', 'end']
```

Zwróć uwagę na **obie** ścieżki dla *tego samego* objawu w dzienniku (`intent` bez `result`):
w jednej obciążenie już było (`[100]` przed decyzją), w drugiej nie (`[]`). Z samego dziennika to
nieodróżnialne — dlatego potrzebny jest człowiek (albo zapytanie do systemu zewnętrznego).
Końcowy stan w obu: dokładnie jedno obciążenie. Ponowne uruchomienie *bez* decyzji też jest
bezpieczne: `replayed=True`, żadnego nowego rekordu (test porównuje bajty pliku).

> 💡 **Haczyk — dlaczego to ważne:** audytowalność. Po miesiącu pytanie „czemu ta płatność nie
> została powtórzona?" ma odpowiedź w jednym pliku: `intent`, `end(NEEDS_HUMAN)`, `resolve(executed)`.
> Decyzja człowieka jest zdarzeniem w event store, tak jak komenda w MassTransit-owej sadze —
> nie ręczną poprawką w bazie.

---

## 5️⃣ 🔁 Dedup, który oddaje to, co zrobił za pierwszym razem

Wczoraj uczciwie zauważyłem, że po wznowieniu krok 2 miał wynik `dedup (already sent)` zamiast
oryginalnego `sent` — agent widział inną obserwację niż w biegu bez awarii. Poprawka leży po
stronie **narzędzia** (nadzorca nie zna jego wyniku): `World.notify` przechowuje pod kluczem parę
`(wiadomość, oryginalny wynik)` i dla powtórzonego klucza zwraca ten drugi element.

```
== 6. crash po efekcie; powtorka z tym samym kluczem
  krok 1: notify   ok=True  proby=1 sent
  krok 2: notify   ok=True  proby=1 sent
  => DONE: ok (replayed=False, vt=0.00s)
  wywolan notify=3, efektow=2
```

Test `test_resumed_observations_equal_uninterrupted` porównuje teraz `(akcja, ok, out)` dla biegu
z awarią i bez niej — i są identyczne (w #14 porównywałem tylko `(akcja, ok)`, stąd luka).
To ta sama zasada co w Stripe-podobnych API: powtórka z `Idempotency-Key` powinna zwrócić
**tę samą odpowiedź**, nie „już było".

---

## 6️⃣ 🧪 Co jest, a czego nie ma

**Zweryfikowane (realne uruchomienie, Python 3.10.4):**
- 24 testy `unittest` (`Ran 24 tests in 0.333s`, `OK`) i `demo.py` — cały output powyżej pochodzi z uruchomień.
- Błąd z #14 (urwany ogon) zreprodukowany i naprawiony; naprawa nie rusza zdrowego pliku ani
  uszkodzeń w środku.
- Końcowość `DONE`/`LOOP`/`NO_PROGRESS`/`NEEDS_HUMAN`, wznawialność `BUDGET_*`, brak duplikatów `end`.
- Persystencja `vt` z kontrolą bez niej; `resolve` w obu wariantach z walidacją; oryginalny wynik przy dedupie.
- Zachowania z #14 (pętla, wznowienie, `NEEDS_HUMAN`, ponowienie operacji tylko-do-odczytu) mają testy regresji.

**Niezweryfikowane / uproszczone — wprost:**
- **Żywa sesja Claude Code i `claude -p`** — `claude` odrzucone przez uprawnienia; nie wiem (tu),
  czy i jak sam harness domyka sesje, przechowuje czas albo ma odpowiednik `resolve`. Nie zakładaj,
  że to, co zbudowałem, jest tym, co robi Claude Code.
- „Model" to deterministyczny skrypt; „zmiana zdania po `DONE`" to symulacja (licznik wywołań),
  nie pomiar zachowania prawdziwego LLM-a.
- `vt` to zegar **wirtualny** nadzorcy (sumuje opóźnienia backoffu), nie czas ścienny; przestój
  procesu nie jest liczony. Liczby czasu pochodzą z jednego uruchomienia z ustalonym ziarnem.
- Naprawa ogona obsługuje jednego pisarza. Dwa procesy piszące do jednego pliku (brak blokady),
  awarie dysku, zapis niepełny w *środku* pliku (tylko wykrywany, nie naprawiany) i Windows —
  nie były testowane.
- `resolve` ufa człowiekowi: nie sprawdza, czy podana obserwacja odpowiada prawdzie.
- Sprzątanie katalogów `/tmp/prasowka-loop2-*` jest wykonywane w kodzie (`tearDown`/`rmtree`),
  ale nie potwierdziłem go listingiem (`ls` w `/tmp` odrzucone).

**Następne kroki:** kompaktowanie dziennika (snapshot stanu zamiast pełnej historii — `fold` jest
już jedynym miejscem, które trzeba by nauczyć snapshotów), detektor postępu oparty o hash drzewa
repo zamiast tekstu błędu, `permissionMode` w frontmatterze agenta i hooki w trybie headless (po
weryfikacji CLI).
