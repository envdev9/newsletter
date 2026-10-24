<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #10 — 3 października 2026

![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)
![ansible-core](https://img.shields.io/badge/ansible--core-2.17.14-informational?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)

## `serial` procentowy spotyka `throttle` i `run_once` — dwa zaległe pytania z #8, zamknięte

</div>

---

> _"Procent to nie liczba — to deklaracja, która w pewnym momencie MUSI zostać zamieniona na
> liczbę całkowitą. W #8 zmierzyliśmy to zaokrąglenie raz: floor, z wymuszonym minimum 1. Dziś
> sprawdzamy, czy ten sam, już zaokrąglony rozmiar paczki zachowuje się tak samo przewidywalnie,
> kiedy nałoży się na niego DRUGI mechanizm — `throttle` albo `run_once` — czy procentowe
> zaokrąglenie wprowadza jakąś niespodziankę, której nie widać przy `serial` podanym wprost
> jako liczba."_

W [#8](../../2026-10-01/ansible/ARTICLE.md) ustaliliśmy, że `serial: "40%"` na 8 hostach
(8 × 0,40 = 3,2, nie całkowita) daje paczki **3, 3, 2** — floor, nie zaokrąglenie w górę, reszta
zawsze w ostatniej paczce. Na końcu tamtego wydania zostały świadomie odłożone dwa pytania:
co się stanie, gdy na te same, nierówne, procentowo wyliczone paczki nałożymy `throttle`
(zmierzony w #7/#8 dla paczek z `serial` *liczbowego*), i co się stanie z `run_once` (zbadanym
w #6/#7 też tylko dla `serial` *liczbowego*). Dziś zamykamy oba — na tej samej flocie 8 hostów
i tym samym podziale 3/3/2, żeby porównanie było czyste.

| Temat | Analogia z .NET | Zweryfikowane? |
|---|---|---|
| `serial: "40%"` + `throttle: 2` na TYM SAMYM tasku (8 hostów → paczki 3/3/2) | `Parallel.ForEachAsync(MaxDegreeOfParallelism: 2)` nad partiami o rozmiarze wyliczonym z `(int)(pct * n)` | ✅ uruchomione, zmierzone znacznikami czasu, 2 przebiegi |
| `run_once` + `serial: "40%"` — w `pre_tasks` vs jako zwykły `task` vs w osobnym playu bez `serial` | `static` inicjalizator wywoływany raz na batch zadań w tle, kontra prawdziwy run-once-globalnie | ✅ uruchomione, 2 przebiegi, identyczne wyniki |
| `ansible-vault` / `ansible-galaxy` / gołe `ansible --version` | user-secrets / NuGet | ❌ **odrzucone przez środowisko (dziewiąty raz z rzędu, #3–#10)** |

> ⚠️ **`ansible-vault`/`ansible-galaxy` — sprawdzone dziś od nowa, wynik bez zmian.**
> `ansible --version`, `ansible-galaxy --version` i próby uruchomienia `ansible-vault` zostały
> **odrzucone przez system uprawnień środowiska agenta**, zanim jakikolwiek proces Ansible
> zdążył wystartować — ten sam komunikat co w #3–#8 (*"Permission to use Bash has been denied
> because Claude Code is running in don't ask mode"*). `ansible-playbook` zadziałał bez
> przeszkód, jak zawsze. Cały output poniżej to **prawdziwy wynik** z `ansible-playbook`,
> `ansible-core 2.17.14`.

Kod: [`code/`](code/). Jedna flota, 8 hostów `n1..n8` (grupa `flota`, `ansible_connection=local`
— bez prawdziwej floty SSH), używana identycznie w obu playbookach, żeby podział na paczki
3/3/2 (wyliczony z `serial: "40%"`) był ten sam punkt odniesienia dla obu eksperymentów.

---

### 🎯 1. `throttle: 2` na paczce wyliczonej z `serial: "40%"` (3, 3, 2 — nie z liczby wprost)

W #7/#8 (na `serial` *liczbowym*, 4 i 3) hipoteza brzmiała: `throttle: N` tworzy
`ceil(rozmiar_paczki / N)` fal wewnątrz każdej paczki `serial`. Dziś ten sam task, ale paczki nie
pochodzą z liczby podanej wprost — pochodzą z zaokrąglenia `8 × 0,40 = 3,2 → floor → 3`, z resztą
`2` w ostatniej paczce (dokładnie to, co zmierzyliśmy w #8 bez `throttle`). Pytanie: czy fakt, że
rozmiar paczki jest *produktem zaokrąglenia*, a nie wartością wpisaną wprost, coś zmienia w
matematyce `throttle`? Baseline (bez `throttle`, dla kontrastu — powinien wyjść identyczny z #8)
plus COMBO (`throttle: 2` na tym samym tasku), prawdziwy log z jednego przebiegu (drugi,
niżej w tabeli, identyczny co do rozmiarów paczek i fal):

```
BASELINE start 01:03:38.458 n1 rozmiar_paczki=3 paczka=['n1', 'n2', 'n3']
BASELINE start 01:03:38.562 n2 rozmiar_paczki=3 paczka=['n1', 'n2', 'n3']
BASELINE start 01:03:38.577 n3 rozmiar_paczki=3 paczka=['n1', 'n2', 'n3']   <- cala paczka 3 naraz
BASELINE start 01:03:40.027 n4 rozmiar_paczki=3 paczka=['n4', 'n5', 'n6']
BASELINE start 01:03:40.163 n5 rozmiar_paczki=3 paczka=['n4', 'n5', 'n6']
BASELINE start 01:03:40.203 n6 rozmiar_paczki=3 paczka=['n4', 'n5', 'n6']
BASELINE start 01:03:41.612 n8 rozmiar_paczki=2 paczka=['n7', 'n8']         <- ostatnia paczka: 2
BASELINE start 01:03:41.627 n7 rozmiar_paczki=2 paczka=['n7', 'n8']

COMBO start 01:03:43.034 n1 rozmiar_paczki=3 paczka=['n1', 'n2', 'n3']      <- fala 1 (2 hosty)
COMBO start 01:03:43.112 n2 rozmiar_paczki=3 paczka=['n1', 'n2', 'n3']
COMBO koniec 01:03:44.037 n1
COMBO koniec 01:03:44.115 n2
COMBO start 01:03:44.408 n3 rozmiar_paczki=3 paczka=['n1', 'n2', 'n3']      <- fala 2 (1 host) - DOPIERO PO fali 1
COMBO koniec 01:03:45.411 n3
COMBO start 01:03:45.809 n4 rozmiar_paczki=3 paczka=['n4', 'n5', 'n6']      <- paczka 2: ten sam wzorzec 2+1
COMBO start 01:03:45.874 n5 rozmiar_paczki=3 paczka=['n4', 'n5', 'n6']
COMBO koniec 01:03:46.812 n4
COMBO koniec 01:03:46.877 n5
COMBO start 01:03:47.177 n6 rozmiar_paczki=3 paczka=['n4', 'n5', 'n6']
COMBO koniec 01:03:48.180 n6
COMBO start 01:03:48.588 n8 rozmiar_paczki=2 paczka=['n7', 'n8']            <- paczka 3 (2 hosty): 1 fala, throttle=2=rozmiar
COMBO start 01:03:48.641 n7 rozmiar_paczki=2 paczka=['n7', 'n8']
```

Wynik, zweryfikowany dwukrotnie (identyczny podział na fale w obu przebiegach):

- **BASELINE** odtwarza dokładnie #8: paczki 3/3/2, każda startuje w całości naraz (bez
  `throttle` nic nie ogranicza równoległości wewnątrz paczki).
- **COMBO**, paczka 1 (`n1,n2,n3`, rozmiar 3): `n1`/`n2` startują razem (`43.034`/`43.112`) —
  fala 1, 2 hosty. `n3` startuje dopiero `44.408`, czyli **po** zakończeniu obu hostów fali 1
  (`44.037`/`44.115`) — fala 2, 1 host. `ceil(3/2) = 2` fale, rozmiary `2 + 1` — identyczny
  wzorzec co w #7/#8 na `serial` liczbowym.
- Paczka 2 (`n4,n5,n6`) — identyczny wzorzec co paczka 1.
- Paczka 3 (`n7,n8`, rozmiar 2 — ta "obcięta" resztka z zaokrąglenia procentu): `ceil(2/2) = 1`
  fala, oba hosty naraz. `throttle` tu w ogóle nie ogranicza, bo rozmiar paczki akurat równa się
  `throttle`.

> 💡 **Dlaczego to ważne:** zaokrąglenie procentu na liczbę całkowitą (floor + min. 1, patrz #8)
> dzieje się **raz**, zanim `throttle` w ogóle wejdzie do gry — `throttle` dostaje gotowy,
> skończony rozmiar paczki (3, 3 albo 2) i nie wie ani nie obchodzi go, że ten rozmiar powstał
> z procentu, a nie z liczby wpisanej wprost. Dwa niezależne zaokrąglenia (floor przy liczeniu
> rozmiaru paczki z procentu, `ceil` przy liczeniu liczby fal `throttle` wewnątrz tej paczki) nie
> wchodzą sobie w drogę — działają w sekwencji, nie równocześnie. Praktyczna konsekwencja: jeśli
> już zmierzyłeś zachowanie `throttle` na konkretnym rozmiarze paczki (jak w #7/#8), możesz mu
> ufać identycznie niezależnie od tego, czy ten rozmiar wyszedł z `serial: 3` czy z
> `serial: "37.5%"` na odpowiedniej flocie — raz ustalony rozmiar paczki to jedyne, co ma
> znaczenie dla `throttle`.

---

### 🔁 2. `run_once` + `serial: "40%"` — `pre_tasks`, zwykły `task`, i poprawka z #5 na procentach

W #5 znaleźliśmy pułapkę: `run_once` w `pre_tasks` playu z `serial` **nie** chroni przed
powtórnym wykonaniem — każda paczka `serial` to osobny "mini-play", więc `pre_tasks` wykonuje się
od nowa dla każdej paczki, a `run_once` ogranicza tylko *w obrębie tej jednej paczki* (woła
pierwszego hosta paczki), nie w obrębie całego playu. W #6/#7 potwierdziliśmy to też dla zwykłych
`tasks` (nie tylko `pre_tasks`) — zawsze dokładnie `liczba_paczek` wykonań, zawsze przez
pierwszego hosta każdej paczki. Pytanie na dziś: czy to się trzyma, gdy paczki są **nierówne**
(3, 3, 2 z `serial: "40%"`), a nie jak w #6/#7 — równe (po 2, po 4)? Trzy playe, ta sama flota,
ten sam podział 3/3/2:

```
PRE_TASKS_BUG run_once-init 01:03:56.468 wykonal=n1 rozmiar_paczki=3 paczka=['n1', 'n2', 'n3']
PRE_TASKS_BUG per-host     01:03:56.931 n2
PRE_TASKS_BUG per-host     01:03:57.084 n1
PRE_TASKS_BUG per-host     01:03:57.112 n3
PRE_TASKS_BUG run_once-init 01:03:57.482 wykonal=n4 rozmiar_paczki=3 paczka=['n4', 'n5', 'n6']   <- ODPALIL SIE PONOWNIE
PRE_TASKS_BUG per-host     01:03:57.921 n6
PRE_TASKS_BUG per-host     01:03:58.066 n4
PRE_TASKS_BUG per-host     01:03:58.107 n5
PRE_TASKS_BUG run_once-init 01:03:58.476 wykonal=n7 rozmiar_paczki=2 paczka=['n7', 'n8']          <- I PONOWNIE (paczka 2-hostowa)
PRE_TASKS_BUG per-host     01:03:58.870 n8
PRE_TASKS_BUG per-host     01:03:58.881 n7

TASK_IN_SERIAL run_once 01:03:59.256 wykonal=n1 rozmiar_paczki=3 paczka=['n1', 'n2', 'n3']
TASK_IN_SERIAL run_once 01:03:59.623 wykonal=n4 rozmiar_paczki=3 paczka=['n4', 'n5', 'n6']
TASK_IN_SERIAL run_once 01:03:59.988 wykonal=n7 rozmiar_paczki=2 paczka=['n7', 'n8']               <- tak samo 3x

SEPARATE_FIX run_once 01:04:00.337 wykonal=n1
```

Wynik, zweryfikowany dwukrotnie (identyczne wzorce w obu przebiegach, łącznie z tym, który
dokładnie host triggeruje `run_once`):

- **`PRE_TASKS_BUG`** (`run_once` w `pre_tasks` playu z `serial: "40%"`): wykonało się
  **dokładnie 3 razy** — raz na każdą z paczek **3, 3, 2** — nie raz na cały play. Pułapka z #5
  reprodukuje się identycznie na nierównych, procentowo wyliczonych paczkach: `pre_tasks` *też*
  podlega batchowaniu `serial`, więc "inicjalizacja" uruchamia się od nowa przy każdej paczce.
- **`TASK_IN_SERIAL`** (ten sam `run_once`, ale jako zwykły `task`, nie `pre_tasks`, w tym samym
  playu z `serial: "40%"`): **identyczny wynik — 3 wykonania.** Miejsce w playie (`pre_tasks` czy
  `tasks`) nie ma żadnego znaczenia — obie sekcje playu dzielą ten sam mechanizm batchowania
  `serial`. To nie jest "naprawiona" wersja, to to samo zachowanie w innym miejscu kodu.
- **Który host odpala `run_once` w obu powyższych:** zawsze **pierwszy host danej paczki**
  (`n1` dla paczki `[n1,n2,n3]`, `n4` dla `[n4,n5,n6]`, `n7` dla `[n7,n8]`) — hipoteza z #6/#7
  (`ansible_play_batch[0]`) trzyma się też dla nierównych paczek procentowych: nie ma znaczenia,
  że ostatnia paczka ma inny rozmiar (2 zamiast 3) — nadal woła jej pierwszy element.
- **`SEPARATE_FIX`** (`run_once` w **osobnym playu, bez `serial`** w ogóle — poprawka z #5):
  **dokładnie 1 wykonanie**, przez `n1` (pierwszy host całej inventory, nie jakiejś paczki).
  Poprawka z #5 trzyma się bez zmian: jeśli chcesz, żeby coś wykonało się raz na CAŁY playbook
  (nie raz na paczkę), to musi być w playu, który nie ma `serial` — niezależnie, czy gdzie indziej
  w tym samym playbooku `serial` jest liczbą, czy procentem.

> 💡 **Dlaczego to ważne:** to domyka pytanie z #5/#6/#7 ostateczną regułą, bez wyjątku dla
> procentów: **`run_once` nigdy nie "widzi" całego playu, jeśli ten play ma `serial`** — widzi
> tylko aktualną paczkę, i to niezależnie od tego, czy ta paczka ma rozmiar 2, 3, czy "obciętą"
> resztkę z zaokrąglenia procentu. Analogia z .NET: to jak `[ThreadStatic]` zainicjalizowany na
> starcie każdego wątku puli, licząc że zainicjalizuje się raz globalnie — w rzeczywistości
> odpala się raz *na wątek* (tu: raz *na paczkę*). Jedyny pewny sposób na "raz na cały playbook"
> to osobny play bez `serial` — tak samo jak jedyny pewny sposób na "raz na wątek" to świadome
> użycie `[ThreadStatic]`, a nie przypadkowe poleganie na kolejności wykonania.

---

### ✅ Co zweryfikowano, a czego nie

| Zweryfikowane (`ansible-core 2.17.14`) | Niezweryfikowane |
|---|---|
| `serial: "40%"` + `throttle: 2` na 8 hostach (paczki 3/3/2) — fale `2+1`, `2+1`, `1` (`throttle` = rozmiar ostatniej paczki) | Molecule (nadal zablokowane `ansible-galaxy`) |
| Hipoteza `ceil(paczka/throttle)` z #7/#8 trzyma się identycznie, gdy rozmiar paczki pochodzi z zaokrąglenia procentu, nie z liczby wprost | `ansible-vault`, `ansible-galaxy`, gołe `ansible --version` — odrzucone przez środowisko (9. raz z rzędu, #3–#10) |
| `run_once` w `pre_tasks` playu z `serial: "40%"` — 3 wykonania (raz na paczkę 3/3/2), pułapka z #5 reprodukuje się na procentach | Zdalne SSH, `become` (brak `sshd`/uprawnień do sprawdzenia w tej sesji — patrz niżej) |
| `run_once` jako zwykły `task` w tym samym playu — identyczne 3 wykonania; miejsce w playie (`pre_tasks`/`tasks`) nie ma znaczenia | — |
| Który host wywołuje `run_once` przy nierównych paczkach — zawsze pierwszy host DANEJ paczki (`n1`, `n4`, `n7`), nie pierwszy host inventory | — |
| `run_once` w OSOBNYM playu bez `serial` — dokładnie 1 wykonanie (poprawka z #5 trzyma się też przy procentowym `serial` gdzie indziej w playbooku) | — |
| `--syntax-check` na obu playbookach, każdy uruchomiony dwukrotnie (identyczne wyniki) | — |

**Pułapki/spostrzeżenia z tego wydania:**
1. `throttle` operuje na GOTOWYM rozmiarze paczki, bez względu na to, czy ten rozmiar powstał z
   liczby wpisanej wprost (`serial: 3`), czy z zaokrąglenia procentu (`serial: "40%"` → 3).
   Zaokrąglenie procentu (floor + min. 1, z #8) i liczenie fal `throttle` (`ceil`, z #7) to dwa
   **niezależne, sekwencyjne** kroki — nie wchodzą sobie w drogę, nie trzeba liczyć ich razem.
2. Pułapka `run_once` + `serial` z #5 (inicjalizacja odpala się raz NA PACZKĘ, nie raz na cały
   play) reprodukuje się identycznie na procentowo wyliczonych, nierównych paczkach (3, 3, 2) —
   nie jest to artefakt tylko równych, "ładnych" podziałów liczbowych.
3. Umiejscowienie `run_once` w `pre_tasks` kontra zwykłych `tasks` **nie ma żadnego wpływu** na
   tę pułapkę — obie sekcje playu dzielą ten sam mechanizm batchowania `serial`. Jedyna
   skuteczna poprawka to osobny play **bez `serial`**, niezależnie od tego, czym `serial` jest
   podany gdzie indziej w tym samym playbooku.
4. Przy nierównych paczkach `run_once` zawsze woła pierwszy host AKTUALNEJ paczki
   (`ansible_play_batch[0]`), nie pierwszy host całej inventory — więc "kto wykona `run_once`"
   zmienia się z paczki na paczkę, nawet gdy paczki mają różne rozmiary.

**Dlaczego dziś nie zdalne SSH/`become`:** sprawdzone na nowo w tej sesji przed pisaniem —
środowisko agenta odrzuca nie tylko `ansible-galaxy`/`ansible-vault`/gołe `ansible --version`
(jak w #3–#8), ale też wszelkie polecenia spoza `ansible-playbook` potrzebne do choćby
*sprawdzenia*, czy `sshd` jest dostępny (`dpkg -l`, `service ssh status`) — każde z nich zostało
odrzucone przez system uprawnień sesji, zanim zdążyło cokolwiek sprawdzić. Bez możliwości
zweryfikowania, czy `sshd` w ogóle działa lokalnie, pisanie o zdalnym SSH oznaczałoby zgadywanie
wyniku — sprzeczne z zasadą zero fikcji tej rubryki. Stąd dzisiejszy wybór: dwa pozostałe,
w pełni weryfikowalne punkty z listy "następny poziom" z #8.

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Demo pisze wyłącznie do `/tmp/ansible-demo-lvl9`
(nowy katalog na to wydanie, posprzątany po zakończeniu weryfikacji — patrz sekcja "Sprzątanie"
w `code/README.md`).

---

<div align="center">

[← wróć do wydania #10 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
