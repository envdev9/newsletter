# Kod do wydania #15 — pierwszeństwo zmiennych (variable precedence)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Ta sama zmienna może być zdefiniowana w wielu warstwach naraz; wygrywa jedna. Zmierzona
> drabinka (od najsłabszej): `role defaults` < `group_vars/all` < `group_vars/<grupa>` <
> `host_vars` < `vars:` playa < `vars_files` < `vars/` roli < `vars:` taska < `include_vars` <
> `set_fact` < `-e`. Niespodzianki: `vars/` roli bije `vars:` playa, a `include_vars` bije
> zmienną na tasku. Dwie grupy tego samego poziomu: wygrywa późniejsza alfabetycznie, chyba że
> ustawisz `ansible_group_priority`.
>
> Czego nie zweryfikowano: parametrów roli, `block` vars, `register`, `vars_prompt`,
> `ansible-vault`/`galaxy`, Molecule, SSH/`become`.

## Pliki

- [`precedence.yml`](precedence.yml) — 10 pojedynków warstw (host `node1`).
- [`groups.yml`](groups.yml) — dwie równorzędne grupy (host `node2`).
- `inventory/` — `hosts.ini`, `group_vars/{all,web}.yml`, `host_vars/node1.yml`.
- `inventory_priority/hosts.ini` — to samo co grupy, ale `alpha` z `ansible_group_priority=10`.
- `roles/demo/{defaults,vars}/main.yml`, `vars/{extra_file,included}.yml`.

Wymagania: `ansible-core` (testowane 2.17.14). Bez `sudo`, nic nie jest zapisywane na dysku.

## Uruchomienie

```bash
cd days/2026-10-08/ansible/code

ansible-playbook --syntax-check -i inventory/hosts.ini precedence.yml

ansible-playbook -i inventory/hosts.ini precedence.yml
ansible-playbook -i inventory/hosts.ini precedence.yml -e d10=extra_vars

ansible-playbook -i inventory/hosts.ini groups.yml
ansible-playbook -i inventory_priority/hosts.ini groups.yml
```

Jeśli `ansible-playbook` zgłasza `Ansible requires blocking IO on stdin/stdout/stderr`
(powłoka agentowa/CI), dopisz `2>&1 | cat`.

## Prawdziwy output (skrót)

```
"d06 vars_files     vs role vars         -> role vars",
"d08 task vars      vs include_vars      -> include_vars",
"d10 play+set_fact  vs -e (jesli podano) -> set_fact"        (z -e d10=extra_vars: extra_vars)
kolor = beta     (inventory/)
kolor = alpha    (inventory_priority/)
```

## Uwagi

- Każdy scenariusz uruchomiony raz; wyniki zgodne z dokumentacją Ansible.
- Sprzątanie: nic nie powstało poza katalogiem wydania.
