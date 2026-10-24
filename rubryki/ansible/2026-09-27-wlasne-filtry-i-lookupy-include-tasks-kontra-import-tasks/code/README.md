# Kod do wydania #4 — własne filtry/lookupy, include vs import, serial, strategy

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Własny filtr Jinja2 to plik Pythona w `filter_plugins/` obok playbooka, a własny lookup to plik w
> `lookup_plugins/` (wykonuje się na kontrolerze). `import_tasks` jest statyczne (widoczne w
> `--list-tasks`, tagi i `when` dziedziczą wszystkie taski z pliku, `loop` zabronione), a
> `include_tasks` dynamiczne (tag dotyczy tylko samego include — chyba że użyjesz `apply` —
> ale działa `loop`). `serial` dzieli hosty na paczki (rolling update), a `max_fail_percentage: 0`
> przerywa kolejne paczki po awarii. `strategy: free` zdejmuje barierę między taskami.
> **Uwaga: `ansible-vault` został w tym wydaniu odrzucony przez system uprawnień środowiska —
> szyfrowania nie uruchomiłem.**

## Pliki

- [`inventory.ini`](inventory.ini) — grupa `web`: `web1..web4` (wszystkie `ansible_connection=local`).
- [`group_vars/all/vars.yml`](group_vars/all/vars.yml), [`group_vars/all/vault.yml`](group_vars/all/vault.yml)
  (jawne, fikcyjne wartości), [`.vault_pass_demo`](.vault_pass_demo) (fikcyjne hasło demo).
- [`filter_plugins/demo_filters.py`](filter_plugins/demo_filters.py), [`lookup_plugins/kv_file.py`](lookup_plugins/kv_file.py),
  [`files/release.env`](files/release.env), [`filters.yml`](filters.yml).
- [`tasks/step.yml`](tasks/step.yml), [`include_vs_import.yml`](include_vs_import.yml), [`import_loop_error.yml`](import_loop_error.yml).
- [`serial.yml`](serial.yml), [`strategy.yml`](strategy.yml).

Wymagania: `ansible-core` (testowane 2.17.14, Python 3.10), bez `sudo`. Zapisy tylko do `/tmp/ansible-demo-lvl4`.

> Uwaga środowiskowa: w powłoce agenta Ansible wymagał `... 2>&1 | cat` (blocking IO). W zwykłym
> terminalu wystarczy sama komenda.

## Uruchomienie (z katalogu `code/`)

```bash
# filtry i lookup (oczekiwane 2 błędy ignorowane: ignored=2)
ansible-playbook -i inventory.ini filters.yml --syntax-check
ansible-playbook -i inventory.ini filters.yml
ansible-playbook -i inventory.ini filters.yml --tags write     # changed=0

# include vs import
ansible-playbook -i inventory.ini include_vs_import.yml --list-tasks
ansible-playbook -i inventory.ini include_vs_import.yml
ansible-playbook -i inventory.ini include_vs_import.yml --tags inner     # tylko wnętrze importu
ansible-playbook -i inventory.ini include_vs_import.yml --tags inc       # tylko sam include
ansible-playbook -i inventory.ini include_vs_import.yml --tags applied   # include + wnętrze (apply)
ansible-playbook -i inventory.ini include_vs_import.yml --tags imp,inc -e do_import=false -e do_include=false
ansible-playbook -i inventory.ini import_loop_error.yml                  # oczekiwany ERROR!

# serial
ansible-playbook -i inventory.ini serial.yml
ansible-playbook -i inventory.ini serial.yml -e fail_host=web2           # web4 nietknięty

# strategy
ansible-playbook -i inventory.ini strategy.yml
ansible-playbook -i inventory.ini strategy.yml -e strat=free
```

## Vault (NIEZWERYFIKOWANE w wydaniu — do wykonania u siebie)

```bash
ansible-vault encrypt --vault-password-file .vault_pass_demo group_vars/all/vault.yml
ansible-vault view    --vault-password-file .vault_pass_demo group_vars/all/vault.yml
ansible-vault encrypt_string --vault-password-file .vault_pass_demo 'DEMO-tajne' --name vault_x
ansible-playbook -i inventory.ini filters.yml --vault-password-file .vault_pass_demo
```

Hasło demo jest fikcyjne i jawne (repo publiczne); w prawdziwym projekcie plik z hasłem trafia do
`.gitignore` albo do menedżera sekretów.

## Sprzątanie

```bash
rm -rf /tmp/ansible-demo-lvl4
```

## Czego nie zweryfikowano

- `ansible-vault` (encrypt / view / encrypt_string / zły hasło) — polecenie odrzucone.
- `ansible-galaxy`, kolekcje, Molecule — nie próbowane.
- `serial` z procentami, `throttle`, zdalne SSH, `become`; zawartość `app.env` (nie odczytana).
