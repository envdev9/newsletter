<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #6 — 29 września 2026

![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)
![ansible-core](https://img.shields.io/badge/ansible--core-2.17.14-informational?style=for-the-badge)

## `delegate_facts`, `run_once` + `serial: 2` i `throttle: 2` — trzy rzeczy, które "prawie" działają tak, jak myślisz

</div>

---

> _"`delegate_to` mówi WYKONAJ TU. `delegate_facts` mówi ZAPISZ TU. To dwie zupełnie różne
> decyzje i domyślnie Ansible podejmuje tylko pierwszą — wynik `set_fact` i tak wraca do hosta
> z pętli, nawet jeśli fizycznie policzony został gdzie indziej."_

W [#5](../../2026-09-28/ansible/ARTICLE.md) poznaliśmy `delegate_to` (task wykonuje się na innym
hoście niż ten z pętli), `async`/`poll` i `throttle: 1`. Zostały trzy rzeczy zapisane wtedy jako
"do zrobienia": `delegate_facts`, `throttle` > 1 i `run_once` z inną wartością `serial` niż `1`.
Dziś wszystkie trzy — plus niezaplanowana czwarta rzecz, którą złapaliśmy przypadkiem podczas
weryfikacji pierwszego przykładu (patrz pułapka w sekcji 1).

| Temat | Analogia z .NET | Zweryfikowane? |
|---|---|---|
| `delegate_facts: true` | zapis do pola statycznego wspólnego serwisu zamiast do zmiennej lokalnej wątku | ✅ uruchomione |
| `run_once` + `serial: 2` (2 paczki z 4 hostów) vs `run_once` bez `serial` | `lock`/singleton wykonany raz na "falę" batcha vs raz na całe wywołanie | ✅ uruchomione |
| `throttle: 2` na 4 hostach | `SemaphoreSlim(2)` wokół jednej sekcji kodu | ✅ uruchomione |
| Cache nazwy taska (`TASK [...]`) przy `{{ inventory_hostname }}` w `name:` | pole `[MemberNotNullWhen]`-owe pozornie per-request, a w praktyce cache'owane raz na proces | ✅ zaobserwowane (niezaplanowane) |
| `ansible-vault`, `ansible-galaxy` | user-secrets / NuGet | ❌ **odrzucone przez środowisko (jak w #3–#5)** |

> ⚠️ **To samo zastrzeżenie co w #3–#5, sprawdzone ponownie dziś.** `ansible-vault --version`,
> gołe `ansible --version` i `ansible-galaxy --version` zostały **znowu odrzucone** przez system
> uprawnień środowiska agenta — identycznie jak w poprzednich czterech wydaniach. `ansible-playbook`
> (jedyne polecenie użyte poniżej) działa bez przeszkód. Wszystko poniżej to **prawdziwy output**
> z `ansible-core 2.17.14`, Python 3.10.4.

Kod: [`code/`](code/). Cztery fikcyjne serwery aplikacyjne `app1..app4` plus fikcyjny load
balancer `lb1` — wszystkie to ta sama maszyna (`ansible_connection=local`), pod różnymi nazwami
w inventory. Czwarty host (`app4`) dołączył dopiero dziś — w #5 były tylko trzy, a do sensownego
pokazania `serial: 2` (dwie równe paczki) i `throttle: 2` (żeby w ogóle było widać "dwie fale")
potrzebna jest liczba podzielna przez 2, większa niż 2.

---

### 🎯 1. `delegate_facts` — gdzie NAPRAWDĘ ląduje fakt z `set_fact` + `delegate_to`

Scenariusz nawiązujący do rolling deployu z [#5](../../2026-09-28/ansible/ARTICLE.md): każdy z
`app1..app4`, przy okazji własnego wdrożenia, chce **raz sprawdzić coś na współdzielonym
zasobie** — tu fikcyjnie `lb1` (w realu: ile wolnego miejsca ma NFS, jaka wersja configu jest na
load balancerze). Naturalny odruch to `delegate_to: lb1` + `ansible.builtin.set_fact`. Problem:
**bez `delegate_facts: true` fakt i tak ląduje w hostvars bieżącego hosta z pętli**, mimo że sam
task fizycznie wykonał się na `lb1`:

```yaml
- name: "BEZ delegate_facts: set_fact leci na lb1, ale fakt ma wylądować tutaj"
  delegate_to: lb1
  ansible.builtin.set_fact:
    lb_seen_without_delegate_facts: "ustawil {{ inventory_hostname }} o {{ lookup('pipe', 'date +%H:%M:%S') }}"

- name: "Z delegate_facts: set_fact leci na lb1 I fakt ma tam wylądować"
  delegate_to: lb1
  delegate_facts: true
  ansible.builtin.set_fact:
    lb_seen_with_delegate_facts: "ustawil {{ inventory_hostname }} o {{ lookup('pipe', 'date +%H:%M:%S') }}"
```

Prawdziwy przebieg dla `app1` (play ma `serial: 1`, więc `app1` idzie jako pierwszy):

```
TASK [BEZ delegate_facts: set_fact leci na lb1, ale fakt ma wylądować tutaj]
ok: [app1 -> lb1]

TASK [Pokaz gdzie fakt NAPRAWDE wyladowal (bez delegate_facts)]
ok: [app1] => {
    "msg": "hostvars[app1].lb_seen_without_delegate_facts = ustawil app1 o 01:03:41 || hostvars['lb1'].lb_seen_without_delegate_facts = BRAK"
}

TASK [Z delegate_facts: set_fact leci na lb1 I fakt ma tam wylądować]
ok: [app1 -> lb1]

TASK [Pokaz gdzie fakt NAPRAWDE wyladowal (z delegate_facts)]
ok: [app1] => {
    "msg": "hostvars[app1].lb_seen_with_delegate_facts = BRAK || hostvars['lb1'].lb_seen_with_delegate_facts = ustawil app1 o 01:03:41"
}
```

Dokładnie odwrotnie niż intuicja podpowiada: **bez** `delegate_facts` fakt jest u `app1` (mimo
`delegate_to: lb1`), **z** `delegate_facts: true` fakt jest u `lb1` (i znika z `app1`). Ale
najciekawsze jest to, co dzieje się przy `app2` — fakt ustawiony przez `app1` na `lb1` jest tam
dalej widoczny, ZANIM `app2` zdąży cokolwiek zrobić:

```
TASK [Co juz widac w hostvars['lb1'] PRZED tym przebiegiem (dowod wspoldzielenia)]
ok: [app2] => {
    "msg": "hostvars['lb1'].lb_seen_with_delegate_facts (przed) = ustawil app1 o 01:03:41"
}
```

...i to samo dla `app3` (widzi zapis `app2`) i `app4` (widzi zapis `app3`) — pełny log w
[`code/README.md`](code/README.md). To jest właśnie sedno `delegate_facts`: fakt zapisany na
hoście `lb1` jest **globalnie widoczny dla całego przebiegu**, niezależnie który host z pętli go
zapisał — dokładnie jak zapis do pola statycznego współdzielonego serwisu, widocznego z każdego
wątku, a nie lokalnej zmiennej, która ginie razem z wątkiem, który ją utworzył.

> 🪤 **Niezaplanowana pułapka, złapana przy weryfikacji tego przykładu.** Task
> `name: "[{{ inventory_hostname }}] Co juz widac..."` w logu **cały czas pokazywał `[app1]`** —
> również w kolejnych, całkowicie osobnych sekcjach `PLAY` wygenerowanych przez `serial: 1` dla
> `app2`, `app3` i `app4`:
> ```
> PLAY [delegate_facts - gdzie ladują fakty ustawione przez set_fact + delegate_to] ***
> TASK [[app1] Co juz widac w hostvars['lb1'] PRZED tym przebiegiem (dowod wspoldzielenia)] ***
> ok: [app2] => { "msg": "hostvars['lb1'].lb_seen_with_delegate_facts (przed) = ustawil app1 o 01:03:41" }
> ```
> Sama **treść** `msg` jest poprawna dla każdego hosta (widać właściwe wartości), ale **nagłówek
> `TASK [...]`** z Jinja-wyrażeniem w `name:` zostaje wyrenderowany raz — najwyraźniej dla
> pierwszego hosta, jaki dla tego taska pojawił się w całym przebiegu playbooka — i ten sam,
> "zamrożony" tekst jest potem pokazywany dla wszystkich kolejnych hostów, mimo że wykonanie i
> `ok: [hostname] =>` poprawnie wskazują właściwą maszynę. Wniosek praktyczny: **nie ufaj nazwie
> hosta wpisanej w pole `name:` taska w logach z `serial`/pętli po hostach** — do identyfikacji,
> który host faktycznie coś zrobił, używaj `ok: [host]`/`changed: [host]` z lewej strony, nie
> tekstu z `TASK [...]`. Sam kod (`hostvars`, `set_fact`) działał przez cały czas poprawnie —
> zmyślony był tylko wyświetlany nagłówek.

> 💡 **Dlaczego to ważne:** `delegate_facts` to mechanizm "sprawdź raz na wspólnym zasobie, użyj
> wszędzie" — np. jedno zapytanie o wersję configu na load balancerze albo o dostępne miejsce na
> współdzielonym storage, którego wynik chcesz mieć dostępny we wszystkich kolejnych krokach
> deployu na wszystkich hostach, bez odpytywania tego zasobu N razy (raz na host).

---

### 🔁 2. `run_once` + `serial: 2` — kontynuacja pułapki z #5

W #5 odkryliśmy, że `run_once` w playu z `serial: 1` liczy się "raz na paczkę", nie "raz na cały
play" — bo `serial` dzieli play na osobne mini-playe. Dziś sprawdzamy to dokładniej na czterech
hostach: `serial: 2` (dwie paczki po dwa hosty) kontra brak `serial` (cała grupa to jedna
paczka), oraz **który konkretnie host** w danej paczce faktycznie wykonuje task oznaczony
`run_once` — sprawdzone magiczną zmienną `ansible_play_batch` (lista hostów aktywnych w
*bieżącej* paczce, dostępna bez `gather_facts`):

```yaml
- name: "run_once + serial: 2 (2 paczki po 2 hosty z 4)"
  hosts: app
  serial: 2
  tasks:
    - name: "[batch] Zapisz znacznik run_once (oczekiwane: RAZ NA PACZKE, czyli 2 razy total)"
      run_once: true
      ansible.builtin.lineinfile:
        path: "{{ marker_file }}"
        line: >-
          run_once wykonany przez {{ inventory_hostname }} o {{ lookup('pipe', 'date +%H:%M:%S.%3N') }}
          | paczka widziana przez ten host (ansible_play_batch) = {{ ansible_play_batch }}
        create: true
```

Prawdziwy wynik — plik znacznika ma **dokładnie dwie linie**, jedną na paczkę, i w każdej paczce
`run_once` wykonał **pierwszy host tej paczki** (`app1` w paczce `[app1, app2]`, `app3` w paczce
`[app3, app4]`):

```
"=== serial: 2 (oczekiwane 2 linie, jedna na paczke) ===",
[
    "run_once wykonany przez app1 o 01:04:10.945 | paczka widziana przez ten host (ansible_play_batch) = ['app1', 'app2']",
    "run_once wykonany przez app3 o 01:04:12.080 | paczka widziana przez ten host (ansible_play_batch) = ['app3', 'app4']"
],
"=== bez serial (oczekiwana 1 linia, caly play to jedna paczka) ===",
[
    "run_once wykonany przez app1 o 01:04:13.114 | ansible_play_batch = ['app1', 'app2', 'app3', 'app4']"
]
```

Dwa fakty potwierdzone realnym uruchomieniem, oba zgodne z dokumentacją Ansible, ale rzadko
sprawdzane w praktyce: (1) `run_once` w playu z `serial: N` wykonuje się **raz na każdą paczkę
`N` hostów**, nie raz na cały play — liczba wykonań to `liczba_hostów / N` (zaokrąglona w górę);
(2) hostem, który faktycznie wykona task, jest **pierwszy host danej paczki** w kolejności z
inventory, nie losowy ani zawsze pierwszy host całego playa. Przy `serial: 1` (jak w #5) to
zawsze ten jeden host paczki — przy `serial: 2` widać to wyraźniej, bo `app2` mimo obecności w
tej samej paczce **nie** wykonuje taska (`changed=True` tylko dla `app1`, `app2` dostaje
`ok=True changed=True` w debugu, bo `run_once` i tak **rozgłasza wynik** na wszystkie hosty
paczki — ale fizycznie policzył go `app1`).

> 💡 **Dlaczego to ważne:** jeśli budujesz playbook, który miesza `serial` (canary/rolling batch)
> z `run_once` (np. jednorazowe powiadomienie "zaczynam deploy" albo zapis do systemu audytu),
> musisz świadomie zdecydować: chcesz **jedno powiadomienie na cały deploy** (usuń `serial` z
> tego konkretnego taska/playa albo przenieś task do osobnego playa bez `serial`, jak w #5), czy
> **jedno powiadomienie na paczkę** (np. "batch 1/3 wystartował") — `run_once` + `serial` daje ci
> to drugie, nawet jeśli chciałeś pierwsze.

---

### 🚧 3. `throttle: 2` — dwie fale zamiast jednej

W #5 sprawdziliśmy tylko `throttle: 1` (pełna serializacja) kontra brak `throttle` (pełna
równoległość, ograniczona jedynie przez `forks`, domyślnie 5). Dziś: cztery hosty, `throttle: 2`
— najwyżej dwa hosty naraz wykonują **ten jeden task**, więc przy czterech hostach powinny
wyjść dokładnie **dwie fale po dwa hosty**:

```yaml
- name: "Task z throttle=2 (4 hosty, max 2 naraz -> 2 fale)"
  throttle: 2
  ansible.builtin.shell: >
    echo "start $(date +%H:%M:%S.%3N) {{ inventory_hostname }}" >> {{ log_file }};
    sleep 2;
    echo "koniec $(date +%H:%M:%S.%3N) {{ inventory_hostname }}" >> {{ log_file }}
```

Prawdziwa zawartość logu. Pierwsze cztery linie (task bez `throttle`) startują w odstępie
kilkudziesięciu milisekund i kończą się niemal razem — czyli `forks: 5` (domyślne) i tak puszcza
wszystkie 4 hosty naraz. Kolejne osiem linii (task z `throttle: 2`) to wyraźnie **dwie fale**:

```
start 01:04:21.350 app2        <- bez throttle: wszystkie 4 razem
start 01:04:21.361 app3
start 01:04:21.379 app1
start 01:04:21.382 app4
koniec 01:04:23.359 app2
koniec 01:04:23.365 app3
koniec 01:04:23.384 app1
koniec 01:04:23.388 app4
start 01:04:23.821 app1        <- throttle=2, fala 1: app1+app2 razem
start 01:04:23.873 app2
koniec 01:04:25.825 app1
koniec 01:04:25.879 app2
start 01:04:26.206 app3        <- throttle=2, fala 2: dopiero PO zakonczeniu fali 1
start 01:04:26.268 app4
koniec 01:04:28.211 app3
koniec 01:04:28.271 app4
```

`app3` startuje o `26.206`, czyli dopiero **po** zakończeniu obu hostów z pierwszej fali
(`25.825`/`25.879`) — `throttle: 2` naprawdę ogranicza równoległość *tego jednego taska* do 2,
niezależnie od tego, że cały play (i poprzedni task w tym samym playu) miał wszystkie 4 hosty
naraz.

> 💡 **Dlaczego to ważne:** `throttle: N` (N > 1) to środek między "wszystko naraz" a "jeden po
> drugim" — przydatne, gdy zasób współdzielony przez jeden krok deployu (np. pula licencji
> narzędzia, limit równoczesnych połączeń do bazy podczas migracji) wytrzymuje np. 2 równoległe
> operacje, ale nie wytrzymałby wszystkich hostów naraz, a serializacja całego playa (`serial`
> albo `throttle: 1`) byłaby niepotrzebnie wolna dla reszty kroków, które żadnego takiego
> ograniczenia nie mają.

---

### ✅ Co zweryfikowano, a czego nie

| Zweryfikowane (`ansible-core 2.17.14`) | Niezweryfikowane |
|---|---|
| `delegate_facts: true` vs brak — realna różnica w `hostvars` (dwa różne wyniki) | `delegate_facts` z prawdziwym `gather_facts`/`setup` na zdalnym hoście (nie tylko `set_fact`) |
| Globalna widoczność faktu ustawionego przez `delegate_facts` dla KOLEJNYCH hostów pętli | Zachowanie przy równoległym (nie `serial: 1`) zapisie tego samego faktu z kilku hostów naraz (race) |
| `run_once` + `serial: 2` — dokładnie 2 wykonania (1/paczkę) na 4 hostach, `ansible_play_batch` | `run_once` + `serial` z nierówną listą np. `[1, 3]` |
| `run_once` bez `serial` — dokładnie 1 wykonanie na całą grupę | — |
| `throttle: 2` na 4 hostach — dwie realne fale, potwierdzone znacznikami czasu | `throttle` łączony jednocześnie z `serial` (obie warstwy naraz) |
| Cache nazwy taska (`TASK [...]`) z `{{ inventory_hostname }}` w `name:` — zaobserwowane w logu | Czy to samo dzieje się bez `serial` (jedna paczka, wiele hostów) — nie testowane osobno |
| `--syntax-check` na wszystkich trzech playbookach | `ansible-vault`, `ansible-galaxy` — oba odrzucone przez środowisko (jak w #3–#5) |
| | Zdalne SSH, `become` |

**Pułapki/niespodzianki z tego wydania:**
1. `delegate_to` bez `delegate_facts: true` zostawia wynik `set_fact` u hosta z pętli, nie u
   hosta docelowego — mimo że sam task fizycznie policzony jest na hoście docelowym.
2. Nagłówek `TASK [...]` w logu Ansible, gdy `name:` zawiera `{{ inventory_hostname }}`, bywa
   **wyrenderowany raz i "zamrożony"** dla kolejnych hostów/paczek tego samego taska w ramach
   jednego przebiegu playbooka — mimo że faktyczne wykonanie (`ok: [host] =>`, treść `msg`)
   pozostaje poprawne per host. Nie ufaj nazwie hosta w `name:` przy `serial`/pętlach.
3. `run_once` + `serial: N` wykonuje task tyle razy, ile jest paczek (`liczba_hostów / N`), a nie
   raz na cały play — potwierdzone teraz precyzyjnie: 2 paczki = 2 wykonania, po jednym na
   pierwszy host każdej paczki.

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Demo pisze wyłącznie do `/tmp/ansible-demo-lvl5`
(ten sam katalog co w #5 — kontynuacja tego samego scenariusza).

---

<div align="center">

[← wróć do wydania #6 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
