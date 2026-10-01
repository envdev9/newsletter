<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #8 — 1 października 2026

![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)
![ansible-core](https://img.shields.io/badge/ansible--core-2.17.14-informational?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)

## `serial` w procentach i `throttle` na "nierównej" paczce — dwa zaokrąglenia, które potrafią zepsuć Ci canary deploy

</div>

---

> _"`serial: 2` to konkretna liczba. `serial: "25%"` to deklaracja intencji — "jedna czwarta
> floty naraz" — którą Ansible musi w jakimś momencie zamienić na konkretną liczbę hostów. Gdy
> ta liczba nie wychodzi całkowita (a przy niewygodnej liczbie hostów wyjdzie prawie zawsze),
> ktoś musi zdecydować: góra czy dół? Dziś to mierzymy, zamiast zgadywać."_

W [#7](../../2026-09-30/ansible/ARTICLE.md) połączyliśmy `serial: 4` + `throttle: 2` na **równej**
paczce (4 dzieli się przez 2 bez reszty) i wyszła ładna, symetryczna hipoteza: `throttle` tworzy
`ceil(rozmiar_paczki / throttle)` fal wewnątrz każdej paczki `serial`. Dziś sprawdzamy dwie rzeczy,
które w #7 zostały świadomie odłożone: co się dzieje, gdy `serial` jest podany w **procentach**
(a procent liczby hostów nie wychodzi całkowity), i czy hipoteza `ceil()` z `throttle` przetrwa,
gdy paczka `serial` jest **nierówna** (niepodzielna przez `throttle` bez reszty). Dodatkowo —
skoro zostało czasu — wracamy do "zamrożonego" nagłówka `TASK [...]` z #6 i w końcu sprawdzamy, czy
to efekt `serial`, czy coś bardziej ogólnego.

| Temat | Analogia z .NET | Zweryfikowane? |
|---|---|---|
| `serial: "25%"` / `"40%"` / `"10%"` na 8 hostach — w którą stronę zaokrągla Ansible? | `Math.Ceiling` vs `Math.Floor` na `batchSize = (int)(pct * hosts.Count)` | ✅ uruchomione, zmierzone znacznikami czasu + `ansible_play_batch` |
| `serial: 3` + `throttle: 2` (3 nie dzieli się przez 2) na 7 hostach | `Parallel.ForEachAsync` z `MaxDegreeOfParallelism: 2` na kolejce o nierównej długości | ✅ uruchomione, zmierzone znacznikami czasu, powtórzone 2× |
| BONUS: "zamrożony" `TASK [...]` z #6 — czy to tylko `serial`, czy też zwykłe playe/`loop`+`delegate_to`? | cache nazwy per-task vs per-request | ✅ uruchomione — rozstrzygnięte: to efekt `serial`, nie ogólna zasada |
| `ansible-vault` / `ansible-galaxy` / gołe `ansible --version` | user-secrets / NuGet | ❌ **odrzucone przez środowisko (ósmy raz z rzędu, #3–#8)** |

> ⚠️ **`ansible-vault`/`ansible-galaxy` — ósma próba, ten sam wynik.** Dziś sprawdzone na nowo:
> `ansible-vault encrypt_string 'sekret' --name 'moj_sekret'` i `ansible-galaxy --version` zostały
> **odrzucone przez system uprawnień środowiska agenta** zanim jakikolwiek proces Ansible ruszył —
> identyczny komunikat co w #3–#7 (*"Permission to use Bash has been denied because Claude Code is
> running in don't ask mode"*). `ansible-playbook` zadziałał bez przeszkód, jak zawsze. Wszystko
> poniżej to **prawdziwy output** z `ansible-playbook`, `ansible-core 2.17.14`, Python 3.10.4.

Kod: [`code/`](code/). Dwie fikcyjne floty: 8 hostów `web1..web8` (grupa `pct_hosts`, do testu
procentów — 8 wybrane tak, żeby jeden procent wyszedł "ładnie", a dwa inne nie) i 7 hostów
`s1..s7` (grupa `uneven_hosts`, do testu `throttle` na nierównej paczce `serial: 3` — 7 nie
dzieli się przez 3, więc ostatnia paczka ma tylko 1 hosta). Plus 3 hosty `h1..h3` do bonusu.
Wszystko `ansible_connection=local` — bez prawdziwej floty SSH.

---

### 🎯 1. `serial` w procentach — w którą stronę Ansible zaokrągla?

Dokumentacja Ansible mówi, że `serial` można podać jako procent floty, ale nie mówi wprost, co
się dzieje, gdy wynik nie jest liczbą całkowitą. Na 8 hostach trzy warianty dają trzy różne
sytuacje matematyczne:

| `serial` | 8 × procent | Czy całkowita? |
|---|---|---|
| `"25%"` | 8 × 0,25 = **2,0** | tak — kontrola, "ładny" przypadek |
| `"40%"` | 8 × 0,40 = **3,2** | nie — testuje zaokrąglenie |
| `"10%"` | 8 × 0,10 = **0,8** | nie, i to mniej niż 1 — testuje wymuszone minimum |

Jeden playbook, trzy playe pod rząd, każdy z osobną wartością `serial`, task loguje znacznik
czasu, hosta i **cały skład swojej paczki** (`ansible_play_batch | length` +
`ansible_play_batch`) — bo to jedyny wiarygodny sposób odczytania realnego rozmiaru paczki, bez
zgadywania go ze samych znaczników czasu. Prawdziwy log z jednego przebiegu (pełny w
[`code/README.md`](code/README.md)):

```
PCT25 start 01:03:35.874 web2 rozmiar_paczki=2 paczka=['web1', 'web2']
PCT25 start 01:03:35.890 web1 rozmiar_paczki=2 paczka=['web1', 'web2']
PCT25 start 01:03:37.322 web3 rozmiar_paczki=2 paczka=['web3', 'web4']
PCT25 start 01:03:37.334 web4 rozmiar_paczki=2 paczka=['web3', 'web4']
PCT25 start 01:03:38.737 web5 rozmiar_paczki=2 paczka=['web5', 'web6']
PCT25 start 01:03:38.758 web6 rozmiar_paczki=2 paczka=['web5', 'web6']
PCT25 start 01:03:40.156 web7 rozmiar_paczki=2 paczka=['web7', 'web8']
PCT25 start 01:03:40.184 web8 rozmiar_paczki=2 paczka=['web7', 'web8']

PCT40 start 01:03:41.689 web1 rozmiar_paczki=3 paczka=['web1', 'web2', 'web3']
PCT40 start 01:03:41.821 web2 rozmiar_paczki=3 paczka=['web1', 'web2', 'web3']
PCT40 start 01:03:41.855 web3 rozmiar_paczki=3 paczka=['web1', 'web2', 'web3']
PCT40 start 01:03:43.309 web4 rozmiar_paczki=3 paczka=['web4', 'web5', 'web6']
PCT40 start 01:03:43.450 web5 rozmiar_paczki=3 paczka=['web4', 'web5', 'web6']
PCT40 start 01:03:43.484 web6 rozmiar_paczki=3 paczka=['web4', 'web5', 'web6']
PCT40 start 01:03:44.882 web7 rozmiar_paczki=2 paczka=['web7', 'web8']       <- OSTATNIA paczka: resztka = 2
PCT40 start 01:03:44.909 web8 rozmiar_paczki=2 paczka=['web7', 'web8']

PCT10 start 01:03:46.271 web1 rozmiar_paczki=1 paczka=['web1']
PCT10 start 01:03:47.639 web2 rozmiar_paczki=1 paczka=['web2']
PCT10 start 01:03:48.999 web3 rozmiar_paczki=1 paczka=['web3']
PCT10 start 01:03:50.364 web4 rozmiar_paczki=1 paczka=['web4']
PCT10 start 01:03:51.723 web5 rozmiar_paczki=1 paczka=['web5']
PCT10 start 01:03:53.084 web6 rozmiar_paczki=1 paczka=['web6']
PCT10 start 01:03:54.442 web7 rozmiar_paczki=1 paczka=['web7']
PCT10 start 01:03:55.803 web8 rozmiar_paczki=1 paczka=['web8']
```

Wynik, zweryfikowany dwukrotnie (identyczny podział paczek w obu przebiegach):

- **`"25%"` (2,0, dokładnie):** 4 paczki po 2 hosty. Kontrola przechodzi bez niespodzianek.
- **`"40%"` (3,2, nie całkowita):** paczki **3, 3, 2** — czyli `3,2` zostało **obcięte w dół do
  3** (nie zaokrąglone w górę do 4!), a "zgubiona" reszta (0,2 hosta × 3 paczki ≈ 0,6, czyli
  realnie 1 cały host) trafiła do ostatniej, mniejszej paczki. Gdyby Ansible zaokrąglał w górę,
  wyszłoby `4, 4` (albo `4, 3, 1`) — zamiast tego dostajemy klasyczne **obcięcie części
  dziesiętnej (floor/`int()`)**, zastosowane raz dla całej floty, a reszta hostów po prostu
  spływa do ostatniej paczki.
- **`"10%"` (0,8, mniej niż 1):** paczki **1, 1, 1, 1, 1, 1, 1, 1** — czyli 8 paczek po 1 hoście,
  NIE 0 paczek i NIE błąd. `int(0.8)` samo z siebie dałoby `0`, co oznaczałoby paczkę o rozmiarze
  zero — Ansible **wymusza minimum 1 hosta na paczkę**, inaczej `serial` z bardzo małym
  procentem na małej flocie zawiesiłby cały playbook (paczka rozmiaru 0 nigdy by się nie
  "skończyła").

> 💡 **Dlaczego to ważne:** to jest dokładnie ten rodzaj zaokrąglenia, który w C# dyskutuje się
> przy `(int)(percentage * collection.Count)` kontra `Math.Ceiling`/`Math.Round` — i tu wygrywa
> najbardziej "zachowawcza" opcja: floor z wymuszonym minimum 1. Praktyczna konsekwencja dla
> canary deployu: `serial: "40%"` na 8 maszynach NIE da Ci fal 4/4 (po które sięgasz myśląc
> "40% to prawie połowa") — da Ci 3/3/2. Jeśli Twoja matematyka deployu zakłada konkretne
> rozmiary fal (np. "canary to zawsze dokładnie 1/4 floty"), licz w liczbach całkowitych
> (`serial: 2`), nie w procentach, które milcząco się obcinają.

---

### 🔁 2. `throttle: 2` na paczce `serial: 3` — hipoteza `ceil()` na nierównym przypadku

W #7 `serial: 4` + `throttle: 2` dało **równą** matematykę: `ceil(4/2) = 2` fale, obie pełne
(2+2). Dziś: `serial: 3` + `throttle: 2` na 7 hostach. `3` nie dzieli się przez `2` — paczki
`serial` wychodzą `[3, 3, 1]` (patrz punkt 1: po prostu `7 / 3` obcięte w dół + reszta w ostatniej
paczce), a każda z nich ma dostać `throttle: 2` na tym samym tasku. Hipoteza z #7 do sprawdzenia
na nierównym materiale: `ceil(rozmiar_paczki / throttle)` fal, więc dla paczki 3-hostowej
`ceil(3/2) = 2` fale (**2 + 1**, NIE 2 pełne fale), a dla ostatniej, jednohostowej paczki
`ceil(1/2) = 1` fala — mimo że `throttle` (2) jest tu większy niż cała paczka (1).

Baseline (bez `throttle`, cała paczka naraz) kontra kombinacja — prawdziwy log, dwa przebiegi,
identyczny wzorzec w obu:

```
BASELINE start 01:04:36.659 s2 paczka=['s1', 's2', 's3']   <- caly batch 3-hostowy naraz
BASELINE start 01:04:36.792 s3 paczka=['s1', 's2', 's3']
BASELINE start 01:04:36.804 s1 paczka=['s1', 's2', 's3']
...
BASELINE start 01:04:39.741 s7 paczka=['s7']               <- ostatnia, 1-hostowa paczka

COMBO start 01:04:41.129 s1 paczka=['s1', 's2', 's3']       <- fala 1 (2 hosty) paczki 1
COMBO start 01:04:41.182 s2 paczka=['s1', 's2', 's3']
COMBO koniec 01:04:42.133 s1
COMBO koniec 01:04:42.187 s2
COMBO start 01:04:42.478 s3 paczka=['s1', 's2', 's3']       <- fala 2 (1 host) paczki 1 - DOPIERO PO fali 1
COMBO koniec 01:04:43.481 s3
COMBO start 01:04:43.866 s5 paczka=['s4', 's5', 's6']       <- fala 1 paczki 2 - DOPIERO PO calej paczki 1
COMBO start 01:04:43.910 s4 paczka=['s4', 's5', 's6']
COMBO koniec 01:04:44.869 s5
COMBO koniec 01:04:44.913 s4
COMBO start 01:04:45.222 s6 paczka=['s4', 's5', 's6']       <- fala 2 (1 host) paczki 2
COMBO koniec 01:04:46.225 s6
COMBO start 01:04:46.581 s7 paczka=['s7']                   <- paczka 3: 1 host, 1 fala, throttle nic nie ogranicza
COMBO koniec 01:04:47.584 s7
```

Hipoteza `ceil()` **się potwierdza, dokładnie**, także na nierównej paczce:

- Paczka 1 (`s1,s2,s3`, 3 hosty): `s1`/`s2` startują razem o `41.129`/`41.182` (fala 1, 2 hosty),
  `s3` startuje dopiero o `42.478` — **po** zakończeniu obu hostów fali 1 (`42.133`/`42.187`),
  czyli fala 2 ma tylko **1** hosta (`ceil(3/2) = 2` fale, rozmiary `2 + 1`, nie `2 + 2`).
- Paczka 2 (`s4,s5,s6`) — identyczny wzorzec: fala 1 (`s5`,`s4`) + fala 2 (`s6`, sam).
- Paczka 3 (`s7`, 1 host) — **1 fala**, bo `ceil(1/2) = 1`. `throttle: 2` na paczce mniejszej niż
  sam `throttle` nie powoduje błędu i nie "czeka" na drugiego hosta, który nigdy nie przyjdzie —
  po prostu ogranicza do tego, co jest.
- Kolejna paczka nie startuje, dopóki *wszystkie* fale poprzedniej (łącznie z niepełną drugą
  falą) się nie skończą — `43.866` (start paczki 2) jest już po `43.481` (koniec fali 2 paczki 1).

> 💡 **Dlaczego to ważne:** w #7 sprawdziliśmy tylko "ładny" przypadek (4/2 = 2,0) — można by
> pomyśleć, że `throttle` po prostu dzieli paczkę na równe kawałki i przy nieparzystej
> różnicy coś się "zepsuje" albo czeka w martwym punkcie. Nie zepsuje się: `ceil()` to naprawdę
> cały mechanizm, łącznie z przypadkiem skrajnym (paczka mniejsza niż `throttle`). To ten sam
> wzorzec co kolejka `Channel<T>` z ograniczoną równoległością konsumentów — ostatnia, niepełna
> partia elementów po prostu dostaje mniej równoległych workerów, zamiast blokować się na
> czekaniu na elementy, których nie będzie.

---

### 🧩 3. BONUS: "zamrożony" `TASK [...]` z #6 — to wina `serial`, nie Ansible w ogóle

W [#6](../../2026-09-29/ansible/ARTICLE.md) zaobserwowaliśmy (niezaplanowanie), że przy
`serial: 1` nagłówek `TASK [...]` z `{{ inventory_hostname }}` w `name:` "zamraża się" na
pierwszym renderze i pokazuje tę samą wartość dla wszystkich kolejnych hostów/paczek — mimo że
faktyczne wykonanie (`ok: [host] =>`) poprawnie wskazuje właściwą maszynę. Zostało odłożone
pytanie: czy to efekt specyficzny dla `serial`, czy ogólna cecha Ansible (np. przy osobnych
playach bez `serial`, albo przy `loop` + `delegate_to`)? Cztery playe, jeden plik, 3 hosty
(`h1`, `h2`, `h3`):

- **Play A/B/C** — trzy OSOBNE playe (bez `serial`), każdy celuje w innego, jednego hosta,
  identyczny wzorzec `name: "[{{ inventory_hostname }}] ..."`.
- **Play D** — jeden play, jeden task, `loop` po liście `[h1, h2, h3]` + `delegate_to: "{{ item }}"`,
  `name: "[{{ item }}] ..."` (zmienna pętli, nie hosta).
- **Play E (kontrola)** — jeden play, `serial: 1` na tych samych 3 hostach, identyczny wzorzec co
  w A/B/C — ma odtworzyć efekt z #6 na tej samej flocie, dla czystego porównania.

Prawdziwy output, dwa przebiegi, identyczne nagłówki w obu:

```
TASK [[h1] test nazwy taska bez serial]              <- Play A, host h1 - poprawnie
TASK [[h2] test nazwy taska bez serial]              <- Play B, host h2 - poprawnie
TASK [[h3] test nazwy taska bez serial]              <- Play C, host h3 - poprawnie
TASK [[{{ item }}] test nazwy taska w loop+delegate_to]   <- Play D - szablon NIE wyrenderowany wcale
TASK [[h1] test nazwy taska z serial: 1]             <- Play E, batch h1 - OK
TASK [[h1] test nazwy taska z serial: 1]             <- Play E, batch h2 - "zamrozone" na [h1]!
TASK [[h1] test nazwy taska z serial: 1]             <- Play E, batch h3 - "zamrozone" na [h1]!
```

Rozstrzygnięte: **to efekt specyficzny dla `serial`, nie ogólna zasada.** Trzy osobne, niezależnie
sparsowane playe (A/B/C) renderują `name:` poprawnie, każdy dla swojego hosta — zero
"zamrażania". Dopiero kontrola (Play E), gdzie `serial: 1` **wielokrotnie wykonuje ten sam,
jeden skompilowany obiekt task/play** w kolejnych paczkach, odtwarza dokładnie efekt z #6:
nagłówek renderuje się raz (dla pierwszego hosta, `h1`) i ten tekst jest potem pokazywany dla
`h2` i `h3`, mimo że `ok: [h2] =>`/`ok: [h3] =>` poniżej są poprawne. Dodatkowa, nieplanowana
obserwacja z Play D: `{{ item }}` (zmienna *pętli*, nie hosta) w `name:` nie zostaje
"zamrożona" na jakiejś wartości — zostaje **wcale nie wyrenderowana**, w logu widać dosłowny,
surowy tekst szablonu `{{ item }}`. To inny mechanizm niż `inventory_hostname`: zmienna pętli
nie jest jeszcze znana w momencie, gdy Ansible renderuje nagłówek taska (przed pierwszą
iteracją), więc nie ma czego "zamrozić" — po prostu nie podstawia niczego.

> 💡 **Dlaczego to ważne:** to zamyka pytanie z #6 praktyczną regułą: jeśli widzisz w logu
> `TASK [...]` z `{{ inventory_hostname }}`, które wygląda "podejrzanie" (ten sam host przy
> wielu różnych playach wykonania), podejrzewaj `serial` (ten sam task odtwarzany w kolejnych
> paczkach) — nie winy w swoim kodzie czy ogólnej niestabilności Ansible. Zwykłe, osobne playe
> renderują nazwy poprawnie zawsze.

---

### ✅ Co zweryfikowano, a czego nie

| Zweryfikowane (`ansible-core 2.17.14`) | Niezweryfikowane |
|---|---|
| `serial: "25%"` na 8 hostach — 4 paczki po 2 (procent całkowity, kontrola) | `serial` procentowy łączony z `throttle` naraz |
| `serial: "40%"` na 8 hostach — paczki 3/3/2 (obcięcie w dół, reszta w ostatniej paczce) | `run_once` + `serial` procentowy |
| `serial: "10%"` na 8 hostach — 8 paczek po 1 (wymuszone minimum 1, nie 0) | `ansible-vault`, `ansible-galaxy`, gołe `ansible --version` — odrzucone przez środowisko (8. raz z rzędu, #3–#8) |
| `serial: 3` + `throttle: 2` na 7 hostach (paczki 3/3/1) — fale 2+1, 2+1, 1, potwierdzające `ceil()` na nierównym materiale | Zdalne SSH, `become` |
| Rozmiar paczki mniejszy niż `throttle` (ostatnia paczka = 1 host, `throttle: 2`) — nie blokuje, po prostu 1 fala | — |
| BONUS: "zamrożony" `TASK [...]` z #6 — odtworzone (kontrola `serial: 1`) i ODRZUCONE dla osobnych playów bez `serial` | — |
| BONUS: `{{ item }}` w `name:` przy `loop` — nie zamrożone, zostaje niewyrenderowanym literałem | — |
| `--syntax-check` na wszystkich trzech playbookach, każdy uruchomiony dwukrotnie (identyczne wyniki) | — |

**Pułapki/spostrzeżenia z tego wydania:**
1. `serial` w procentach **obcina w dół** (floor/`int()`), nie zaokrągla w górę — `"40%"` z 8
   hostów to paczki `3, 3, 2`, nie `4, 4`. Resztki zawsze trafiają do ostatnich paczek.
2. Minimum rozmiaru paczki `serial` procentowego to **1**, nigdy 0 — nawet `"10%"` z 8 hostów
   (matematycznie 0,8) daje 8 paczek po 1 hoście, nie zawieszony playbook.
3. `throttle: N` na paczce `serial`, która nie jest wielokrotnością `N`, tworzy `ceil(paczka/N)`
   fal z niepełną ostatnią falą (`2+1`, nie `2+2`) — hipoteza z #7 trzyma się także na
   nierównym materiale, włącznie z przypadkiem skrajnym "paczka mniejsza niż throttle" (1 fala,
   zero błędów).
4. "Zamrożony" nagłówek `TASK [...]` z `{{ inventory_hostname }}` to artefakt **konkretnie**
   `serial` (ten sam skompilowany task wykonywany wielokrotnie w kolejnych paczkach) — zwykłe,
   osobne playe renderują nazwy poprawnie. `{{ item }}` z `loop` w ogóle nie jest renderowane w
   nagłówku (literalny tekst szablonu), bo w momencie druku nagłówka iteracja jeszcze się nie
   zaczęła.

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Demo pisze wyłącznie do `/tmp/ansible-demo-lvl8`
(nowy katalog na to wydanie, posprzątany po zakończeniu weryfikacji — patrz sekcja "Sprzątanie"
w `code/README.md`).

---

<div align="center">

[← wróć do wydania #8 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
