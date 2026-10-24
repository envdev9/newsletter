# Kod do wydania #2 — Handlery, szablony, pętle i pierwsza rola

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Rola `app_config` renderuje plik konfiguracyjny z szablonu Jinja2, tworzy osobny
> plik dla każdej włączonej „strony" (`loop` + `when`), usuwa pliki wyłączonych, a
> `notify` uruchamia handler „Przeładuj usługę" **tylko wtedy, gdy coś się zmieniło**
> — i to najwyżej raz na play. `meta: flush_handlers` wymusza jego wykonanie od razu,
> zanim ruszą kolejne taski. Drugi przebieg bez zmian: `changed=0` i zero linii
> `RUNNING HANDLER`. Pułapka: `-e enable_metrics=false` to string, więc w Jinja
> trzeba `| bool`.

## Pliki

- [`inventory`](inventory) — `localhost`, `ansible_connection=local`.
- [`site.yml`](site.yml) — play z rolą.
- [`roles/app_config/`](roles/app_config/) — `defaults`, `tasks`, `handlers`,
  `templates`, `meta`.

Wymagania: `ansible-core` (testowane na 2.17.14, Python 3.10), bez `sudo`. Instalacja:
`python3 -m pip install --user ansible-core` (patrz [wydanie #1](../../../2026-09-24/ansible/code/README.md)).
Demo pisze wyłącznie do `/tmp/ansible-demo-lvl2` (zmienna `work_dir`).

> Uwaga środowiskowa: w mojej powłoce agenta Ansible odmawiał startu z błędem
> „requires blocking IO on stdin/stdout/stderr”; pomogło dopięcie wyjścia do potoku
> (`... 2>&1 | cat`). W zwykłym terminalu wystarczy sama komenda `ansible-playbook`.

## Uruchomienie (z katalogu `days/2026-09-25/ansible/code`)

```bash
# 1. składnia
ansible-playbook -i inventory site.yml --syntax-check
# 2. pierwszy przebieg: changed=4, handler odpala się raz
ansible-playbook -i inventory site.yml
# 3. drugi przebieg: changed=0, BRAK "RUNNING HANDLER"
ansible-playbook -i inventory site.yml
# 4. zmiana jednej zmiennej: zmienia się app.conf, handler wraca
ansible-playbook -i inventory site.yml -e log_level=debug
# 5. podgląd zmian bez zapisu (handler shell jest w check mode pomijany)
ansible-playbook -i inventory site.yml -e enable_metrics=false --check --diff
# 6. przełączenie stron danymi
ansible-playbook -i inventory site.yml -e '{"sites":[{"name":"api","port":8081,"enabled":false},{"name":"admin","port":8082,"enabled":true},{"name":"legacy","port":8083,"enabled":true}]}'
```

Podgląd wyników:

```bash
cat /tmp/ansible-demo-lvl2/app.conf
cat /tmp/ansible-demo-lvl2/reload.log
```

Prawdziwy `app.conf` po pierwszym przebiegu:

```
# Ansible managed
[app]
name = shop
port = 8080
log_level = INFO
system = Linux

[metrics]
enabled = true
endpoint = /metrics

[sites]
api = 8081
admin = 8082
```

Kluczowe fragmenty prawdziwego outputu (pełne przebiegi w artykule):

```
# przebieg 1
RUNNING HANDLER [app_config : Przeładuj usługę] ********************************
changed: [localhost]
PLAY RECAP: localhost : ok=8  changed=4  unreachable=0  failed=0  skipped=0

# przebieg 2 (idempotencja, handlera brak)
PLAY RECAP: localhost : ok=7  changed=0  unreachable=0  failed=0  skipped=0
```

Po krokach 2, 4 i 6 (tam, gdzie były zmiany) `reload.log` ma 3 linie
`reload`.

## Sprzątanie

```bash
rm -rf /tmp/ansible-demo-lvl2
```

W `code/` nic się nie generuje (wszystko ląduje w `/tmp`).

## Czego nie zweryfikowano

- Handler z prawdziwą usługą (`ansible.builtin.service`) — wymaga uprawnień
  administratora; tu symulacja przez `reload.log`.
- `ansible-galaxy init` — struktura roli stworzona ręcznie wg tej samej konwencji.
- Połączenia SSH do zdalnych hostów.
