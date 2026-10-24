<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #2 — 25 września 2026

![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)

## Handlery, szablony, pętle i pierwsza rola — czyli jak nie restartować usługi „na zapas”

</div>

---

> _"Restart produkcji bez powodu to nie automatyzacja, to hazard. Handler restartuje
> tylko wtedy, gdy coś naprawdę się zmieniło."_

W [wydaniu #1](../../2026-09-24/ansible/ARTICLE.md) był playbook z trzema taskami i
dowód idempotencji. Dziś stopień wyżej: **szablony Jinja2** (`template`), **pętle**
(`loop`), **warunki** (`when`), **handlery** (`notify` / `flush_handlers`) i
**rola** — czyli sposób pakowania tego wszystkiego w wielokrotnego użytku moduł.
Wszystko uruchomione naprawdę, na `localhost` (`ansible_connection=local`), bez
`sudo`/`become`. Kod: [`code/`](code/).

---

### 🎯 Problem, który to rozwiązuje

Klasyczny scenariusz z Twojego świata: zmieniasz `appsettings.json` na serwerze i
musisz zrestartować aplikację, żeby przeczytała nową konfigurację. Naiwne rozwiązanie:
„zawsze restartuj na końcu”. Skutek: każdy przebieg playbooka (np. z crona) ubija
usługę, choć nic się nie zmieniło. Ansible ma na to wbudowany mechanizm — **handler**.

| Pojęcie | Analogia z .NET | Po co |
|---|---|---|
| `template` + Jinja2 | Razor / `string.Format` z logiką (`if`, `for`) | Plik konfiguracyjny generowany ze zmiennych |
| `loop` | `foreach` | Jeden task, wiele elementów |
| `when` | `if` | Task wykonuje się warunkowo (inaczej: `skipping`) |
| `notify` + handler | event, który odpala się **raz** i **tylko przy zmianie** | Restart/reload tylko gdy trzeba |
| `meta: flush_handlers` | „wykonaj oczekujące handlery teraz” | Kolejne taski widzą już efekt handlera |
| rola | biblioteka klas / projekt NuGet | Reużywalny pakiet tasków, szablonów i domyślnych wartości |

---

### 🗂️ Rola — struktura katalogów

Rola to po prostu **konwencja nazw katalogów**. Ansible sam ładuje `main.yml` z
każdego z nich (układ zgodny z tym, co generuje `ansible-galaxy init`; tutaj
stworzony ręcznie, samego `ansible-galaxy init` nie uruchamiałem):

```
code/
├── inventory
├── site.yml                     # play: hosts + roles
└── roles/app_config/
    ├── defaults/main.yml        # zmienne domyślne (najniższy priorytet)
    ├── tasks/main.yml           # taski roli
    ├── handlers/main.yml        # handlery roli
    ├── templates/*.j2           # szablony Jinja2
    └── meta/main.yml            # metadane roli
```

Play w `site.yml` robi się banalny:

```yaml
- name: Poziom 2 - rola app_config, szablony, pętle, warunki i handlery
  hosts: demo
  gather_facts: true
  gather_subset:
    - min
  roles:
    - role: app_config
```

> 💡 **Dlaczego to ważne:** `defaults/main.yml` to „publiczne API” roli — dowolną
> wartość nadpiszesz z inventory, ze zmiennych playa albo z `-e`, bez ruszania kodu
> roli. Rola jest kontraktem: „daj mi te zmienne, dostaniesz taki stan”.

---

### 🧩 Szablon Jinja2

`templates/app.conf.j2`:

```jinja
# {{ ansible_managed }}
[app]
name = {{ app_name }}
port = {{ app_port }}
log_level = {{ log_level | upper }}
system = {{ ansible_facts['system'] }}
{% if enable_metrics | bool %}

[metrics]
enabled = true
endpoint = /metrics
{% endif %}

[sites]
{% for site in sites if site.enabled %}
{{ site.name }} = {{ site.port }}
{% endfor %}
```

Widać tu: interpolację `{{ }}`, filtr (`| upper`), warunek `{% if %}`, pętlę
`{% for %}` z filtrem inline oraz **fakt** (`ansible_facts['system']` — Ansible na
starcie playa zbiera informacje o maszynie; `gather_subset: min` ogranicza to do
minimum, więc jest szybko).

Task, który z tego korzysta:

```yaml
- name: Główny plik konfiguracyjny z szablonu Jinja2
  ansible.builtin.template:
    src: app.conf.j2
    dest: "{{ work_dir }}/app.conf"
    mode: "0644"
  notify: Przeładuj usługę
```

`template` jest idempotentny tak jak `copy`: renderuje szablon **w pamięci** i
porównuje z plikiem na dysku. Ta sama treść = `ok`, inna = `changed`.

> ⚠️ **Pułapka, na którą realnie wpadłem podczas pisania tego wydania.** Pierwotnie
> miałem `{% if enable_metrics %}`. Uruchomiłem playbook z `-e enable_metrics=false`
> i… nic się nie zmieniło, a raport pisał „metryki: włączone”. Powód: zmienne z `-e
> klucz=wartość` są **stringami** — `"false"` to niepusty napis, więc w Jinja jest
> *truthy*. Rozwiązanie: filtr `| bool` (`{% if enable_metrics | bool %}`). Ten sam
> filtr stosuję w `when: site.enabled | bool`. Zasada: wszystko, co może przyjść z
> linii poleceń, przepuść przez `| bool`. (Wartości typu bool zapisane w YAML-u,
> jak w `defaults`, są prawdziwymi boolami — ale rola nie wie, skąd dostanie
> nadpisanie.)

---

### 🔁 Pętle i warunki

```yaml
- name: Plik konfiguracyjny per włączona strona (loop + when)
  ansible.builtin.template:
    src: site.conf.j2
    dest: "{{ work_dir }}/sites/{{ site.name }}.conf"
    mode: "0644"
  loop: "{{ sites }}"
  loop_control:
    loop_var: site
    label: "{{ site.name }}"
  when: site.enabled | bool
  notify: Przeładuj usługę

- name: Usuń plik wyłączonych stron (loop + when)
  ansible.builtin.file:
    path: "{{ work_dir }}/sites/{{ site.name }}.conf"
    state: absent
  loop: "{{ sites }}"
  loop_control:
    loop_var: site
    label: "{{ site.name }}"
  when: not (site.enabled | bool)
  notify: Przeładuj usługę
```

- `loop` iteruje po liście słowników `sites` (zdefiniowanej w `defaults`).
- `loop_var: site` zmienia domyślną nazwę `item` na czytelniejszą — **i to
  ważne w rolach**: unika kolizji, gdy pętle się zagnieżdżają.
- `label` skraca log — zamiast wypisywać cały słownik, widzisz tylko `api`.
- `when` jest sprawdzane **osobno dla każdego elementu** pętli; pominięte to
  `skipping`.
- Drugi task to wzorzec „stan docelowy”: strona wyłączona ma **nie mieć** pliku
  (`state: absent`), a nie „kiedyś ją usuń”.

> 💡 **Dlaczego to ważne:** dodanie czwartej strony to jedna linia w liście, a nie
> nowy task. Konfiguracja jest danymi, logika jest jedna.

---

### 🔔 Handler i `flush_handlers`

`handlers/main.yml`:

```yaml
- name: Przeładuj usługę
  ansible.builtin.shell: "echo reload >> {{ work_dir }}/reload.log"
  changed_when: true
```

Prawdziwego serwisu nie mamy, więc „przeładowanie” **symulujemy** dopisaniem linii
do `reload.log` — po przebiegach wystarczy policzyć linie, żeby wiedzieć, ile razy
handler ruszył. (W realnej roli byłoby tu np. `ansible.builtin.service` z
`state: reloaded` — tego nie uruchamiałem, bo wymagałoby uprawnień do systemu.)

Reguły handlerów, które warto znać:

1. Handler odpala się **tylko**, gdy notyfikujący task zgłosił `changed`.
2. Odpala się **maksymalnie raz na play**, nawet jeśli notyfikuje go 10 tasków.
   W naszym pierwszym przebiegu trzy taski (główny plik i dwie strony) zgłosiły
   `changed` — a handler ruszył raz.
3. Domyślnie handlery wykonują się **na końcu playa** (a raczej sekcji `roles`/
   `tasks`). Chcesz, żeby zadziałały wcześniej? `meta: flush_handlers`:

```yaml
- name: Wymuś uruchomienie handlerów TERAZ
  ansible.builtin.meta: flush_handlers
```

> 💡 **Dlaczego to ważne:** typowy przypadek — najpierw zmieniasz konfigurację,
> potem restart, a dopiero potem task „sprawdź, czy usługa odpowiada”. Bez
> `flush_handlers` sprawdzenie wykonałoby się na starej wersji usługi.

---

### 🏃 Przebieg 1 — pierwsze uruchomienie (wszystko `changed`)

Prawdziwy output (pominięto nieszkodliwy `[WARNING]` o wykrytym interpreterze
Pythona):

```
TASK [app_config : Katalogi robocze (pętla po liście)] *************************
changed: [localhost] => (item=/tmp/ansible-demo-lvl2)
changed: [localhost] => (item=/tmp/ansible-demo-lvl2/sites)

TASK [app_config : Główny plik konfiguracyjny z szablonu Jinja2] ***************
changed: [localhost]

TASK [app_config : Plik konfiguracyjny per włączona strona (loop + when)] ******
changed: [localhost] => (item=api)
changed: [localhost] => (item=admin)
skipping: [localhost] => (item=legacy) 

TASK [app_config : Usuń plik wyłączonych stron (loop + when)] ******************
skipping: [localhost] => (item=api) 
skipping: [localhost] => (item=admin) 
ok: [localhost] => (item=legacy)

TASK [app_config : Wymuś uruchomienie handlerów TERAZ] *************************

RUNNING HANDLER [app_config : Przeładuj usługę] ********************************
changed: [localhost]

...
PLAY RECAP *********************************************************************
localhost                  : ok=8    changed=4    unreachable=0    failed=0    skipped=0 ...
```

Wynik: `legacy` (`enabled: false`) nie dostał pliku, `api` i `admin` — tak.
`reload.log` ma jedną linię.

### 🏃 Przebieg 2 — idempotencja i **brak** handlera

Te same polecenie, nic nie zmienione:

```
TASK [app_config : Główny plik konfiguracyjny z szablonu Jinja2] ***************
ok: [localhost]
...
TASK [app_config : Wymuś uruchomienie handlerów TERAZ] *************************

TASK [app_config : Ten task widzi już efekt handlera] **************************
ok: [localhost]
...
PLAY RECAP *********************************************************************
localhost                  : ok=7    changed=0    unreachable=0    failed=0    skipped=0 ...
```

Kluczowe: **nie ma linii `RUNNING HANDLER`**. Handler się nie odpalił, bo żaden
task nie zgłosił `changed`. Licznik `ok` spadł z 8 do 7, bo brakuje właśnie handlera.

### 🏃 Przebieg 3 — zmiana jednej zmiennej, handler wraca

```bash
ansible-playbook -i inventory site.yml -e log_level=debug
```

```
TASK [app_config : Główny plik konfiguracyjny z szablonu Jinja2] ***************
changed: [localhost]

TASK [app_config : Plik konfiguracyjny per włączona strona (loop + when)] ******
ok: [localhost] => (item=api)
ok: [localhost] => (item=admin)
skipping: [localhost] => (item=legacy) 
...
RUNNING HANDLER [app_config : Przeładuj usługę] ********************************
changed: [localhost]
...
PLAY RECAP: ok=8 changed=2 ...
```

Zmienił się tylko `app.conf` (poziom logowania), strony zostały `ok` — a handler
ruszył, bo jeden notyfikujący task miał `changed`.

### 🏃 Przebieg 4 — `--check --diff`, czyli „pokaż, co byś zrobił”

Wróciłem do `log_level=info` i wyłączyłem metryki (`-e enable_metrics=false`),
uruchamiając w trybie **suchym** — nic nie jest zapisywane, ale widzisz różnicę:

```bash
ansible-playbook -i inventory site.yml -e enable_metrics=false --check --diff
```

```
TASK [app_config : Główny plik konfiguracyjny z szablonu Jinja2] ***************
--- before: /tmp/ansible-demo-lvl2/app.conf
+++ after: <katalog tymczasowy Ansible>/app.conf.j2
@@ -2,12 +2,8 @@
 [app]
 name = shop
 port = 8080
-log_level = DEBUG
+log_level = INFO
 system = Linux
-
-[metrics]
-enabled = true
-endpoint = /metrics
 
 [sites]
 api = 8081

changed: [localhost]
...
RUNNING HANDLER [app_config : Przeładuj usługę] ********************************
skipping: [localhost]
...
PLAY RECAP: ok=7 changed=1 ... skipped=1 ...
```

(Ścieżkę „after” zamieniłem na opis — w oryginale to katalog tymczasowy w profilu
użytkownika.) Zauważ `skipping` przy handlerze: w trybie `--check` moduł `shell`
nie jest wykonywany. Uwaga: to zachowanie modułu `shell`/`command` w check mode
(moduły nieobsługujące check mode są pomijane); handler wywołujący moduł, który
check mode obsługuje (np. `service`), zostałby „symulowany”.

> 💡 **Dlaczego to ważne:** `--check --diff` to odpowiednik `terraform plan` /
> `dotnet ef migrations script` — podgląd zmian przed uruchomieniem na produkcji.

### 🏃 Przebieg 5 — dane zamiast kodu: przełączenie stron

Nadpisanie całej listy `sites` przez JSON w `-e` (api wyłączone, legacy włączone):

```
TASK [app_config : Plik konfiguracyjny per włączona strona (loop + when)] ******
skipping: [localhost] => (item=api) 
ok: [localhost] => (item=admin)
changed: [localhost] => (item=legacy)

TASK [app_config : Usuń plik wyłączonych stron (loop + when)] ******************
changed: [localhost] => (item=api)
skipping: [localhost] => (item=admin) 
skipping: [localhost] => (item=legacy) 
```

Plik `api.conf` zniknął, `legacy.conf` powstał, `admin` bez zmian — i znów jeden
`RUNNING HANDLER`. Po wszystkich rzeczywistych przebiegach `reload.log` miał
**3 linie** (przebiegi 1, 3 i 5 — tam, gdzie coś się zmieniło; przebiegi 2 i 4
nie dopisały nic).

---

### ✅ Co zweryfikowano, a czego nie

| Zweryfikowane (uruchomione, `ansible-core 2.17.14`, Python 3.10) | Niezweryfikowane |
|---|---|
| `--syntax-check` | Handler z prawdziwą usługą (`service`/`systemd`) — wymaga `become` |
| Przebiegi 1–5 opisane wyżej, w tym idempotencja i brak handlera | `ansible-galaxy init` (strukturę stworzyłem ręcznie wg konwencji) |
| Błąd `-e enable_metrics=false` (string vs bool) i jego poprawka | Zachowanie na zdalnych hostach przez SSH |
| Zawartość wygenerowanych plików i `reload.log` | Inne wersje ansible-core niż 2.17 |

Uwaga do przebiegów 1–3: zostały wykonane, zanim dodałem `| bool` do szablonu i
raportu; poprawka nie zmienia ich wyniku (przy domyślnym `true`), a przebiegi 4–5
uruchomiłem już po niej. Przebieg z błędnym zachowaniem (`-e enable_metrics=false`
bez `| bool` → „metryki: włączone”, zero zmian) jest opisany w ramce z pułapką.

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — komendy, oczekiwane wyniki i sprzątanie.
Katalog roboczy demo to `/tmp/ansible-demo-lvl2` (nie dotyka niczego poza `/tmp`).

---

<div align="center">

[← wróć do wydania #2 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
