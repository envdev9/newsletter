# Kod do wydania #18 — parametry roli, `argument_specs`, `include_role`, `block` vars, `set_stats`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> `roles:` wykonuje rolę raz dla danej kombinacji nazwa + parametry (chyba że `allow_duplicates:
> true`); `include_role` to zwykły task i zawsze się wykona. `meta/argument_specs.yml` waliduje typy,
> `required` i `choices` przed pierwszym taskiem roli — ale nieznany parametr nie jest błędem.
> Po `roles:`/`import_role` w playu widać **default** roli (nie przekazany parametr); `include_role`
> nic nie ujawnia bez `public: true`, a `register` z roli jest widoczny zawsze. `vars:` na `block`
> działa leksykalnie i obejmuje też role wywołane w bloku. `set_stats` z `aggregate: true` zsumuje
> liczby, ale sklei napisy (`"2"+"5"+"3"` = `"253"`) — a szablon Jinja zawsze zwraca napis.
>
> Czego nie zweryfikowano: `show_custom_stats` jako wbudowane wyjście, `include_role` z `apply:`,
> `private_role_vars`, vault/galaxy/Molecule, SSH/`become`.

## Pliki

- [`role_params.yml`](role_params.yml) — deduplikacja `roles:`, `include_role` w pętli, `tasks_from`.
- [`role_validate.yml`](role_validate.yml) — 5 przypadków walidacji `argument_specs`.
- [`role_scope.yml`](role_scope.yml) — wyciek zmiennych: `roles:` / `include_role` / `public` / `import_role`.
- [`block_vars.yml`](block_vars.yml) — `vars:` na `block`, zagnieżdżenie, rola w bloku.
- [`set_stats.yml`](set_stats.yml) + [`callback_plugins/dump_custom_stats.py`](callback_plugins/dump_custom_stats.py).
- [`roles/`](roles/) — `svc_unit` (defaults, `meta/argument_specs.yml`, `tasks/main.yml`, `tasks/health.yml`),
  `svc_note`, `svc_unit_dup` (`allow_duplicates: true`).
- [`cleanup.yml`](cleanup.yml) — usuwa `/tmp/ansible-demo-lvl18`.
- [`inventory.ini`](inventory.ini) — `localhost` (grupa `local`) i `n1..n3` (grupa `fleet`), wszystkie
  `ansible_connection=local`.

Wymagania: `ansible-core` (testowane 2.17.14), `python3`. Bez `sudo`.

## Uruchomienie

```bash
cd days/2026-10-11/ansible/code

ansible-playbook --syntax-check -i inventory.ini role_params.yml
ansible-playbook --syntax-check -i inventory.ini role_validate.yml
ansible-playbook --syntax-check -i inventory.ini role_scope.yml
ansible-playbook --syntax-check -i inventory.ini block_vars.yml
ansible-playbook --syntax-check -i inventory.ini set_stats.yml

# deduplikacja + include_role w pętli (drugi przebieg: changed=0)
ansible-playbook -i inventory.ini role_params.yml
ansible-playbook -i inventory.ini role_params.yml

# walidacja argument_specs, wyciek zmiennych, zmienne bloku
ansible-playbook -i inventory.ini role_validate.yml
ansible-playbook -i inventory.ini role_scope.yml
ansible-playbook -i inventory.ini block_vars.yml

# set_stats: dump_custom_stats.py wypisuje CUSTOM_STATS_JSON na końcu
ansible-playbook -i inventory.ini set_stats.yml
# wbudowane wyjście (niezweryfikowane tutaj):
ANSIBLE_SHOW_CUSTOM_STATS=true ansible-playbook -i inventory.ini set_stats.yml

# sprzątanie
ansible-playbook -i inventory.ini cleanup.yml
```

Jeśli `ansible-playbook` zgłasza `Ansible requires blocking IO on stdin/stdout/stderr`
(powłoka agentowa/CI), dopisz `2>&1 | cat`.

## Prawdziwy output (skrót)

```
role_params.yml   run 1: ok=22 changed=3    run 2: ok=22 changed=0
   roles: svc_note tag=one, tag=two (trzecie, identyczne z pierwszym, pominięte);
          svc_unit_dup tag=same x2 (allow_duplicates)

role_validate.yml  rescued=3
   missing required arguments: svc_name
   value of svc_env must be one of: dev, stage, prod, got: qa
   argument 'svc_port' ... unable to convert to int
   svc_color: red -> przeszło;  svc_port: "9500" -> przeszło (port=9500)

role_scope.yml    (svc_port widoczny w playu po roli: 8080, nie przekazany 9100..9400)
   roles: 8080/dev/result=True   include_role: NIEDEFINIOWANE/NIEDEFINIOWANE/result=True
   include_role public: 8080/dev   import_role: 8080/dev

block_vars.yml    env=play-level -> outer-block -> inner-block -> task-level -> outer-block -> play-level
   rola w bloku z vars svc_env=prod, svc_replicas=4: "env=prod replicas=4"

set_stats.yml
   CUSTOM_STATS_JSON: {"_run": {"aggregate_off": "3", "hosts_done": 3, "last_host": "n3",
     "units_sum_once": "10", "units_total": "253"}, "n1": {"written_changed": false}, ...}
```

## Uwagi

- `roles/svc_unit/tasks/health.yml` nie ma własnej specyfikacji argumentów (tylko `main`).
- `vars: "{{ slownik }}"` w `include_role` jest błędem (`Vars in a IncludeRole must be specified as
  a dictionary`) — dlatego `role_validate.yml` ma pięć jawnych bloków.
- `callback_plugins/dump_custom_stats.py` ma `CALLBACK_NEEDS_ENABLED = False`, więc ładuje się sam,
  gdy leży obok playbooka — bez `ansible.cfg`.
- `.gitignore`/sprzątanie: po uruchomieniu może powstać `callback_plugins/__pycache__` (Python),
  można go usunąć.
