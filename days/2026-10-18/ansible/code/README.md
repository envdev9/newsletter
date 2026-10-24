# Kod do wydania #25 — `include_role` + `apply:`, wyciek zmiennych roli, `set_stats` w wielu playach

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Tag na `include_role` dotyczy tylko zadania „dołącz": `--tags only_tag` dołącza rolę, ale nie
> wykonuje żadnego jej zadania. `apply: { tags: [...], environment: {...} }` przekazuje tag i
> środowisko do zadań wewnątrz roli (`--tags applied_tag` → `DEMO_ENV=ustawione-przez-apply`).
> `environment` bezpośrednio na `include_role` to błąd parsowania: `'environment' is not a valid
> attribute for a IncludeRole`. `lookup('env')` działa na kontrolerze i nie widzi `environment:`.
> Domyślnie `defaults/` i `vars/` roli są widoczne po jej wywołaniu (`roles:` i `include_role` z
> `public: true`). `set_stats` zbiera dane przez wiele playów: liczby z `aggregate: true` sumują się
> (3×2 + 3×3 = 15), napisy się sklejają, `aggregate: false` = ostatni zapis, `per_host: true` = klucz na host.
>
> Czego nie zweryfikowano: `private_role_vars` z włączoną flagą, `apply:` z `become`/`when`,
> `show_custom_stats`, SSH/`become`, vault/galaxy/Molecule.

## Pliki

- [`apply.yml`](apply.yml) — `include_role` z tagiem vs z `apply:`.
- [`env_on_include_broken.yml`](env_on_include_broken.yml) — CELOWO zepsuty (`environment` na `include_role`).
- [`private.yml`](private.yml) — wyciek `defaults`/`vars` po roli (`roles:` i `include_role public: true`).
- [`stats.yml`](stats.yml) + [`callback_plugins/dump_custom_stats.py`](callback_plugins/dump_custom_stats.py) — `set_stats` w 3 playach.
- [`roles/probe`](roles/probe) — rola testowa (`defaults`, `vars`, 2 zadania bez tagów).
- [`inventory.ini`](inventory.ini) — 3 hosty lokalne (`n1`–`n3`).

Wymagania: `ansible-core` (testowane 2.17.14), `python3`. Bez `sudo`, nic nie zapisuje poza `__pycache__`.

## Uruchomienie

```bash
cd days/2026-10-18/ansible/code

ansible-playbook --syntax-check -i inventory.ini apply.yml
ansible-playbook --syntax-check -i inventory.ini private.yml
ansible-playbook --syntax-check -i inventory.ini stats.yml
ansible-playbook --syntax-check -i inventory.ini env_on_include_broken.yml   # oczekiwany BŁĄD

# 1. include_role + apply
ansible-playbook -i inventory.ini apply.yml --tags only_tag      # ok=1, zadania roli pominięte
ansible-playbook -i inventory.ini apply.yml --tags applied_tag   # ok=3, DEMO_ENV=ustawione-przez-apply
ansible-playbook -i inventory.ini apply.yml                      # ok=6

# 2. wyciek zmiennych (stan bazowy)
ansible-playbook -i inventory.ini private.yml                    # obie zmienne widoczne

# 2b. NIEZWERYFIKOWANE przeze mnie - uruchom sam i porównaj z 2:
ANSIBLE_PRIVATE_ROLE_VARS=true ansible-playbook -i inventory.ini private.yml

# 3. set_stats
ansible-playbook -i inventory.ini stats.yml
```

Jeśli `ansible-playbook` zgłasza `Ansible requires blocking IO on stdin/stdout/stderr`
(powłoka agentowa/CI), dopisz `2>&1 | cat`.

## Prawdziwy output (skrót)

```
env_on_include_broken.yml --syntax-check:
  ERROR! 'environment' is not a valid attribute for a IncludeRole

apply.yml --tags only_tag     : "included: probe for localhost", ok=1 (zadań roli brak)
apply.yml --tags applied_tag  : ok=3, "rola probe wykonana, DEMO_ENV=ustawione-przez-apply"
apply.yml (bez tagów)         : ok=6, A -> DEMO_ENV=(brak), B -> DEMO_ENV=ustawione-przez-apply

private.yml (bez flagi), oba play'e:
  "probe_default": "z defaults roli", "probe_fixed": "z vars/ roli"     # wyciek

stats.yml (2 przebiegi, identyczne):
  CUSTOM_STATS[_run]: {"etap": "play1play1play1play2play2play2", "ostatni_etap": "play3-n3", "pliki": 15}
  CUSTOM_STATS[n1]: {"wersja": "v1"}   (analogicznie n2, n3)
```

## Uwagi

- Pierwsza wersja roli czytała `DEMO_ENV` przez `lookup('env')` i zawsze pokazywała `(brak)` —
  lookup działa na kontrolerze. Dlatego odczyt robi `shell` na hoście.
- `ostatni_etap` (`aggregate: false`) zależy od kolejności zakończenia hostów; `n3` w naszych przebiegach
  nie jest gwarancją.
- W `callback_plugins/` może zostać katalog `__pycache__` (wygenerowany przez Pythona) — można go usunąć.
