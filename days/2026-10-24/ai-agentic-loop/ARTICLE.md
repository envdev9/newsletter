<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #29 — 24 października 2026

![AI/Agentic loop](https://img.shields.io/badge/AI_%2F_Agentic_loop-5A67D8?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10.4-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Linux](https://img.shields.io/badge/SIGSTOP%20%2B%20flock-Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![Testy](https://img.shields.io/badge/testy_lokalne-13%2F13_x3-brightgreen?style=for-the-badge)
![Claude CLI](https://img.shields.io/badge/claude%20CLI-niezweryfikowane-lightgrey?style=for-the-badge)

## Token w dzienniku WAL: czytelnik ogradza zombie, ale nie cofa skutków

</div>

---

> _"Strażnik przy bramie jest dobry. Strażnik w archiwum, który wyrzuca podrzucone kartki, jest lepszy niż nic — ale kartki, które już zostały wykonane, nie wrócą."_

W #25 ogrodziliśmy **zasób**: `FencedLog` sprawdzał token atomowo z zapisem. To działa tylko wtedy, gdy
zasób *umie* odmówić. Dziennik WAL z #14–#24 to zwykły plik z `O_APPEND` — nikt przy zapisie nie pyta o
token (tak samo wygląda np. magazyn bez warunkowego zapisu). Dziś **przesuwamy sprawdzanie na stronę czytelnika**:
każdy rekord niesie token, a `fold()` odrzuca rekord z tokenem niższym niż najwyższy widziany wcześniej w pliku.
Na prawdziwych procesach (`SIGSTOP`/`SIGCONT`/`SIGKILL`) sprawdzamy, co to chroni — i, co ważniejsze, czego **nie**.
Kod: [`code/`](code/).

> ⚠️ **Uczciwie na starcie:** rolę agenta gra skrypt Pythona (`actor.py`), „praca" to `sleep`, „skutek zewnętrzny" to
> wiersz w `effects.log`. Realne są: procesy, sygnały, `flock` (dzierżawa z #25, skopiowana bez zmian), `O_APPEND`,
> `os.replace`. Python 3.10.4, Linux. `claude --version` nadal nie sprawdzałem — o `permissionMode` i hookach headless nic nie twierdzę.
> Liczby: jedno uruchomienie `demo.py`; testy 13/13 przeszły trzykrotnie (jedno z uruchomień równolegle z drugim).

---

## 1️⃣ 📜 Model: rekord = (token, operacja), `fold` = filtr + redukcja

Nowy właściciel dzierżawy **jako pierwszą rzecz** dopisuje rekord `barrier` ze swoim tokenem. Od tego momentu
każdy rekord z mniejszym tokenem (zombie po `SIGCONT`) jest przy składaniu stanu pomijany i liczony w `dropped`:

```python
for r in recs:
    tok = r.get("tok", 0)
    if fence and tok < st.hw:          # hw = najwyższy token widziany wcześniej w pliku
        st.dropped.append(r.get("id", "?")); continue
    st.hw = max(st.hw, tok)
    ...  # zastosuj rekord (step / done / snapshot); barrier tylko podnosi hw
```

Kolejność w pliku jest tu „zegarem": `O_APPEND` w jednym `write()` ustawia ją atomowo. Porównanie z wersją naiwną
(`fence=False`, ostatni zapis wygrywa) robimy na tych samych bajtach dziennika.

> 💡 **Dlaczego to ważne:** w #25 token chronił dane *przed* zapisem. Tu chroni *interpretację* — a ta decyduje o tym,
> co nadzorca uzna za „zrobione" po wznowieniu. Zombie, który dopisze `done`, bez fencingu zamyka cudzy bieg.

## 2️⃣ 🧟 Zombie w dzienniku: fold z tokenem vs naiwny

Scenariusz (`blind`: najpierw skutek, potem rekord): A robi kroki 0–1, dostaje `SIGSTOP` w trakcie „myślenia" przed krokiem 2,
dzierżawa (TTL 0,6 s) wygasa, B przejmuje (token 2), kończy kroki 2–5 i `done`. Potem `SIGCONT` — A dokańcza swoje 2–5 ze starym tokenem:

```
== 1. blind, A zamrozony PRZED krokiem 2 (SIGSTOP), B przejmuje, A wznowiony
  fold z tokenem  : {"steps": {"0": "A/t1", "1": "A/t1", "2": "B/t2", "3": "B/t2", "4": "B/t2", "5": "B/t2"}, "done_by": "B", "hw": 2, "dropped": 5}
  fold naiwny     : {"steps": {"0": "A/t1", "1": "A/t1", "2": "A/t1", "3": "A/t1", "4": "A/t1", "5": "A/t1"}, "done_by": "A", "hw": 2, "dropped": 0}
  skutki na krok  : {0: 1, 1: 1, 2: 2, 3: 2, 4: 2, 5: 2} | duplikaty: [2, 3, 4, 5] | brakujace: []
```

Dziennik jest poprawny tylko dla czytelnika z tokenem: 5 rekordów zombie odrzuconych (4 kroki + `done`), stan = wynik B.
Naiwny fold mówi, że kroki 2–5 wykonał A i to A skończył bieg. Ale spójrz na ostatnią linię: **skutki zewnętrzne zdublowane**
(kroki 2–5 wykonane dwukrotnie). Fold z tokenem niczego nie cofnął — nie ma jak, skutek już się stał.

> 💡 **Dlaczego to ważne:** fencing po stronie czytelnika naprawia *wiedzę* o tym, co się stało, nie *świat*. Prawdziwa
> obrona przed podwójnym `git push`/płatnością/migracją to klucz idempotencji (#14) albo zasób sprawdzający token. Dziennik z tokenem
> daje audytowi i wznowieniu prawdę — nic więcej.

## 3️⃣ 🪟 Tryb `intent`: zapis zamiarem przed skutkiem — i trzy konsekwencje

Wariant: najpierw dopisz rekord, odczytaj dziennik, `fold` — **jeśli twój rekord został odrzucony, nie wykonuj skutku**.
Ten sam zombie, trzy momenty zamrożenia (wszystko zmierzone `demo.py`):

```
== 2. intent, to samo zamrożenie przed krokiem 2
  skutki na krok  : {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1} | duplikaty: [] | brakujace: []
  kolejnosc skutkow: ['A/t1:0', 'A/t1:1', 'B/t2:2', 'B/t2:3', 'B/t2:4', 'B/t2:5']
== 3. intent, A zamrozony w OKNIE miedzy sprawdzeniem a skutkiem (pause 0.4 s), potem SIGCONT
  skutki na krok  : {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1} | duplikaty: [] | brakujace: []
  kolejnosc skutkow: ['A/t1:0', 'A/t1:1', 'B/t2:3', 'B/t2:4', 'B/t2:5', 'A/t1:2']
== 4. intent, A zamrozony w oknie i zabity (SIGKILL)
  skutki na krok  : {0: 1, 1: 1, 3: 1, 4: 1, 5: 1} | duplikaty: [] | brakujace: [2]
  fold z tokenem  : {"steps": {"0": "A/t1", "1": "A/t1", "2": "A/t1", "3": "B/t2", ...}, "done_by": "B", ...}
```

- **2** — zombie dopisuje zamiar, widzi własne odrzucenie i kończy: zero duplikatów. Zamrożenie *przed* zapisem zamiaru jest bezpieczne.
- **3** — zamiar zdążył wejść **przed** barierą B, więc jest ważny; B uczciwie pomija krok 2. Zombie po wznowieniu wykonuje skutek:
  **dokładnie raz, ale po krokach 3–5** (kolejność skutków odwrócona). Jeśli kroki zależą od kolejności, to jest błąd, którego żaden token nie wykryje.
- **4** — ta sama sytuacja, ale A ginie: dziennik twierdzi, że krok 2 jest zrobiony (`A/t1`), a skutku **nie ma** (`brakujace: [2]`).
  Cena semantyki „co najwyżej raz": rekord przed skutkiem oznacza, że crash w oknie gubi skutek bez śladu.

> 💡 **Dlaczego to ważne:** to nie jest „lepszy tryb", tylko wybór błędu. `blind` = co najmniej raz (duplikaty), `intent` = co najwyżej raz
> (luka). Okno między sprawdzeniem a skutkiem to dokładnie *check-then-act* z #25 — token je tylko przesunął, nie zamknął.
> Domknięcie wymaga, żeby skutek też był potwierdzany (rekord „wykonano") i by wznowienie umiało rozstrzygać „zamiar bez potwierdzenia" (`NEEDS_HUMAN` z #14).

## 4️⃣ 🗜️ Kompaktowanie musi nieść high-water mark

Snapshot z #17 zastępuje cały dziennik jednym rekordem. Jeśli nie zapisze najwyższego tokenu, fold po kompaktowaniu „zapomina" o barierze B.
Offline, na tych samych 4 rekordach, z zombie dopisanym po kompaktowaniu:

```
== 5. offline: snapshot musi niesc high-water mark; stary fd po compact
  carry_hw=True : krok1 zapisal B/t2, hw=2, odrzucone=['A1s1-zombie']
  carry_hw=False: krok1 zapisal A/t1, hw=1, odrzucone=[]
  zapis przez stary fd po compact: rekordow w dzienniku = 1 (1 = snapshot; zapis zombie trafil do osieroconego i-node'a)
```

Bez `hw` w snapshocie zombie przechodzi (`carry_hw=False` to celowo zepsuta wersja, jest w testach). Ciekawostka: zombie, który trzyma
**otwarty deskryptor sprzed** `os.replace`, pisze do osieroconego i-node'a — jego zapis przepada, więc tu akurat ogranicza go sam system plików.
Nasz `Journal.append` otwiera plik przy każdym zapisie, więc ta ochrona to przypadek, nie projekt. (Zweryfikowane lokalnie na Linuxie; NFS/inne FS nie.)

> 💡 **Dlaczego to ważne:** każdy mechanizm „stanu pochodnego" (snapshot, indeks, cache) musi przenosić wszystkie niezmienniki sprawdzane przy czytaniu.
> `hw` jest takim niezmiennikiem — kompaktowanie bez niego cicho wyłącza całą ochronę.

---

## 5️⃣ 🧪 Co jest, a czego nie ma

**Zweryfikowane (Python 3.10.4, Linux):**
- `python3 -B run_tests.py`: **13 testów OK** (~9,6 s), trzy uruchomienia (w tym dwa równocześnie); testy: fold z tokenem/naiwny, okno przed barierą,
  urwany ogon, snapshot z `hw` i bez, zgubiony zapis przez stary fd, 4 scenariusze procesowe, sprzątanie `/tmp/prasowka-fence-*`.
  Przy pierwszym przebiegu pojawiły się `ResourceWarning` (nie zamykałem plików w `scen.py`) — poprawione, testy bez zmian.
- `python3 -B demo.py` — źródło wszystkich liczb.

**Niezweryfikowane / uproszczone — wprost:**
- **Żywa sesja Claude Code, `claude -p`, `permissionMode`, hooki headless** — nie sprawdzano; agent to skrypt.
- Zombie z okna **przed barierą** B (po wygaśnięciu dzierżawy, przed jej zapisem) jest przyjmowany — to test `test_window_before_barrier_is_accepted`.
  B widzi taki rekord we własnym stanie po barierze, więc jest spójny, ale to nie jest „zero zapisów po wygaśnięciu".
- Jedno zamrożenie na scenariusz; scenariusze procesowe zależą od czasu (`sleep`, TTL 0,6 s) — na wolnej maszynie mogą się zachwiać.
- `O_APPEND` jednym `write()` jako atomowy porządek: założenie lokalnego systemu plików Linux; NFS/Windows/macOS nie badane. Wielu pisarzy poza A/B nie badano.
- Tokeny z `time.monotonic()` dzierżawy z #25 — ograniczenia zegara bez zmian. Nie zintegrowałem z `Supervisor` z #14–#24 (samodzielny model).
- Dokładne reguły Claude Code nie są tu użyte; to wzorzec projektowy, nie funkcja produktu.

**Następne kroki:** potwierdzenie skutku jako osobny rekord + rozstrzyganie „zamiaru bez potwierdzenia" przy wznowieniu; dzierżawa w bazie danych zamiast
pliku; `permissionMode` po weryfikacji CLI.
