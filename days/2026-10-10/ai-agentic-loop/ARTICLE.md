<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #17 — 10 października 2026

![AI/Agentic loop](https://img.shields.io/badge/AI_%2F_Agentic_loop-5A67D8?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10.4-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Testy](https://img.shields.io/badge/testy_lokalne-41%2F41-brightgreen?style=for-the-badge)
![Claude CLI](https://img.shields.io/badge/claude%20CLI-niezweryfikowane-lightgrey?style=for-the-badge)

## Postęp mierzy się w kodzie, nie w tekście błędu — i pamięć agenta nie może rosnąć bez końca

</div>

---

> _"Agent, który po raz piąty uruchamia testy na tym samym kodzie, nie jest uparty. Jest po prostu
> nieobserwowany."_

W #14 nadzorca dostał detektory zapętlenia opartych o **tekst** (ten sam odcisk akcji, ten sam błąd),
a w #15 dziennik write-ahead dostał zamknięcie biegu i zegar. Zostały dwie dziury z listy
„następne": (1) **jak poznać brak postępu, gdy tekst się zmienia, a kod nie**, oraz (2) **dziennik,
który po 500 krokach jest już zbyt duży, żeby go czytać przy każdym wznowieniu**. Dziś jedno i drugie.
Kod: [`code/`](code/).

> ⚠️ **Uczciwie na starcie:** rolę modelu gra **deterministyczna funkcja Pythona**
> `policy(historia) -> Action | Done`. To nie jest LLM ani Claude Code. Realny i uruchomiony jest
> **nadzorca**, a repo, którego hash liczymy, to **prawdziwy katalog na dysku** (plik `Foo.cs` z
> błędem i `notes.txt`; „testy" to funkcja sprawdzająca, czy w `Foo.cs` jest słowo `fixed`, a nie
> `dotnet test`). Python 3.10.4, `python3 -B code/run_tests.py` → **41 testów OK**. Komenda `claude`
> jest w tym środowisku odrzucana przez uprawnienia (`claude --version` odrzucone także dziś) i nie
> obchodziłem tego. Dlatego **nie ma** dziś trzeciego punktu z listy („`permissionMode` w
> frontmatterze agenta i hooki headless") — nie umiem go uczciwie zweryfikować (patrz sekcja 5).

---

## 1️⃣ 🌳 Dlaczego detektor oparty o tekst jest ślepy

Detektory z #14 patrzą na odcisk akcji (`narzędzie + argumenty`) i na „sygnaturę błędu" (pierwsza
linia, cyfry zamienione na `N`). Są tanie i łapią dwa klasyczne przypadki. Ale model potrafi
zapętlić się tak, że **żaden z nich nie zadziała**:

- w argumentach kolejnych wywołań jest coś zmiennego (numer próby, „notatka", timestamp) — odciski
  akcji są różne, więc `LOOP_EXACT` i `LOOP_CYCLE` milczą;
- runner testów dopisuje do błędu identyfikator uruchomienia albo ścieżkę pliku `.trx` z datą —
  pierwsza linia błędu jest za każdym razem inna, więc `NO_PROGRESS` milczy.

Zbudowałem dwa takie zachowania (obie „modele" są deterministyczne, stworzone pod ten przypadek —
to **konstrukcja**, nie pomiar tego, jak zachowuje się prawdziwy LLM):

- `policy_spin_same_tree`: na zmianę `run_tests` i `read_file` z rosnącym polem `n`; **kod nigdy
  się nie zmienia**;
- `policy_oscillate`: przełącza `Foo.cs` między wersjami `v1` i `v2` (obie nie działają), z polem
  `note: "proba k"`, więc odciski akcji są różne.

Realny output `demo.py`, ten sam nadzorca z wyłączonym i włączonym detektorem drzewa:

```
== 2. 'kreci sie': testy na tym samym kodzie
  detektor drzewa WYL: testow uruchomionych=10
    => BUDGET_STEPS: limit 20 krokow
       krokow lacznie=20, w oknie=20, koszt=345, replayed=False
  detektor drzewa WL: testow uruchomionych=3
    => NO_PROGRESS: TREE_STALL: weryfikacja padla 3x na identycznym drzewie ffd943ff (...)
       krokow lacznie=5, w oknie=5, koszt=89, replayed=False

== 3. oscylacja v1 <-> v2 (obie wersje nie dzialaja)
  detektor drzewa WYL: testow uruchomionych=10
    => BUDGET_STEPS: limit 20 krokow
       krokow lacznie=20, w oknie=20, koszt=430, replayed=False
  detektor drzewa WL: testow uruchomionych=5
    => NO_PROGRESS: TREE_STALL: weryfikacja padla 3x na identycznym drzewie 3d78334b (...)
       krokow lacznie=10, w oknie=10, koszt=215, replayed=False
```

Bez detektora drzewa agent spala cały budżet 20 kroków (10 uruchomień testów); z nim kończy po 5
(3 testy) i po 10 krokach (5 testów, bo drzewo `v1` wraca po raz trzeci). Koszt (`len/4`)
spada z 345 do 89 i z 430 do 215.

### Jak to działa

`tree_hash(root)` to SHA-256 z posortowanej listy `ścieżka względna + długość + bajty` wszystkich
plików, **z pominięciem** `.git`, `bin`, `obj`, `__pycache__`, `node_modules`. Nadzorca dostaje go
jako `observer` (funkcja `() -> str`) i woła po każdym kroku. Kluczowa reguła jest węższa, niż
by się wydawało:

> **Liczymy porażki weryfikacji na danym hashu drzewa**, nie „kroki bez zmiany drzewa".

Narzędzie ma flagę `verifies=True` (u nas `run_tests`). Gdy weryfikacja pada, nadzorca zapisuje
w rekordzie `result` pole `tf` = hash drzewa, na którym padła. `fold` zlicza `tf` w słowniku
`tree_fail`. Gdy ten sam hash ma `tree_repeat` (domyślnie 3) porażek → `TREE_STALL`
(status `NO_PROGRESS`). Dlaczego tak, a nie prościej? Sprawdziłem to na drugim kryterium:

```
== 4. brak falszywych alarmow (drzewo-detektor WL, naiwny 'drzewo bez zmian w oknie 4 krokow' obok)
  progres (3 proby naprawy): DONE (testy zielone); naiwny detektor by zadzialal: False
  rozeznanie: 8 odczytow, potem naprawa: DONE (naprawione po rozeznaniu); naiwny detektor by zadzialal: True
  hashe drzewa po kolejnych krokach rozeznania: ['ffd943ff', ... x8, '950301f8', '950301f8']
```

Agent, który najpierw przez 8 kroków czyta pliki (drzewo stoi w miejscu, bo **czytanie nie zmienia
repo**), a potem naprawia i przechodzi testy, jest zupełnie zdrowy. Naiwny detektor „drzewo bez
zmian w oknie 4 kroków" by go zabił (`True` powyżej). Detektor zliczający porażki weryfikacji na
tym samym drzewie go nie rusza, bo żadnej weryfikacji w tym czasie nie było.

Co jeszcze mówi tabela testów (`TestTreeHash`):

| Zmiana | Hash |
|---|---|
| zapis do `obj/` lub `bin/` (artefakt buildu) | ten sam |
| zmiana `mtime` pliku | ten sam |
| jedna spacja w `Foo.cs` | **inny** |
| powrót do poprzedniej treści | **wraca do pierwotnego** (to wykrywa oscylację) |
| zmiana nazwy pliku (ta sama treść) | inny |
| nowy plik (nieśledzony przez gita) | inny |
| pusty katalog | ten sam |

Hash jest też **zapisywany w dzienniku** (`th`, a `tf` tylko przy porażce weryfikacji), więc
licznik przeżywa restart: test `test_tree_counter_survives_crash_and_restart` zabija proces po
`intent` kroku 3 i wznowienie kończy się tym samym `TREE_STALL` po 5 krokach i 3 testach.

> 💡 **Haczyk — dlaczego to ważne:** tekst jest tym, co model **opowiada**, a drzewo jest tym, co
> model **zrobił**. Model nie kontroluje drugiego tak łatwo jak pierwszego. W praktyce jest to
> ten sam pomysł co `git diff --stat` jako bramka w CI: pytasz „czy cokolwiek się zmieniło w
> treści", a nie „czy powiedziałeś, że się zmieniło". Pułapka jest ta sama co w Gradle/MSBuild:
> **liczyć treść, nie `mtime`, i wyrzucać `obj/`** — inaczej każdy build „zmienia" drzewo i detektor
> nigdy się nie odpali.

---

## 2️⃣ 📸 Snapshoty stanu zamiast pełnej historii

Dziennik z #14/#15 rośnie o 2 rekordy na krok (`intent` + `result`) plus `end`. Przy każdym
wznowieniu `fold` czyta i składa **całość**. W moim syntetycznym biegu 30 kroków to 61 rekordów i
15 kB (wyniki `read_file` mają ~300 znaków). Przy agencie, który robi tysiąc kroków, to
dwa problemy: czas wznowienia i — co ważniejsze — to, że **historia przekazywana do modelu rośnie
bez końca** (do tego wrócimy w sekcji 3).

Rozwiązanie jest dwuczęściowe i obie części mieszkają w jednym miejscu — `fold`:

1. **`Summary`** — to, co detektory i budżet wiedzą o przeszłości: liczba kroków `total`, `cost`,
   ostatnie `WINDOW=12` odcisków i sygnatur błędów, słownik `tree_fail`. Aktualizowane przez `add()`
   przy każdym kroku, niezależnie od tego, czy sam krok jest jeszcze w oknie.
2. **Rekord `snapshot`** — zawiera `Summary`, **ogon `keep` ostatnich kroków w pełnej postaci**,
   wiszący `intent` (`pending`), ostatni `end`, flagę `approved` i `vt`. `fold` po napotkaniu
   `snapshot` po prostu **podmienia stan** i czyta dalej.

`compact(journal, keep)` zastępuje dziennik jednym rekordem `snapshot`. Kolejność operacji ma
znaczenie, bo ma być bezpieczna na crash w dowolnym punkcie:

```
1. zapisz KOMPLETNY plik journal.jsonl.tmp + fsync
2. (opcjonalnie) twarde dowiązanie starego dziennika jako journal.jsonl.archive-NNNNN
3. os.replace(tmp, journal.jsonl)        # atomowe
```

Nadzorca robi to sam, gdy okno kroków urośnie do `compact_every`, i **odczytuje okno z dysku
po kompaktowaniu** — dzięki temu proces w pamięci widzi dokładnie to, co zobaczyłby po restarcie.

```
== 5. kompaktowanie: 30 krokow, compact_every=8, keep=3
  bez kompaktowania : DONE, krokow=30, koszt=1900, dziennik=15007 B / 61 rekordow, efektow notify=15
  z kompaktowaniem  : DONE, krokow=30, koszt=1900, dziennik=2555 B / 6 rekordow, efektow notify=15
  rodzaje rekordow  : ['snapshot', 'intent', 'result', 'intent', 'result', 'end']
  stan z dziennika  : total=30, okno=[26, 27, 28, 29, 30]
```

Ten sam wynik (`DONE`, 30 kroków, koszt 1900, 15 efektów), dziennik 5,9× mniejszy. Okno ma 5
kroków, nie 3, bo kompaktowanie następuje co `compact_every - keep` kroków (tu: po kroku 28 zostają
26–28, potem dochodzą 29 i 30).

### Crash w środku kompaktowania

Dwa punkty, w których proces ginie (hook `crash_hook`):

```
== 6. crash W TRAKCIE kompaktowania (compact_every=8, keep=3)
  crash po 'compact_tmp_written': plik .tmp zostal=True, rekordow po crashu=16 (pierwszy: intent)
    wznowienie: DONE, krokow=30, koszt=1900, efektow notify=15
  crash po 'compact_replaced': plik .tmp zostal=False, rekordow po crashu=1 (pierwszy: snapshot)
    wznowienie: DONE, krokow=30, koszt=1900, efektow notify=15
```

Po pierwszym crashu stary dziennik jest **nietknięty i kompletny** (16 rekordów, bez `snapshot`),
a osierocony `.tmp` jest ignorowany przez odczyt i nadpisany przy następnym kompaktowaniu
(`test_stale_tmp_does_not_leak_into_state`). Po drugim — nowy plik jest kompletny. W obu wypadkach
wynik końcowy jest identyczny z biegiem bez awarii.

### Detektory przeżywają snapshot

Test, który mnie interesował najbardziej: czy po kompaktowaniu do `keep=1` nadzorca wciąż „pamięta"
porażki testów na tym drzewie, skoro kroki, które je wywołały, zniknęły z okna?

```
== 7. detektory przezywaja kompaktowanie (tree_fail w snapshocie), compact_every=3 keep=1
  => NO_PROGRESS: TREE_STALL: weryfikacja padla 3x na identycznym drzewie ffd943ff (...)
     krokow lacznie=5, w oknie=3, koszt=89, replayed=False
  dziennik: ['snapshot', 'intent', 'result', 'intent', 'result', 'end']
```

Tak. Ten sam `TREE_STALL` po tych samych 5 krokach co bez kompaktowania (liczy `Summary`, nie okno).
Analogicznie testy: `LOOP_EXACT` po 3 krokach mimo `compact_every=2, keep=1`, `BUDGET_STEPS` przy
12 krokach z kompaktowaniem co 4, `NEEDS_HUMAN` + `resolve` po kompaktowaniu, wiszący `intent`
(kompaktowanie w środku kroku 6) i powtórka zamkniętego biegu bez wołania `policy`.

> 💡 **Haczyk — dlaczego to ważne:** **snapshot jest poprawny tylko wtedy, gdy każdy, kto czyta
> stan, czyta go przez `fold`.** Wszystkie reguły (co to `pending`, kiedy `end` unieważniony) żyją w
> jednej funkcji, więc nauczenie jej jednego nowego rekordu wystarczyło. Gdyby `run()` miał własną
> kopię logiki, snapshot rozjechałby dwie interpretacje. To jest ten sam argument, co za
> `Aggregate`/`Apply` w event sourcingu: zdarzenia i migawka muszą dawać **ten sam** stan, a
> test (`test_offline_compact_preserves_fold`) porównuje `fold` przed i po.

---

## 3️⃣ ⚠️ Cena snapshotu: dwie rzeczy, które znikają

**Po pierwsze: model nie widzi starych kroków.** `History` (lista, którą dostaje `policy`) po
kompaktowaniu to tylko ogon; pełną liczbę kroków niesie pole `.total`. „Model", którego decyzja
zależy od pierwszego kroku, zachowuje się inaczej:

```
== 9. granica: 'model', ktory potrzebuje starej historii
  compact_every=0: pierwszy widoczny krok: 1
  compact_every=3: pierwszy widoczny krok: 5
```

To nie jest błąd, tylko **kontrakt**: kompaktowanie to decyzja o tym, co model *może* zapomnieć.
W prawdziwym agencie na to miejsce trafia streszczenie lub plik handoff (rubryka o kontekście, #15);
tu jest zero streszczenia — dlatego testowy „model" musi opierać się na liczniku, a nie na starych
krokach. Bez tej decyzji kompaktowanie bez cichej utraty jest niemożliwe.

**Po drugie: ślad audytowy.** Rekordy `intent`/`result`/`resolve` starszych kroków przestają
istnieć w głównym pliku. Jeśli „czemu ta płatność nie została powtórzona" ma mieć odpowiedź po
miesiącu (#15), trzeba zachować starą wersję. Opcja `archive=True` robi twarde dowiązanie
(`os.link`) przed podmianą — nie kopiuje bajtów:

```
== 8. archiwum przed kompaktowaniem (audyt)
  pliki: ['journal.jsonl', 'journal.jsonl.archive-00010', 'journal.jsonl.archive-00018', 'journal.jsonl.archive-00026']
  najstarsze archiwum: 20 rekordow, rodzaje: ['intent', 'result'], wynikow krokow: 10
```

Zwróć uwagę, że to **kilka segmentów**, nie jeden plik: każde archiwum zawiera zdarzenia od
poprzedniego snapshotu. Ich złożenie to osobna operacja, której nie napisałem.

Dwie bramki bezpieczeństwa, które testy pilnują: kompaktowanie dziennika z uszkodzeniem **w środku**
rzuca `JournalCorrupt` i **nie zmienia pliku** (nie „naprawiamy" czegoś, czego nie rozumiemy), a
`compact_keep >= compact_every` jest odrzucane w konstruktorze (kompaktowanie niczego by nie skracało).

---

## 4️⃣ 🧪 Co jest, a czego nie ma

**Zweryfikowane (realne uruchomienie, Python 3.10.4):**
- 41 testów `unittest` (`Ran 41 tests in 3.092s`, `OK`) i `demo.py` — cały output powyżej pochodzi
  z uruchomień (jedyna edycja: skrócone `(...)` w komunikatach i `...x8` w liście hashy).
- `tree_hash` na prawdziwym katalogu: ignorowanie `obj/`/`bin/`/`.git`, `mtime`, powrót do treści.
- `TREE_STALL` w dwóch scenariuszach, w których detektory tekstowe milczą; brak fałszywych alarmów
  w scenariuszach „progres" i „rozeznanie".
- Licznik porażek przeżywa restart i kompaktowanie; kompaktowanie jest idempotentne, odporne na crash
  w dwóch punktach, i nie zmienia wyniku biegu (status, liczba kroków, koszt, efekty).
- Regresje: wznowienie po crashu z dedupem, `NEEDS_HUMAN`, `resolve`, naprawa urwanego ogona po snapshocie.

**Niezweryfikowane / uproszczone — wprost:**
- **Żywa sesja Claude Code i `claude -p`** — `claude --version` odrzucone przez uprawnienia; nie
  próbowałem dalej. Nie wiem, czy i jak Claude Code sam wykrywa brak postępu lub kompaktuje
  kontekst. Nie zakładaj, że to, co zbudowałem, jest tym, co robi harness.
- **`permissionMode` w frontmatterze agenta i hooki headless** — bez CLI nie sprawdziłem ani nazw
  pól, ani dopuszczalnych wartości, ani kształtu wejścia hooków w `-p`. Nie piszę o nich niczego z
  pamięci. Zostają na następne wydanie.
- Rolę modelu gra funkcja; oba „zapętlone" modele są **zbudowane** tak, by ominąć detektory tekstowe.
  Nie mam danych, jak często prawdziwy LLM robi to samo.
- „Testy" to funkcja `"fixed" in Foo.cs`, nie `dotnet test`. **Flaky testy**: weryfikacja, która
  raz pada, raz przechodzi na tym samym drzewie, jest dokładnie tym, czego `tree_repeat=3` ma
  nie karać zbyt szybko — progi (3 porażki, okno 12) są heurystyką, nie wynikiem pomiaru.
- Hash liczy **całe drzewo** (w jednym wątku, `os.walk`); na dużym repo będzie wolny. Nie mierzyłem.
  Alternatywa, np. `git write-tree`/`git diff | sha256`, nie była sprawdzana.
- `ignore` jest stałą listą katalogów; plik generowany poza nimi (np. log z timestampem w korzeniu)
  zawsze „zmieni" drzewo i wyłączy detektor.
- Kompaktowanie obsługuje jednego pisarza; nie testowałem równoległości, awarii dysku ani Windows
  (`os.link`, `os.replace` i `fsync` katalogu mają tam inną semantykę — nie sprawdzano).
- Złożenie segmentów archiwum w jedną oś zdarzeń nie jest zaimplementowane.
- Sprzątanie `/tmp/prasowka-loop3-*` odbywa się w kodzie (`rmtree`), ale potwierdzenie listingiem
  (`find /tmp`) zostało odrzucone przez uprawnienia.

**Następne kroki:** streszczenie zamiast „pustego" okna po kompaktowaniu (to, co `History`
oddaje modelowi), złożenie archiwów w jedną oś zdarzeń, `permissionMode` i hooki headless — po
weryfikacji CLI.
