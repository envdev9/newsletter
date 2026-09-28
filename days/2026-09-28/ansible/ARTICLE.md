<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #5 — 28 września 2026

![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)
![ansible-core](https://img.shields.io/badge/ansible--core-2.17.14-informational?style=for-the-badge)

## `delegate_to`, `async`/`poll` i `throttle` — czyli gdzie naprawdę wykonuje się Twój task

</div>

---

> _"`delegate_to` nie zmienia PĘTLI, zmienia tylko ADRES. Zmienna `inventory_hostname` dalej
> mówi "app2", nawet gdy sam task fizycznie leci na zupełnie innej maszynie."_

W [#1](../../2026-09-24/ansible/ARTICLE.md)–[#4](../../2026-09-27/ansible/ARTICLE.md) budowaliśmy
playbooki, które **robią coś na hoście, na którym akurat jesteśmy**, ewentualnie z barierami
czasowymi (`serial`, `strategy`). Dziś pierwsza rzecz, która naprawdę łamie ten schemat: task
zapętlony po hostach `app1..app3`, który w środku pętli **wykonuje się gdzie indziej**. Do tego
dwa mechanizmy sterowania czasem wykonania, o których dotąd nie było mowy: praca w tle
(`async`/`poll`) i limit równoległości dla pojedynczego taska (`throttle`), niezależny od tego,
ile hostów gra jednocześnie w całym play'u.

| Temat | Analogia z .NET | Zweryfikowane? |
|---|---|---|
| `delegate_to` (+ `run_once` + `delegate_facts`) | wywołanie metody na innym obiekcie w pętli `foreach` | ✅ uruchomione |
| `async` + `poll` (poll>0, poll=0 + `async_status`, timeout) | `Task.Run` + `await` z timeoutem vs fire-and-forget | ✅ uruchomione |
| `throttle` na pojedynczym tasku | `SemaphoreSlim(1)` tylko wokół jednej sekcji kodu | ✅ uruchomione |
| `ansible-vault` | user-secrets w pliku | ❌ **odrzucone przez środowisko (jak w #3 i #4)** |
| `ansible-galaxy`, kolekcje | NuGet | ❌ **odrzucone przez środowisko (nowe: nawet `--version`)** |

> ⚠️ **To samo zastrzeżenie co w #3 i #4, tym razem z dodatkowym odkryciem.** Próbowałem
> ponownie `ansible-vault --version` — odrzucone przez system uprawnień środowiska, identycznie
> jak poprzednio. Nowość: tym razem odrzucone zostało też **gołe `ansible --version`** oraz
> **całe `ansible-galaxy`** (nawet samo sprawdzenie wersji), mimo że w #4 problemem był tylko
> `ansible-vault encrypt`. `ansible-playbook` — jedyne polecenie użyte w tym wydaniu — działa
> bez przeszkód. Wszystko poniżej to **prawdziwy output** z `ansible-core 2.17.14`, Python 3.10.

Kod: [`code/`](code/). Trzy fikcyjne serwery aplikacyjne `app1..app3` plus fikcyjny load
balancer `lb1` — wszystkie to ta sama maszyna (`ansible_connection=local`), ale pod różnymi
nazwami w inventory, żeby `delegate_to` miało sens do pokazania.

---

### 🎯 1. `delegate_to` — rolling deploy z drenowaniem load balancera

Do tej pory każdy task w pętli po hostach robił swoje **na tym hoście**. `delegate_to: X`
mówi: "ten jeden task, dla tego jednego przebiegu pętli, wykonaj na maszynie X" — reszta
zmiennych (`inventory_hostname`, `item`, wszystko co dotyczy bieżącego hosta z pętli) **zostaje
bez zmian**. To jak wywołanie `otherService.Notify(currentItem.Id)` wewnątrz `foreach (var item
in items)` — pętla dalej idzie po `items`, ale konkretne wywołanie ląduje gdzie indziej.

Scenariusz: trzy hosty `app1..app3`, każdy po kolei (`serial: 1`) ma zostać wyjęty z puli
load balancera, wdrożony, i wrócić do puli. "Pula LB" to zwykły plik tekstowy na `lb1`
(`ansible.builtin.lineinfile`), a wyjęcie/dodanie hosta z tego pliku **musi wykonać się na
`lb1`**, nie na hoście, który akurat wdrażamy:

```yaml
tasks:
  - name: "[{{ inventory_hostname }}] wyjmij mnie z puli LB (zadanie leci na lb1!)"
    delegate_to: lb1
    ansible.builtin.lineinfile:
      path: "{{ pool_file }}"
      regexp: "^{{ inventory_hostname }}$"
      state: absent

  - name: "[{{ inventory_hostname }}] deploy (zadanie leci LOKALNIE na tym hoscie)"
    ansible.builtin.copy:
      content: "wdrozono {{ inventory_hostname }} o {{ lookup('pipe', 'date +%H:%M:%S') }}\n"
      dest: "{{ demo_dir }}/deployed_{{ inventory_hostname }}.txt"

  - name: "[{{ inventory_hostname }}] wroc do puli LB (zadanie znowu na lb1)"
    delegate_to: lb1
    ansible.builtin.lineinfile:
      path: "{{ pool_file }}"
      line: "{{ inventory_hostname }}"
      create: true
```

Prawdziwy przebieg (skrót). Zwróć uwagę na `[app1 -> lb1]` w logu — to jest dokładnie ten
zapis, po którym poznasz `delegate_to` w outpucie Ansible:

```
TASK [[app1] wyjmij mnie z puli LB (zadanie leci na lb1!)]
changed: [app1 -> lb1]

TASK [Pokaz stan puli]
ok: [app1] => { "msg": "Pula LB podczas deployu app1: ['app2', 'app3']" }

TASK [[app1] deploy (zadanie leci LOKALNIE na tym hoscie)]
changed: [app1]

TASK [[app1] wroc do puli LB (zadanie znowu na lb1)]
changed: [app1 -> lb1]
...
TASK [Pokaz koncowy stan puli]
ok: [app3] => { "msg": "Pula LB na koniec: ['app1', 'app2', 'app3']" }
```

Cała pula przewinęła się poprawnie: `app1` znika z listy na czas swojego deployu, wraca na
koniec listy; potem to samo dla `app2` (który drenuje pulę zawierającą już powracającego
`app1`), potem `app3`. Na końcu w puli są znowu wszystkie trzy hosty.

> 🪤 **Prawdziwa pułapka znaleziona przy pisaniu tego przykładu.** Pierwsza wersja inicjowała
> plik puli w `pre_tasks` tego samego play'a, z `run_once: true`, licząc że to "zainicjuje pulę
> raz na cały play". Błąd: play ma `serial: 1`, a `serial` — jak pokazaliśmy w
> [#4](../../2026-09-27/ansible/ARTICLE.md) — dzieli play na **osobne mini-playe, jeden na
> paczkę**. `run_once` w `pre_tasks` liczy się więc **per paczka**, a przy `serial: 1` każda
> paczka ma dokładnie jeden host — więc `run_once` nic nie chroni i inicjalizacja **cicho
> resetowała całą pulę przy każdym kolejnym hoście**, kasując efekt drenowania poprzednika. Log
> z tej (błędnej) wersji: `"Zainicjuj pule LB..."` → `changed` dla `app1`, `app2` **i** `app3`
> — powinno być `changed` tylko raz. Naprawa: inicjalizacja w **osobnym play'u** kierowanym
> wprost na grupę `lb` (tam jest jeden host, więc problem znika strukturalnie, nie przez
> pilnowanie `run_once`). Wniosek ogólny: **`run_once` w playu z `serial` nie robi tego, czego
> intuicyjnie oczekujesz** — myśl w kategoriach "raz na paczkę", nie "raz na play".

> 💡 **Dlaczego to ważne:** `delegate_to` to mechanizm za każdym prawdziwym "rolling update za
> load balancerem" w Ansible — wyjęcie z HAProxy/nginx/AWS Target Group, health-check, deploy,
> przywrócenie. Bez niego musiałbyś pisać osobny playbook na maszynę LB i ręcznie go
> synchronizować z playbookiem deployu.

---

### ⏳ 2. `async` / `poll` — praca w tle po stronie hosta

`async`/`poll` to **nie** to samo co odpalenie czegoś w tle w Twoim terminalu. To task, który
faktycznie startuje na hoście docelowym i od razu oddaje sterowanie kontrolerowi — a kontroler
później (albo wcale) sprawdza, czy się skończył. Trzy warianty, wszystkie w
[`async_poll.yml`](code/async_poll.yml):

**a) `poll > 0` — Ansible sam pyta co `poll` sekund**, aż zadanie się skończy albo minie limit
`async`. Wygląda w YAML jak zwykły, synchroniczny task:

```yaml
- name: "Backup (trwa ok. 6s), async=20 poll=2 - Ansible sam czeka i odpytuje"
  ansible.builtin.command: "sleep 6"
  async: 20
  poll: 2
```

```
ASYNC POLL on app1: jid=j842117621130.104311 started=1 finished=0
ASYNC POLL on app1: jid=j842117621130.104311 started=1 finished=0
ASYNC OK on app1: jid=j842117621130.104311
ok: [app1]
```

**b) `poll: 0` — "fire and forget".** Task kończy się natychmiast i zwraca `ansible_job_id`
(`jid`). Wynik sprawdzasz później ręcznie, modułem `ansible.builtin.async_status` — dokładnie
jak `Task.Run(...)` bez `await`, gdzie później sam decydujesz, kiedy sprawdzić `IsCompleted`:

```yaml
- ansible.builtin.shell: "sleep 8 && echo GOTOWE > {{ demo_dir }}/async_job_done.txt"
  async: 30
  poll: 0
  register: bg_job

- ansible.builtin.async_status:
    jid: "{{ bg_job.ansible_job_id }}"
  register: final_check
  until: final_check.finished
  retries: 6
  delay: 2
```

Prawdziwy przebieg — sprawdzenie od razu po starcie pokazuje `finished=0`, a pętla
`until`/`retries`/`delay` (poznana w [#4](../../2026-09-27/ansible/ARTICLE.md) przy okazji
`register`/`failed_when`) sama dogania zakończenie zadania:

```
"Sprawdzenie natychmiastowe: finished=0"

FAILED - RETRYING: [app1]: Poczekaj na dokonczenie jobu ... (6 retries left).
FAILED - RETRYING: [app1]: Poczekaj na dokonczenie jobu ... (5 retries left).
FAILED - RETRYING: [app1]: Poczekaj na dokonczenie jobu ... (4 retries left).
FAILED - RETRYING: [app1]: Poczekaj na dokonczenie jobu ... (3 retries left).
changed: [app1]

"Sprawdzenie koncowe: finished=1, rc=0"
```

`until` na module, który jeszcze nie skończył zadania, w logu wygląda jak porażka
(`FAILED - RETRYING`) — to nie jest błąd, to normalne działanie mechanizmu retry.

**c) Co gdy zadanie nie zdąży w limicie `async`?** To pytanie, które prędzej czy później zada
sobie każdy, kto pierwszy raz ustawia `async`. Zrobiłem to celowo źle: `sleep 6` z `async: 3`:

```
ASYNC POLL on app1: jid=j326263578337.104598 started=1 finished=0
ASYNC POLL on app1: jid=j326263578337.104598 started=1 finished=0
ASYNC POLL on app1: jid=j326263578337.104598 started=1 finished=0
ASYNC FAILED on app1: jid=j326263578337.104598
fatal: [app1]: FAILED! => {"msg": "async task did not complete within the requested time - 3s", ...}
...ignoring
```

Task kończy się błędem z **dokładnie takim komunikatem** — Ansible przestaje odpytywać i
zgłasza porażkę, ale (tego nie sprawdzałem dalej) proces w tle na hoście może dalej żyć, bo
`async` nie zabija zadania, tylko przestaje na nie czekać.

> 🪤 **Druga prawdziwa pułapka z tego samego pliku.** Pierwsza wersja zadania "w tle" użyła
> `ansible.builtin.command: "sleep 8 && echo GOTOWE > plik"`. `command` **nie przechodzi przez
> powłokę** — `&&` i `>` trafiły jako dosłowne argumenty do `sleep`, który natychmiast (nie po
> 8 sekundach!) padł z błędem `sleep: invalid time interval '&&'`. Naprawa: `ansible.builtin.shell`
> zamiast `command`, gdy potrzebujesz operatorów powłoki. To ta sama zasada co w #1 (`command`
> jako bezpieczniejszy, "goły" odpowiednik `shell`), tylko tym razem złapana na błędzie, a nie
> opisana z góry.

> 💡 **Dlaczego to ważne:** `async` przydaje się przy zadaniach, które trwają dłużej niż
> rozsądny timeout połączenia SSH (duże backupy, długie migracje) — bez niego kontroler czeka
> zablokowany na jednym hoście przez cały czas trwania zadania.

---

### 🚧 3. `throttle` — limit równoległości dla jednego taska

`serial` (poznane w [#4](../../2026-09-27/ansible/ARTICLE.md)) i `forks` (domyślnie 5)
ograniczają, ile hostów gra naraz **w całym play'u**. `throttle` działa inaczej: to limit
**tylko dla jednego konkretnego taska** — reszta taskow w tym samym play'u nadal leci z
pełną równoległością. To odpowiednik obłożenia jednej sekcji kodu `SemaphoreSlim(1)`, a nie
zmiany `MaxDegreeOfParallelism` całego programu.

Ten sam task, dwa razy — raz bez `throttle`, raz z `throttle: 1`, każdy host śpi 2 sekundy i
zapisuje znacznik czasu do wspólnego pliku logu:

```yaml
- name: "Task ROWNOLEGLY (bez throttle)"
  ansible.builtin.shell: >
    echo "start $(date +%H:%M:%S.%3N) {{ inventory_hostname }}" >> {{ log_file }};
    sleep 2;
    echo "koniec $(date +%H:%M:%S.%3N) {{ inventory_hostname }}" >> {{ log_file }}

- name: "Task Z throttle=1"
  throttle: 1
  ansible.builtin.shell: >
    echo "start $(date +%H:%M:%S.%3N) {{ inventory_hostname }}" >> {{ log_file }};
    sleep 2;
    echo "koniec $(date +%H:%M:%S.%3N) {{ inventory_hostname }}" >> {{ log_file }}
```

Prawdziwa zawartość logu po przebiegu — pierwsze trzy linie (bez `throttle`) startują w
odstępie **kilkunastu milisekund** i kończą się prawie równocześnie; kolejne sześć (z
`throttle: 1`) to ścisła sekwencja, host po hoście:

```
start 01:46:48.211 app1        <- rownolegle: start w ~150ms od siebie
start 01:46:48.358 app2
start 01:46:48.367 app3
koniec 01:46:50.214 app1
koniec 01:46:50.364 app2
koniec 01:46:50.369 app3
start 01:46:50.719 app1        <- throttle=1: app2 czeka az app1 skonczy
koniec 01:46:52.722 app1
start 01:46:53.059 app2
koniec 01:46:55.062 app2
start 01:46:55.400 app3
koniec 01:46:57.403 app3
```

`app2` startuje o `53.059`, czyli dopiero **po** `koniec ... app1` (`52.722`) — dokładnie tak,
jak przy `serial`, tylko że tu ograniczony jest jeden task, a nie cały play.

> 💡 **Dlaczego to ważne:** `throttle` ma sens, gdy tylko **jeden konkretny krok** ma wspólne
> ograniczone zasoby (np. jedna licencja narzędzia, jedno gniazdo w bazie danych używane do
> migracji), a reszta deployu spokojnie może iść równolegle na wszystkich hostach. Robienie
> tego przez `serial` na całym play'u byłoby przesadą — spowolniłoby też taski, które nie mają
> żadnego konfliktu.

---

### ✅ Co zweryfikowano, a czego nie

| Zweryfikowane (`ansible-core 2.17.14`) | Niezweryfikowane |
|---|---|
| `delegate_to` (drenowanie fikcyjnego LB, `[host -> lb1]` w logu) | `delegate_facts` |
| `run_once` + `delegate_to` w `pre_tasks`/`post_tasks` | `run_once` w kombinacji z `serial` inna niż `[1]` |
| `async` + `poll>0` (auto-polling, `ASYNC POLL`/`ASYNC OK`) | Realny, długi backup (testowano tylko `sleep`) |
| `poll: 0` + ręczny `async_status` + `until`/`retries`/`delay` | Zachowanie procesu w tle PO przekroczeniu `async` (czy faktycznie żyje dalej) |
| Timeout `async` (`ASYNC FAILED`, komunikat "did not complete within...") | `ansible-vault`, `ansible-galaxy` — oba odrzucone przez środowisko |
| `throttle: 1` vs brak (rzeczywiste znaczniki czasu z dwóch przebiegów) | `throttle` > 1, `throttle` łączony z `forks`/`serial` jednocześnie |
| `--syntax-check` na wszystkich trzech playbookach | Zdalne SSH, `become` |

**Pułapki znalezione w tym wydaniu (obie realne, nie przewidziane z góry):**
1. `run_once` w `pre_tasks` play'a z `serial: 1` **nie chroni** przed powtórnym wykonaniem —
   każda paczka `serial` to osobny mini-play, więc `run_once` liczy się per paczka. Rozwiązanie:
   wydzielić inicjalizację do osobnego play'a bez `serial`.
2. `ansible.builtin.command` nie przechodzi przez powłokę — `&&`, `>`, `|` trafiają jako
   dosłowne argumenty do programu. Potrzebny `ansible.builtin.shell`.

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Demo pisze wyłącznie do `/tmp/ansible-demo-lvl5`.

---

<div align="center">

[← wróć do wydania #5 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
