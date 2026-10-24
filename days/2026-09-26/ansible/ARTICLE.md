<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #3 — 26 września 2026

![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)

## Grupy hostów, `block/rescue/always`, `failed_when` i tagi — czyli playbook, który potrafi się wycofać

</div>

---

> _"Automatyzacja bez planu B to skrypt, który padnie o 3:00 w nocy w połowie
> wdrożenia. `rescue` to Twój `try/catch`, `always` to `finally`."_

W [wydaniu #1](../../2026-09-24/ansible/ARTICLE.md) były taski i idempotencja, w
[#2](../../2026-09-25/ansible/ARTICLE.md) szablony, pętle i handlery. Dziś: **inventory
z grupami i `group_vars`/`host_vars`**, **`block/rescue/always`**, **`register` +
`failed_when`/`changed_when`**, **tagi**, **filtry Jinja2** i **`ansible-vault`**.
Trzy „hosty” (`web1`, `web2`, `db1`) to w rzeczywistości ta sama maszyna
(`ansible_connection=local`) — Ansible widzi jednak trzy serwery w dwóch grupach.
Kod: [`code/`](code/).

> ⚠️ **Ważne zastrzeżenie.** W środowisku, w którym powstawało to wydanie, system
> uprawnień odrzucił polecenie `ansible-vault` (oraz `ansible-inventory`). Nie
> obchodziłem tego. Skutek: **sekcja o vaulcie jest opisem, nie zweryfikowanym
> wynikiem** — plik `vault.yml` w repo jest jawny (fikcyjne wartości), a komendy
> szyfrowania są w README do wykonania u siebie. Wszystko inne uruchomiłem naprawdę
> (`ansible-core 2.17.14`).

---

### 🎯 Problem, który to rozwiązuje

Masz kilka środowisk i typów serwerów. Port, poziom logów, hasła — różne dla każdego.
Wdrożenie konfiguracji może się nie udać w połowie. Sekrety nie mogą leżeć w Gicie
jawnym tekstem. To wszystko rozwiązuje ten zestaw:

| Pojęcie | Analogia z .NET | Po co |
|---|---|---|
| grupy + `group_vars` / `host_vars` | `appsettings.json` → `appsettings.Production.json` → user secrets | Warstwowa konfiguracja: wspólne → grupa → host |
| `block` / `rescue` / `always` | `try` / `catch` / `finally` | Wycofanie zmian i sprzątanie |
| `register` | zmienna na wynik wywołania | Zapamiętaj `rc`, `stdout` polecenia |
| `failed_when` / `changed_when` | własny warunek `if (exitCode ...)` | Ty definiujesz, co jest błędem i co zmianą |
| `tags` | filtr testów `--filter` | Uruchom tylko wycinek playbooka |
| filtry Jinja2 | LINQ (`OrderBy`, `String.Join`) | Przetwarzanie danych w szablonach |
| `ansible-vault` | `dotnet user-secrets` / Key Vault (ale plikowo) | Szyfrowane zmienne w repo |

---

### 🗂️ Inventory grupowe i warstwy zmiennych

```ini
[web]
web1 ansible_connection=local
web2 ansible_connection=local

[db]
db1 ansible_connection=local

[app:children]      # grupa grup
web
db
```

Zmienne leżą obok playbooka — Ansible sam je dopasowuje po nazwie grupy/hosta:

```
code/
├── inventory.ini
├── site.yml
├── group_vars/
│   ├── all/vars.yml, vault.yml   # wszyscy
│   ├── web.yml                   # service_port: 8080
│   └── db.yml                    # service_port: 5432, log_level: warning
└── host_vars/
    └── web2.yml                  # service_port: 8081, log_level: debug
```

Kolejność (od najsłabszego): `group_vars/all` → `group_vars/<grupa>` →
`host_vars/<host>` → `-e` z linii poleceń (zawsze wygrywa). Dowód z prawdziwego
przebiegu — końcowy task „Porty wszystkich hostów” (filtry `zip` + `extract` na
`hostvars`):

```
ok: [web1] => {
    "msg": "{\"web1\": 8080, \"web2\": 8081, \"db1\": 5432}"
}
```

`web1` dostał port z grupy `web`, `web2` z własnego `host_vars`, `db1` z grupy `db`.

> 💡 **Dlaczego to ważne:** dodanie nowego serwera to jedna linia w inventory —
> resztę odziedziczy z grupy. Różnica między środowiskami to różne pliki
> `group_vars`, a nie kopie playbooków.

---

### 🧩 Filtry Jinja2 w praktyce

`templates/app.conf.j2`:

```jinja
[app]
host = {{ inventory_hostname }}
group = {{ group_names | sort | join(',') }}
env = {{ env | upper }}
port = {{ service_port }}
log_level = {{ log_level | default('info') | upper }}
features = {{ features | sort | join(',') }}
api_key_fingerprint = {{ api_key | hash('sha256') | truncate(12, True, '') }}
```

Wynik dla `web2` (prawdziwy plik):

```
host = web2
group = app,web
env = DEV
port = 8081
log_level = DEBUG
features = audit,cache,metrics
api_key_fingerprint = 272994f19a59
```

Do tego `settings.json` przez `combine` (rekurencyjne scalanie słowników:
domyślne z `group_vars/all` + nadpisanie z `host_vars/web2`) i `to_nice_json`. Dla
`web2` `timeouts.read` wynosi 60, a `connect` zostaje 5 — nadpisany tylko jeden klucz:

```
{
    "retries": 3,
    "timeouts": {
        "connect": 5,
        "read": 60
    }
}
```

> 💡 **Dlaczego to ważne:** w szablonie nigdy nie wypisuj sekretu — pokaż jego
> *odcisk* (`hash`), żeby dało się sprawdzić, że wdrożył się właściwy klucz.

---

### 🛟 `block` / `rescue` / `always` — wdrożenie z wycofaniem

```yaml
- name: Wdrozenie konfiguracji z automatycznym wycofaniem
  tags: [config]
  block:
    - name: Wyrenderuj app.conf
      ansible.builtin.template: {src: app.conf.j2, dest: "{{ host_dir }}/app.conf", mode: "0644"}
    - name: Zwaliduj konfiguracje
      ansible.builtin.command:
        argv: [sh, "{{ playbook_dir }}/files/validate.sh", "{{ host_dir }}/app.conf"]
      changed_when: false
    - name: Zapamietaj ostatnia dobra konfiguracje
      ansible.builtin.copy: {src: "{{ host_dir }}/app.conf", dest: "{{ host_dir }}/app.conf.last-good", remote_src: true}
  rescue:
    - ansible.builtin.debug:
        msg: "Padl task '{{ ansible_failed_task.name }}' (rc={{ ansible_failed_result.rc | default('n/a') }})"
    # ... stat + copy last-good z powrotem (albo usuń zły plik, gdy nie ma poprzedniej wersji)
    - ansible.builtin.set_fact: {deploy_status: rolled-back}
  always:
    - ansible.builtin.copy:
        content: "{{ deploy_status | default('ok') }}\n"
        dest: "{{ host_dir }}/deploy.status"
```

(Fragmenty skrócone; pełny kod w `site.yml`.) Wywołałem to ze złym portem
(`-e service_port=abc`) — walidator wymaga liczby:

```
TASK [Zwaliduj konfiguracje] ***
fatal: [web1]: FAILED! => {... "msg": "non-zero return code", "rc": 2, ...
"stderr": "config INVALID: port nie jest liczba", ...}
...
TASK [Co poszlo nie tak] ***
ok: [web1] => { "msg": "Padl task 'Zwaliduj konfiguracje' (rc=2)" }
TASK [Przywroc ostatnia dobra konfiguracje] ***
changed: [web1]
TASK [Brak poprzedniej wersji - usun zla konfiguracje] ***
skipping: [web1]
TASK [Zapisz status wdrozenia (wykonuje sie zawsze)] ***
changed: [web1]

PLAY RECAP
db1   : ok=8  changed=3  unreachable=0  failed=0  skipped=1  rescued=1  ignored=0
web1  : ok=9  changed=3  unreachable=0  failed=0  skipped=1  rescued=1  ignored=0
web2  : ok=8  changed=3  unreachable=0  failed=0  skipped=1  rescued=1  ignored=0
```

Sprawdzone na dysku: `web2/app.conf` znów ma `port = 8081`, a `deploy.status`
zawiera `rolled-back`. Kolejny przebieg z dobrymi wartościami przywrócił status `ok`
(`changed=1` na host — tylko plik statusu).

Co warto wiedzieć:

- `rescue` uruchamia się, gdy **którykolwiek** task w `block` padnie; jeśli `rescue`
  się powiedzie, host **nie** jest `failed` — zobacz `failed=0`, `rescued=1`.
- Zmienne `ansible_failed_task` i `ansible_failed_result` istnieją tylko w `rescue`.
- `always` wykonuje się niezależnie od wyniku (jak `finally`).
- Pułapka logiczna: nasz `block` zapisuje zły plik, dopiero potem go waliduje —
  dlatego potrzebny jest rollback. Lepsza wersja: renderuj do pliku tymczasowego i
  waliduj przed podmianą (moduł `template` ma też parametr `validate`; tu go nie
  używałem).

> 💡 **Dlaczego to ważne:** bez `rescue` padnięty task zostawia hosta w stanie
> połowicznym, a Ansible pomija resztę playbooka dla tego hosta. Z `rescue` masz
> deterministyczny stan końcowy i **czytelny status** do dalszej automatyzacji.

---

### 🔍 `register` + `failed_when` / `changed_when`

Ansible nie wie, co znaczy kod wyjścia Twojego skryptu. Ty mu to mówisz:

```yaml
- name: Healthcheck (rc 0 = OK, 3 = degraded, reszta = blad)
  ansible.builtin.command:
    argv: [sh, "{{ playbook_dir }}/files/health.sh", "{{ host_dir }}/app.conf"]
  register: health
  changed_when: false
  failed_when: health.rc not in [0, 3]
  check_mode: false
```

`web2` ma logowanie `DEBUG`, więc skrypt zwraca rc 3 — dla Ansible to **nie** błąd:

```
ok: [web1] => { "msg": "web1: OK (healthy)" }
ok: [web2] => { "msg": "web2: DEGRADED (degraded: wlaczone logowanie DEBUG)" }
ok: [db1] => { "msg": "db1: OK (healthy)" }
```

Gdy pliku brakuje (rc 2), zadziałał `failed_when` — zwróć uwagę na
`failed_when_result`:

```
fatal: [web1]: FAILED! => {"changed": false, ... "failed_when_result": true,
"msg": "non-zero return code", "rc": 2, ..., "stdout": "brak pliku konfiguracji"}
```

Drugi wzorzec — `changed_when` według treści wyjścia. Udawana migracja bazy
(tylko grupa `db` przez `when: "'db' in group_names"`) drukuje `applied 1 migration`
albo `nothing to do`:

```yaml
  register: migrate
  changed_when: "'applied' in migrate.stdout"
```

Przebieg 1: `changed: [db1]`. Przebieg 2: `ok: [db1]`, a w recapie `changed=0`.
Bez `changed_when` każde `command` zawsze świeci na żółto (`changed`), co niszczy
sygnał idempotencji.

`check_mode: false` przy healthchecku sprawia, że task read-only wykonuje się
**także** w `--check` (domyślnie `command` jest wtedy pomijany).

> 💡 **Dlaczego to ważne:** raport „changed” to Twój wskaźnik, czy coś realnie się
> zmieniło. Jeśli każdy przebieg pokazuje zmiany, nikt nie zauważy tej prawdziwej.

---

### 🏷️ Tagi

Tagi dodajesz do tasków lub bloków (`config`, `check`, `secrets`, `migrate`).
Tag specjalny `always` oznacza „uruchom zawsze, chyba że `--skip-tags always`” —
użyłem go przy tworzeniu katalogu (bez niego `--tags secrets` nie miałoby gdzie
pisać).

```
$ ansible-playbook -i inventory.ini site.yml --list-tags
  play #1 (app): Poziom 3 - vault, grupy, block/rescue/always, tags	TAGS: []
      TASK TAGS: [always, check, config, migrate, secrets]
```

Wycinek: `--skip-tags config,secrets --limit db` uruchomił tylko katalog,
healthcheck, migrację i podsumowanie na `db1` (recap: `ok=5 changed=0`).

> 💡 **Dlaczego to ważne:** zmiana samego hasła to `--tags secrets`, nie
> pełny przebieg po całej flocie. Ale uwaga: tag na tasku, który zależy od
> wcześniejszych tasków (np. `register`), wymaga, by tamte też się wykonały.

---

### 🔐 `ansible-vault` — opis (NIEZWERYFIKOWANY)

Zgodnie z zastrzeżeniem na początku: **nie uruchomiłem `ansible-vault`**. Opisuję
wzorzec z dokumentacji i to, co zrobił mój kod:

1. Sekrety trzymasz w `group_vars/all/vault.yml` ze zmiennymi z prefiksem `vault_`
   i szyfrujesz plik komendą `ansible-vault encrypt`. Przy uruchomieniu podajesz
   hasło (`--vault-password-file` lub `--ask-vault-pass`).
2. W `vars.yml` robisz odwołanie: `db_password: "{{ vault_db_password }}"` — w Gicie
   widać, skąd zmienna pochodzi, bez odszyfrowywania.
3. Task z sekretem dostaje `no_log: true`.

To ostatnie **zweryfikowałem realnie** (na jawnych, fikcyjnych wartościach). Zmieniłem
hasło i uruchomiłem z `--check --diff`:

```
TASK [Plik z sekretami (wartosci z ansible-vault)] ***
changed: [web1]
```

Diff się nie wyświetlił (dla porównania: przy zmianie `env` na `prod` w `app.conf`
diff był widoczny, `-env = DEV` / `+env = PROD`). Plik `secrets.env` powstał z trybem
`0600`.

Czego **nie** wiem z własnego przebiegu: jak wygląda błąd przy braku/złym haśle,
`encrypt_string`, `ansible-vault view`. Repo jest publiczne, więc `vault.yml` jest
jawny z wyraźnie fikcyjnymi wartościami, a `.vault_pass_demo` zawiera jawne
hasło DEMO. Komendy do samodzielnego sprawdzenia są w
[`code/README.md`](code/README.md).

> 💡 **Dlaczego to ważne:** zaszyfrowany plik w repo pozwala mieć całą konfigurację
> w jednym miejscu. Ale pamiętaj: `no_log` i szyfrowanie to dwie różne warstwy —
> szyfrowanie chroni plik w spoczynku, `no_log` chroni logi i diff.

---

### 🏃 Idempotencja — przebieg 1 vs 2

```
# przebieg 1
db1   : ok=10  changed=7  failed=0  skipped=0  rescued=0
web1  : ok=10  changed=6  failed=0  skipped=1  rescued=0
web2  : ok=9   changed=6  failed=0  skipped=1  rescued=0

# przebieg 2 — te same polecenie
db1   : ok=10  changed=0  failed=0  skipped=0  rescued=0
web1  : ok=10  changed=0  failed=0  skipped=1  rescued=0
web2  : ok=9   changed=0  failed=0  skipped=1  rescued=0
```

Liczby `ok` różnią się między hostami, bo podsumowanie (`run_once`) wykonuje się na
pierwszym hoście, a migracja tylko na `db1`.

Obserwacja z realnego przebiegu: w logu Ansible potrafi wypisywać wyniki hostów w
różnej kolejności (`web2, web1, db1`) — taski wykonują się równolegle (`forks`).
Nie polegaj na kolejności.

---

### ✅ Co zweryfikowano, a czego nie

| Zweryfikowane (uruchomione, `ansible-core 2.17.14`, Python 3.10) | Niezweryfikowane |
|---|---|
| `--syntax-check`, `--list-tags` | `ansible-vault` (encrypt/view/encrypt_string, błąd złego hasła) — polecenie odrzucone |
| Przebieg 1 i 2 (idempotencja, `changed=0`) | `ansible-inventory --graph` — odrzucone |
| `block/rescue/always` ze złym portem: `rescued=1`, plik przywrócony | Odczyt zaszyfrowanego `!vault` przez playbook |
| `failed_when` (rc 3 tolerowany, rc 2 = FAILED), `changed_when` | Zdalne SSH, `become` |
| `--tags`, `--skip-tags`, `--limit`, `--check --diff` (+ `no_log` chowa diff) | Parametr `validate` modułu `template` |
| Priorytety `group_vars` / `host_vars`, filtry (`combine`, `join`, `hash` …) | Inne wersje ansible-core |

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Katalog roboczy demo to
`/tmp/ansible-demo-lvl3` — nic poza `/tmp` nie jest ruszane.

---

<div align="center">

[← wróć do wydania #3 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
