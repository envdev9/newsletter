<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #25 — 18 października 2026

![AI/Agentic loop](https://img.shields.io/badge/AI_%2F_Agentic_loop-5A67D8?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10.4-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Linux](https://img.shields.io/badge/SIGSTOP%20%2B%20flock-Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![Testy](https://img.shields.io/badge/testy_lokalne-14%2F14_x2-brightgreen?style=for-the-badge)
![Claude CLI](https://img.shields.io/badge/claude%20CLI-niezweryfikowane-lightgrey?style=for-the-badge)

## Zamrożony właściciel: dzierżawa, heartbeat i token ogrodzeniowy

</div>

---

> _"Blokada mówi: «ja tu jestem». Dzierżawa mówi: «byłem tu jeszcze przed chwilą». Token mówi: «a teraz sprawdź, czy to w ogóle ja»."_

Wczoraj (#24) `flock` rozwiązał problem dwóch nadzorców: jądro zwalnia blokadę, gdy właściciel **umiera**.
Zostawiliśmy sobie jedno pytanie bez odpowiedzi: co, gdy właściciel **nie umiera, tylko zamarza**? Agent
czeka na odpowiedź modelu, proces dostaje `SIGSTOP`, maszyna wirtualna zostaje wstrzymana, długa pauza GC,
zawieszony na dyskowym I/O `dotnet build`. Dla jądra on żyje, więc blokada trzyma. Dziś: **dlaczego
`flock` jest tu zły**, co daje dzierżawa z heartbeatem, i dlaczego **sama dzierżawa nie wystarcza** — potrzebny
jest jeszcze token ogrodzeniowy sprawdzany przez *zasób*. Wszystko na prawdziwych procesach. Kod: [`code/`](code/).

> ⚠️ **Uczciwie na starcie:** rolę agenta gra skrypt Pythona (`holder.py`), „praca" to `sleep`, „efekt" to wiersz
> w pliku `work.log`. Realne są: **procesy, `SIGSTOP`/`SIGCONT`/`SIGKILL`, `flock(2)`, `os.replace`, wątek heartbeatu**.
> Python 3.10.4, Linux. `claude --version` nadal nie sprawdzałem — niczego o `permissionMode` nie twierdzę.
> Liczby z `python3 -B demo.py 10` (jedno uruchomienie, czasy zależą od maszyny).

---

## 1️⃣ 🧊 Zamrożony właściciel trzyma `flock` bez końca

Proces A bierze `flock`, dostaje `SIGSTOP`. Proces B próbuje przez 2 sekundy. Obok to samo z dzierżawą (TTL 0,6 s):

```
== 2. zamrozony ZYWY wlasciciel: flock vs dzierzawa
  flock  : got=False po 2.002 s oczekiwania (timeout 2 s)
  dzierz.: B busy=False token=2 czekal 0.542 s
```

`flock` nigdy nie odda — zamarznięty proces ma otwarty deskryptor. B może czekać godzinami. Dzierżawa wygasa po TTL,
bo wymaga **ciągłego odnawiania**, a zamrożony proces (razem z wątkiem heartbeatu) odnawiać przestaje.

> 💡 **Dlaczego to ważne:** w pętli agentowej „zawieszony" jest *normalnym* stanem — wywołanie modelu trwa minuty,
> narzędzie wisi. Blokada bez terminu ważności zamienia jedno zawieszenie w zatrzymanie całej floty.

## 2️⃣ ⏱️ Dzierżawa: stan, token, heartbeat

[`lease.py`](code/lease.py), ~100 linii. Stan to plik JSON `{owner, token, expires}`. Zmiany są transakcjami
pod krótkim `flock` na osobnym pliku `.mx` (to nadal `flock`, ale jako **mutex CAS na mikrosekundy**, nie jako
dzierżawa). Reguły:

- `try_acquire`: sukces, gdy brak właściciela **albo `expires` minął**; każde przejęcie zwiększa `token` o 1.
- `renew(owner, token)`: tylko gdy owner i token się zgadzają **i dzierżawa jeszcze nie wygasła** (po wygaśnięciu — porażka, nie „reaktywacja").
- `release`: zeruje właściciela, ale **nie cofa licznika** tokenu (test: kolejne przejęcia dają 1, 2, 3).
- `Heartbeat`: wątek odnawia co `ttl/3`; nieudane odnowienie ustawia `lost`.

Heartbeat odróżnia „żywy, ale pracuje długo" od „martwy lub zamrożony":

```
== 3. zywy wlasciciel, dluga praca 2.0 s przy ttl 0.6 s; probe B po 1.5 s
  heartbeat=True : B busy=True; A odnowien=9, A hb_lost=False, A events=['wrote:0']
  heartbeat=False: B busy=False; A odnowien=None, A hb_lost=False, A events=['wrote:0']
```

Z heartbeatem (9 odnowień w 2 s) B odbija się od ściany. Bez niego dzierżawa po 0,6 s wygasła i B **wszedł w środek
cudzej pracy** — i A nawet o tym nie wie (`hb_lost=False`, bo nie ma kto sprawdzić). Wniosek: **TTL musi być
dłuższy niż interwał heartbeatu z zapasem, a heartbeat musi żyć niezależnie od pracy** (wątek, nie ta sama pętla).

## 3️⃣ 💸 Cena: wolniejsze przejęcie

Dzierżawa nie jest darmowa. Czas od `SIGKILL` właściciela do zdobycia zasobu przez następcę (10 prób):

```
== 4. czas od SIGKILL do przejecia (10 prob, ttl 0.6 s)
  flock: min 0.083 s, mediana 0.084 s, max 0.087 s
  lease: min 0.549 s, mediana 0.553 s, max 0.559 s
```

`flock`: ~0,08 s (to w zasadzie start interpretera nowego procesu). Dzierżawa: ≈ TTL. Za odporność na zamrożenie
płacisz opóźnieniem po śmierci; **TTL to pokrętło**: krótszy = szybsze przejęcie, ale większe ryzyko fałszywego
„wygasło" przy chwilowym zacięciu. (Zmierzyłem tylko TTL 0,6 s. Wynik tuż poniżej TTL wynika stąd, że kill przychodził zaraz po zdobyciu dzierżawy,
zanim heartbeat zdążył ją odnowić — przy kill później czas do przejęcia byłby krótszy, do TTL w najgorszym razie; tego nie mierzyłem.)

## 4️⃣ 🧟 Dzierżawa nie wystarcza: właściciel-zombie wraca

Najważniejsza część. A jest zamrożony **po sprawdzeniu dzierżawy, przed zapisem**. Dzierżawa wygasa, B przejmuje
(token 2) i pracuje. Potem `SIGCONT` — A nie wie, że czas minął, i kończy swój krok. Trzy tryby, ten sam scenariusz:

```
== 1. zamrozony (SIGSTOP) wlasciciel miedzy sprawdzeniem a zapisem; B przejmuje; A wznowiony (ttl 0.6 s)
  unfenced: tokeny A/B = 1/2; A: ['wrote:0', 'wrote:1', 'wrote:2']; zapisy przeterminowane = 3; log: ['B token=2 item=0', 'B token=2 item=1', 'B token=2 item=2', 'A token=1 item=0', 'A token=1 item=1', 'A token=1 item=2']
  checked : tokeny A/B = 1/2; A: ['wrote:0', 'stop:lease-lost-before-1']; zapisy przeterminowane = 1; log: ['B token=2 item=0', 'B token=2 item=1', 'B token=2 item=2', 'A token=1 item=0']
  fenced  : tokeny A/B = 1/2; A: ['REJECTED:0:token 1 < 2']; zapisy przeterminowane = 0; log: ['B token=2 item=0', 'B token=2 item=1', 'B token=2 item=2']
```

- **`unfenced`** — A nic nie sprawdza: 3 zapisy po zapisach B. Dane nadpisane przeterminowanym stanem.
- **`checked`** — A przed każdym krokiem pyta „czy dzierżawa jeszcze moja?". Zatrzymuje się przed krokiem 1, **ale zapis kroku 0
  już „leciał"**: 1 przeterminowany zapis. To klasyczne *check-then-act* — między sprawdzeniem a użyciem wynik się zdezaktualizował.
  Żadna częstość sprawdzania tego nie zamknie, bo okno nie ma dolnej granicy.
- **`fenced`** — każdy zapis niesie token, a **zasób** (`FencedLog.append`) pamięta najwyższy widziany i odrzuca niższy,
  atomowo z dopisaniem wiersza. 0 przeterminowanych zapisów; A dostaje wyjątek i kończy się.

> 💡 **Dlaczego to ważne:** to ten sam wzorzec, który zna każdy, kto użył `ETag`/`If-Match`, kolumny `rowversion` w SQL
> Server czy `git push --force-with-lease` (analogie — tu ich nie testowałem): **kontrola musi być po stronie zasobu, w tej samej operacji co zapis**.
> Token to numer wersji uprawnienia, nie tajemnica. Rosnący licznik z `release` bez cofania jest tu warunkiem poprawności.

## 5️⃣ 🏁 Wyścig o wolną dzierżawę

4 procesy jednocześnie wołają `try_acquire` na wolnej dzierżawie, 20 rund:

```
== 5. wyscig 4 procesow o wolna dzierzawe (20 rund)
  zwyciezcow na runde: [1]; tokeny zwyciezcow: [(1,)]
```

Zawsze jeden zwycięzca z tokenem 1: transakcja pod `flock` jest atomowa. (Testowałem wyścig na *wolnej* dzierżawie; wyścig o
dzierżawę, która wygasa w trakcie, osobno nie.)

---

## 6️⃣ 🧪 Co jest, a czego nie ma

**Zweryfikowane (Python 3.10.4, Linux):**
- `python3 -B run_tests.py`: **14 testów OK** (`Ran 14 tests in 17.3s`), uruchomione dwukrotnie (po poprawce błędu w moim
  teście: pierwszy test `FencedLog` czytał zły plik logu; naprawione, kod `lease.py` nie był zmieniany).
- `python3 -B demo.py 10` — źródło wszystkich liczb powyżej. Po testach w `/tmp` nie zostają katalogi `prasowka-lease-*` (test `TestZCleanup`).

**Niezweryfikowane / uproszczone — wprost:**
- **Żywa sesja Claude Code, `claude -p`, `permissionMode`, hooki headless** — nie sprawdzano; model to skrypt.
- **Zegar:** używam `time.monotonic()` (wspólny dla procesów jednego hosta Linux). Między maszynami, po restarcie hosta i przy
  dryfie zegarów dzierżawa w tej postaci **nie działa**; nie testowałem skoków zegara. Zasób jest pojedynczym plikiem na lokalnym dysku
  — rozproszona wersja (baza, etcd, Redis) wymaga osobnej analizy.
- Fencing działa tylko, gdy **zasób umie go sprawdzić**. Wywołania zewnętrzne bez wsparcia tokenu (API, `git push` bez lease) ogrodzić się nie dadzą —
  zostaje idempotencja z #14 i tylko ona. Nie mierzyłem tego.
- Zapis przez `FencedLog` serializuje wszystkich pisarzy na jednym `flock` — narzut przy wielu pisarzach niemierzony.
- Testowałem 1 przejęcie na scenariusz zamrożenia (z powtórzeniami tylko w testach/demie wyścigu i przejęcia po kill).
  Heartbeat na wątku może być głodzony, jeśli proces jest przeciążony, ale nie zamrożony — nie badałem.
- Nie zintegrowałem dzierżawy z `Supervisor` z #14–#18 (kopii nie dołączam); to osobny, samodzielny model.

**Następne kroki:** integracja tokenu z dziennikiem WAL (każdy rekord niesie token, `fold` odrzuca rekordy ze starszym);
`permissionMode` po weryfikacji CLI; dzierżawa w bazie danych zamiast pliku.
