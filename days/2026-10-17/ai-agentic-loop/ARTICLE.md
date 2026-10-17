<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #19 — 17 października 2026

![AI/Agentic loop](https://img.shields.io/badge/AI_%2F_Agentic_loop-5A67D8?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10.4-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Linux](https://img.shields.io/badge/flock%282%29-Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![Testy](https://img.shields.io/badge/testy_lokalne-20%2F20_x2-brightgreen?style=for-the-badge)
![Claude CLI](https://img.shields.io/badge/claude%20CLI-niezweryfikowane-lightgrey?style=for-the-badge)

## Dwóch nadzorców, jeden dziennik: kto trzyma pióro?

</div>

---

> _"Blokada, której właściciel zginął, to nie blokada — to nagrobek z napisem „zajęte"."_

Przez sześć wydań (#13–#18) budowaliśmy nadzorcę pętli agentowej tak, by przeżył crash: dziennik
write-ahead, klucze idempotencji, snapshoty, oś zdarzeń. Wszystko to milcząco zakładało jedno:
**po dzienniku pisze dokładnie jeden proces**. A prawdziwe życie to: dwa terminale, restart
supervisora, który „jeszcze nie zdążył umrzeć", CI uruchamiające ten sam job dwa razy. Dziś
sprawdzamy, **co się dzieje, gdy dwóch nadzorców dostaje ten sam dziennik** — na prawdziwych
procesach, z powtórzeniami — oraz jak to naprawić, nie wprowadzając nowych błędów. Kod: [`code/`](code/).

> ⚠️ **Uczciwie na starcie:** rolę modelu gra **funkcja Pythona**; „efektem ubocznym" jest dopisanie
> wiersza do pliku `effects.log`. Realne są: **prawdziwe procesy** (`subprocess`, `SIGKILL`),
> **prawdziwe `flock(2)`**, `O_EXCL`, `/proc`, `os.replace`. Python 3.10.4, Linux. Liczby poniżej
> pochodzą z `python3 -B demo.py 20` (20 powtórzeń na sekcję; w sekcji 5 — 100 prób).
> `claude --version` nadal odrzucone przez środowisko, więc o `permissionMode` dalej nie piszę z pamięci.

---

## 1️⃣ 💥 Bez blokady: co psuje się naprawdę

Dwa procesy startują w tej samej chwili na tym samym `journal.jsonl`, 12 kroków, oczekiwane 12 efektów:

```
== 1. dwoch pisarzy, BEZ blokady (20 powtorzen, 12 krokow, oczekiwane efekty: 12)
  narzedzie plain: efekty 12..24 (srednio 23.4), unikalne klucze 12..12, intents w dzienniku 12..24, fold.total 12..12; bieg z duplikatem: 19/20
  narzedzie keyed: efekty 12..24 (srednio 17.0), unikalne klucze 12..12, intents w dzienniku 23..24, fold.total 12..12; bieg z duplikatem: 18/20
```

Trzy rzeczy do zapamiętania:

1. **Efekty się podwajają** (średnio 23,4 z 12). Oba procesy robią `fold` pustego dziennika i oba widzą
   „krok 1 do wykonania".
2. **Klucz idempotencji nie ratuje.** Narzędzie `keyed` sprawdza „czy ten klucz już jest w logu?" i
   dopiero potem pisze — to *check-then-write*, nieatomowe między procesami. Efektów 17,0 średnio zamiast
   12. Idempotencja z #14 chroni przed **powtórzeniem po crashu jednego procesu**, nie przed dwoma
   żywymi naraz.
3. **Dziennik kłamie spokojnie.** `fold.total` = 12 zawsze, choć wykonano do 24 efektów. Rekordy
   `intent` obu pisarzy się przeplatają, a `result` drugiego nie pasuje już do `pending` — jest ignorowany.
   Dziennik wygląda zdrowo, a audyt nie zobaczy duplikatów. (Zwróć uwagę: pojedyncze `write` rekordu w trybie
   `O_APPEND` nie rozdarło wierszy — wszystkie dzienniki dały się sparsować. Uszkodzenie bajtów nie jest tu
   problemem; problemem jest **semantyka**.)

---

## 2️⃣ 🔒 `flock` na osobnym pliku: wzorzec docelowy

`FlockLock` (plik [`joblock.py`](code/joblock.py)) to ~40 linii: `open(O_CREAT)` pliku
`journal.jsonl.lock`, `flock(LOCK_EX|LOCK_NB)` w pętli z timeoutem, metadane `{pid, start}` zapisane **po**
zdobyciu blokady (tylko diagnostyka — o własności decyduje jądro). Kluczowa kolejność w workerze:
**najpierw blokada, dopiero potem `Supervisor.run()`**, bo `run()` robi `fold` dziennika na starcie —
stan przeczytany przed blokadą jest już nieaktualny.

```
== 2. dwoch pisarzy, flock na pliku .lock (20 powtorzen)
  flock   : efekty 12..12; DONE-wykonane 20, DONE-odtworzone 20, BUSY(75) 0; najdluzsze czekanie 107 ms
  flock-nb: efekty 12..12; DONE-wykonane 20, DONE-odtworzone 0, BUSY(75) 20; najdluzsze czekanie 0 ms
```

- **Tryb blokujący:** drugi proces czeka, potem składa dziennik, widzi `DONE` i **odtwarza wynik** zamiast
  powtarzać pracę (20/20). Efekty: dokładnie 12 w każdym z 20 biegów.
- **Tryb nieblokujący:** przegrany natychmiast kończy się kodem `75` (`EX_TEMPFAIL`) z informacją, kto
  trzyma pióro — to jest zachowanie, które chcesz w CI („ktoś już to robi").

### Kill -9 właściciela

Najważniejszy test dla blokady: właściciel umiera **brutalnie** w losowym momencie (`SIGKILL` po 2–10 efektach),
drugi proces startuje od razu.

```
== 3. kill -9 wlasciciela w losowym momencie, przejecie przez drugi proces (20 powtorzen)
  narzedzie keyed: statusy B {'DONE': 20}; wiszacy intent w chwili smierci A: 2/20; efekty (lacznie, unikalne) [(12, 12)]; sredni czas B 0.16 s
  narzedzie plain: statusy B {'NEEDS_HUMAN': 8, 'DONE': 12}; wiszacy intent w chwili smierci A: 8/20; efekty (lacznie, unikalne) [(3, 3), (5, 5), (8, 8), (9, 9), (12, 12)]; sredni czas B 0.14 s
```

Jądro zwolniło blokadę w chwili śmierci procesu, B przejął dziennik bez czekania (średni czas B 0,16 s obejmuje start
interpretera i dokończenie pracy; nie rozbijałem go) i **efekty = dokładnie 12 unikalnych w 20/20 biegów** dla narzędzia honorującego klucz.
Dla narzędzia bez klucza (`plain`) nadzorca z #14 robi to, co obiecał: gdy kill trafia w okno
„intent zapisany, wynik nie" (8/20), odmawia zgadywania i oddaje `NEEDS_HUMAN` — **nigdy** nie wykonał kroku
dwa razy (sprawdzone: efekty = unikalne klucze w każdym biegu).

---

## 3️⃣ 🪦 Plik-zamek `O_EXCL`: martwy zamek i wyścig przejęcia

Wielu programistów .NET (i nie tylko) sięga po „plik-zamek": utwórz `x.lock` z `O_EXCL`, usuń na końcu.
Atomowe jest tylko tworzenie. Zmierzone:

```
== 4. martwy zamek: O_EXCL bez/ze sprawdzaniem wlasciciela vs flock
  po kill -9: plik zamka zostal, pid w nim 441793, zyje? False
  B (excl, bez sprawdzania, 1,5 s): busy=True rc=75 po 1.502 s
  C (excl-stale): status=DONE resumed_from=3 efekty=12 unikalne=12
  B (flock): status=DONE czekal 0 ms, efekty=12
```

Po `kill -9` plik zostaje, a B czeka w nieskończoność (tu: do timeoutu 1,5 s). Naprawa „sprawdź, czy PID z pliku
żyje; jak nie — usuń i weź" działa (C), ale to **nowa klasa błędów**:

> 🐛 **Błąd znaleziony w trakcie — wyścig przejęcia martwego zamka.** Dwóch kontrolerów jednocześnie ocenia
> zamek jako martwy. A: `unlink` + `create` (ma zamek). B: `unlink` — **kasuje świeży zamek A** — `create`
> (też „ma zamek"). Obaj w sekcji krytycznej.

```
== 5. wyscig przejecia martwego zamka (100 prob, 2 procesy, zamek startuje jako martwy)
  O_EXCL + stale, naturalne okno                : obaj w sekcji naraz 5/100, zgubiona aktualizacja licznika 5/100
  O_EXCL + stale, okno 10 ms (haczyk testowy)   : obaj w sekcji naraz 13/100, zgubiona aktualizacja licznika 13/100
  flock                                         : obaj w sekcji naraz 0/100, zgubiona aktualizacja licznika 0/100
```

Pierwszego wiersza nie musiałem sztucznie poszerzać: **5 na 100 prób** (naturalne okno to mikrosekundy
między odczytem metadanych a `unlink`) kończy się dwoma właścicielami i **zgubioną aktualizacją** (licznik
`read → sleep → write+1` daje 1 zamiast 2). Drugi wiersz — z wstrzykniętym 10 ms opóźnieniem — to haczyk
testowy, tylko żeby zobaczyć rząd większy. `flock`: 0/100, bo „czy właściciel żyje" nie jest osobnym krokiem —
rozstrzyga jądro, atomowo.

Dwie poprawki na drodze, które i tak warto znać:

| Pułapka | Zmierzone |
|---|---|
| `kill(pid, 0)` po ponownym użyciu PID-u mówi „żyje" | `pid_alive(pid)`=True, a z czasem startu z `/proc/<pid>/stat` (pole 22) cudzy start → `False` (**symulacja** reuse — prawdziwego nie wywołałem) |
| zombie (dziecko niezebrane `wait()`) | `/proc/<pid>` istnieje, `kill(0)` „widzi", a stan `Z` → liczymy jako martwy |

---

## 4️⃣ 🧨 Cztery haczyki `flock`, które wyszły w pomiarach

> 💡 **Haczyk 1 — nie blokuj samego dziennika.** `compact()` z #17 kończy się `os.replace(tmp, journal)`, a
> `flock` siedzi na **i-węźle**, nie na nazwie. Po podmianie nowy proces otwiera nowy plik i dostaje zamek:
>
> ```
> flock na journal.jsonl        : po os.replace -> DRUGI TEZ DOSTAL ZAMEK (dwoch wlascicieli)
> flock na journal.jsonl.lock   : po os.replace -> drugi odrzucony
> ```
>
> Dlatego osobny plik `.lock`.

> 💡 **Haczyk 2 — nie usuwaj pliku `.lock` przy zwalnianiu.** B otwiera stary plik i czeka; A robi `unlink` i
> zamyka; B dostaje zamek na **osieroconym** i-węźle; C tworzy nowy plik pod tą samą nazwą i też dostaje zamek.
> Odtworzone deterministycznie: „B i C trzymają zamek jednocześnie: tak". Plik `.lock` zostaje na zawsze (kilkadziesiąt
> bajtów metadanych).

> 💡 **Haczyk 3 — dziecko po `fork()` dziedziczy zamek.** Zamek należy do *opisu otwartego pliku*, nie do
> procesu. Jeśli właściciel zrobi `os.fork()` (albo agent uruchomi narzędzie, które zostaje w tle — serwer
> deweloperski, `dotnet watch`), a właściciel zginie, **zamek trzyma dziecko**:
>
> ```
> wlasciciel zabity, dziecko (fork) zyje: ZAMEK DALEJ ZAJETY; w metadanych pid 442802, zyje? False
> wlasciciel zabity, dziecko (popen) zyje: zamek wolny
> ```
>
> Metadane mówią „wlasciciel martwy", a jądro mówi „zajęte" — **ufaj jądru**, nie metadanym. `subprocess.Popen`
> jest bezpieczny, bo Python otwiera `fd` jako nieodziedziczalny (PEP 446) i domyślnie `close_fds=True`.
> Uwaga: to dotyczy kodu, który sam robi `fork`/`pass_fds`; innych języków (np. .NET `Process.Start`) nie testowałem.

> 💡 **Haczyk 4 — `flock` to blokada doradcza i lokalna.** Chroni tylko przed procesami, które o nią pytają;
> proces z `echo >> journal.jsonl` ją ignoruje. Nie testowałem NFS ani Windows (tam inna semantyka).

### 🐛 Drugi błąd: wspólny `journal.jsonl.tmp` wywraca nadzorcę

Przy dwóch pisarzach i `compact_every=4` (kompaktowanie z #17) bez blokady dostajemy nie tylko duplikaty,
ale **wyjątek w połowie procesów**:

```
== 9. dwoch pisarzy + kompaktowanie (compact_every=4), 20 powtorzen, narzedzie keyed
  none : efekty 20..24 (oczekiwane 20); procesy zakonczone wyjatkiem 20/40; bieg poprawny (20 krokow w dzienniku i 20 efektow) 2/20
         20x FileNotFoundError: [Errno 2] No such file or directory: '/tmp/prasowka
  flock: efekty 20..20 (oczekiwane 20); procesy zakonczone wyjatkiem 0/40; bieg poprawny (20 krokow w dzienniku i 20 efektow) 20/20
```

Mechanizm: oba procesy piszą do **tej samej nazwy** `journal.jsonl.tmp`; pierwszy `os.replace` przenosi
plik, drugi nie ma już czego przenosić. Padło 20 z 40 procesów (wszystkie na
`FileNotFoundError`; nie liczyłem, czy po jednym na bieg); tylko 2/20 biegów skończyło się poprawnie. Z blokadą: 0 wyjątków, 20/20 poprawnych. Nie
zmieniałem `compact` — blokada jest warunkiem jego poprawności (alternatywa, unikalna nazwa `.tmp` z PID,
usunęłaby wyjątek, ale **nie** utraconych zapisów między odczytem a podmianą; tego nie mierzyłem osobno).

---

## 5️⃣ 🧪 Co jest, a czego nie ma

**Zweryfikowane (realne uruchomienia, Python 3.10.4, Linux):**
- `python3 -B run_tests.py`: **20 testów OK** (`Ran 20 tests in 50.7s`, drugie uruchomienie `50.9s`, też OK);
  testy są statystyczne tam, gdzie wyścig jest losowy (np. wyścig przejęcia: ≥1 trafienie w 40 próbach,
  z 3 zawodnikami i 10 ms oknem), a deterministyczne tam, gdzie się da (i-węzeł, `unlink`, `fork`).
- `python3 -B demo.py 20` — źródło wszystkich liczb; zmieniają się między uruchomieniami (pierwsze
  uruchomienie z 5 powtórzeniami dało np. 0/25 wyścigów w naturalnym oknie, 20 powtórzeń: 5/100) — to jest
  rzecz **losowa**, podaję częstość, nie stałą.
- Po testach w `/tmp` nie zostają katalogi `prasowka-lock-*` (test `TestZCleanup`), w `code/` brak `__pycache__`.

**Niezweryfikowane / uproszczone — wprost:**
- **Żywa sesja Claude Code, `claude -p`, `permissionMode`, hooki headless** — `claude` odrzucane; nic nie
  twierdzę o ich zachowaniu przy dwóch sesjach na jednym repo.
- Model to funkcja; „efekt uboczny" to wiersz w pliku. Prawdziwy LLM wznawiający po przejęciu nie był testowany.
- Linux, lokalny system plików, jedna maszyna. **NFS, Windows (`LockFileEx`), macOS, kontenery z różnymi
  przestrzeniami PID** — nie. Reuse PID-u tylko symulowany.
- Sprawdzałem 2 procesy (3 w teście wyścigu); nie testowałem dziesiątek pisarzy ani **sprawiedliwości**
  (głodzenia) przy `flock` — kolejka oczekujących nie jest FIFO.
- Brak dzierżawy z odnawianiem (lease/heartbeat) i „fencing tokenów": zawieszony (`SIGSTOP`), ale żywy właściciel
  trzyma zamek bez końca — nie mierzyłem tego scenariusza. To następny, trudniejszy krok.
- Okno `NEEDS_HUMAN` nadal wymaga człowieka — blokada go nie usuwa, tylko zapobiega *drugiemu* pisarzowi.

**Następne kroki:** dzierżawa z heartbeatem i fencing token dla zawieszonego właściciela; `permissionMode` po
weryfikacji CLI; strumieniowe składanie osi z #18.
