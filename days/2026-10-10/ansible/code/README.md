# Kod do wydania #17 — `lineinfile`, `blockinfile`, `template` + `validate`, `assemble`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> `lineinfile` edytuje pojedynczą linię: `regexp` mówi, którą linię uznajemy za naszą — bez niego
> zmiana wartości dopisze kolejną linię, a stara zostanie (i `changed=0` tego nie wykryje).
> `blockinfile` identyfikuje blok po markerze; nadawaj własny. `template` z `validate:
> "python3 -m json.tool %s"` renderuje do pliku tymczasowego i podmienia cel tylko, gdy walidator
> zwróci 0 — zepsuty szablon nie dociera do dysku. `assemble` skleja katalog fragmentów w kolejności
> sortowania napisów (`5-` ląduje między `10-` a `50-`) i nie usuwa fragmentów-sierot.
>
> Czego nie zweryfikowano: kolizja domyślnego markera w dwóch rolach, `backup`/`create`,
> `validate` w `assemble`, `set_stats`, parametry roli/`include_role`, vault/galaxy/Molecule,
> SSH/`become`.

## Pliki

- [`edit_files.yml`](edit_files.yml) — `lineinfile` + `blockinfile` na `app.conf`.
- [`template_validate.yml`](template_validate.yml) + [`templates/settings.json.j2`](templates/settings.json.j2).
- [`assemble.yml`](assemble.yml) — fragmenty `conf.d` → `merged.conf`.
- [`cleanup.yml`](cleanup.yml) — usuwa `/tmp/ansible-demo-lvl17`.
- [`inventory.ini`](inventory.ini) — `localhost`, `ansible_connection=local`.

Wymagania: `ansible-core` (testowane 2.17.14), `python3`. Bez `sudo`.

## Uruchomienie

```bash
cd days/2026-10-10/ansible/code

ansible-playbook --syntax-check -i inventory.ini edit_files.yml
ansible-playbook --syntax-check -i inventory.ini template_validate.yml
ansible-playbook --syntax-check -i inventory.ini assemble.yml

# lineinfile / blockinfile (drugi przebieg: changed=0)
ansible-playbook -i inventory.ini edit_files.yml
ansible-playbook -i inventory.ini edit_files.yml
ansible-playbook -i inventory.ini edit_files.yml -e ssh_port=2200 -e naive=true --diff

# template + validate
ansible-playbook -i inventory.ini template_validate.yml
ansible-playbook -i inventory.ini template_validate.yml -e broken_json=true -e workers=16
ansible-playbook -i inventory.ini template_validate.yml -e workers=16 -e "validator='python3 -m json.tool'"

# assemble (drugi przebieg: changed=0)
ansible-playbook -i inventory.ini assemble.yml
ansible-playbook -i inventory.ini assemble.yml
ansible-playbook -i inventory.ini assemble.yml -e bad_name=true

# sprzatanie
ansible-playbook -i inventory.ini cleanup.yml
```

Jeśli `ansible-playbook` zgłasza `Ansible requires blocking IO on stdin/stdout/stderr`
(powłoka agentowa/CI), dopisz `2>&1 | cat`.

## Prawdziwy output (skrót)

```
edit_files.yml  run 1: ok=10 changed=8     run 2: ok=10 changed=0
   -Port 2222 / +Port 2200  (--diff, -e ssh_port=2200)
   +Banner /etc/issue.v1 / +Banner /etc/issue.v2  (-e naive=true, bez regexp)

template_validate.yml  (broken_json=true):
   FAILED! "msg": "failed to validate", "exit_status": 1,
   "stderr": "Invalid control character at: line 3 column 19 (char 37)"
   cel nadal: "workers": 4
   (validator bez %s): "validate must contain %s: python3 -m json.tool"

assemble.yml  run 1: changed=3   run 2: changed=0
   z -e bad_name=true: base=1 / early=1 / app=on / end=1
   kolejny przebieg bez bad_name: early=1 nadal w merged.conf, changed=0
```

## Uwagi

- Sprzątanie wykonane `cleanup.yml` (`changed=1`); `ls` po sprzątaniu odrzucone przez środowisko,
  więc zniknięcie katalogu potwierdza tylko raport modułu `file`.
- `port` i `break` są niedozwolonymi/zarezerwowanymi nazwami zmiennych — dlatego `ssh_port`,
  `broken_json`.
