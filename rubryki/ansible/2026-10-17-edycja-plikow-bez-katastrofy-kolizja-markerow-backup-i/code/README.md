# Kod do wydania #24 — kolizja markerów `blockinfile`, `create`/`backup`, `validate`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> `blockinfile` rozpoznaje swój blok po markerze. Dwie role z domyślnym markerem piszące do jednego
> pliku nadpisują się nawzajem: w pliku zostaje jeden blok, a każdy przebieg daje `changed` (u nas
> `changed=3`, potem `2`). Marker z nazwą roli (`# {mark} team_a`) daje `changed=3`, potem `0`.
> `lineinfile` na brakującym pliku bez `create: true` kończy się błędem; `backup: true` robi kopię
> tylko przy realnej zmianie istniejącego pliku, a ścieżka jest w kluczu `backup` (nie `backup_file`).
> Kopie się kumulują. `validate` (`lineinfile`, `blockinfile`, `assemble`) uruchamia polecenie na
> pliku tymczasowym z CAŁĄ zawartością (z markerami i cudzymi liniami); przy `rc` ≠ 0 plik docelowy
> zostaje nietknięty.
>
> Czego nie zweryfikowano: `nginx -t`/`visudo -cf`, kolizji przy `serial`/wielu hostach, `backup`
> poza `lineinfile`, `validate` z `--check`, SSH/`become`, vault/galaxy/Molecule.

## Pliki

- [`collision.yml`](collision.yml) + [`roles/team_a`](roles/team_a), [`roles/team_b`](roles/team_b) — kolizja
  markerów; `-e fix_markers=true` włącza markery z nazwą roli.
- [`backup.yml`](backup.yml) — `create` i `backup` w `lineinfile` (5 kroków na jednym pliku).
- [`validate.yml`](validate.yml) + [`validate_conf.py`](validate_conf.py) — `validate` w `lineinfile`,
  `blockinfile`, `assemble`; walidator wymaga `klucz=wartość` i zapisuje zrzut tego, co dostał.
- [`cleanup.yml`](cleanup.yml) — usuwa `/tmp/ansible-demo-lvl24`.
- [`inventory.ini`](inventory.ini) — `localhost`, `ansible_connection=local`.

Wymagania: `ansible-core` (testowane 2.17.14), `python3`. Bez `sudo`.

## Uruchomienie

```bash
cd rubryki/ansible/2026-10-17-edycja-plikow-bez-katastrofy-kolizja-markerow-backup-i/code

ansible-playbook --syntax-check -i inventory.ini collision.yml
ansible-playbook --syntax-check -i inventory.ini backup.yml
ansible-playbook --syntax-check -i inventory.ini validate.yml

# 1. kolizja (dwa razy: changed=3, potem changed=2), potem sprzątanie i wersja naprawiona
ansible-playbook -i inventory.ini collision.yml
ansible-playbook -i inventory.ini collision.yml
ansible-playbook -i inventory.ini cleanup.yml
ansible-playbook -i inventory.ini collision.yml -e fix_markers=true   # changed=3
ansible-playbook -i inventory.ini collision.yml -e fix_markers=true   # changed=0

# 2. create/backup (zacznij od czystego katalogu; kolejne przebiegi dokładają kopie)
ansible-playbook -i inventory.ini cleanup.yml
ansible-playbook -i inventory.ini backup.yml

# 3. validate (drugi przebieg: changed=0, rescued=3 w obu)
ansible-playbook -i inventory.ini validate.yml
ansible-playbook -i inventory.ini validate.yml

# sprzątanie
ansible-playbook -i inventory.ini cleanup.yml
```

Jeśli `ansible-playbook` zgłasza `Ansible requires blocking IO on stdin/stdout/stderr`
(powłoka agentowa/CI), dopisz `2>&1 | cat`.

## Prawdziwy output (skrót)

```
collision.yml            run 1: ok=5 changed=3   run 2: ok=5 changed=2
  plik: # BEGIN ANSIBLE MANAGED BLOCK / flag_b=on / retries_b=5 / # END ANSIBLE MANAGED BLOCK
  (bloku team_a brak)
collision.yml -e fix_markers=true   run 1: changed=3   run 2: changed=0
  plik: # BEGIN team_a ... # END team_a  # BEGIN team_b ... # END team_b

backup.yml (czysty katalog)  ok=10 changed=4 rescued=1
  lineinfile bez create: Destination .../app.conf does not exist !  (rc 257)
  krok 2: changed=True  backup=          (plik dopiero powstał)
  krok 3: changed=True  backup=app.conf.<pid>.2026-10-17@00:41:49~
  krok 4: changed=False backup=
  krok 5: changed=True  backup=app.conf.<pid>.2026-10-17@00:41:50~
  'backup_file' in wynik: False;  kopia z kroku 3: ['port=8080']
  kolejny przebieg na tym samym katalogu: 4 kopie zamiast 2

validate.yml  run 1: ok=16 changed=5 rescued=3   run 2: ok=16 changed=0 rescued=3
  A2 failed to validate: rc:1 error:niepoprawny format key=value: linia 1: 'port 9091'  -> port=9090 bez zmian
  B2 failed to validate: rc:1 error:niepoprawny format key=value: linia 5: 'ttl: 120'   -> plik bez zmian
  walidator dostal: ['port=9090','mode=prod','# BEGIN ANSIBLE MANAGED BLOCK','cache=on','ttl=60','# END ANSIBLE MANAGED BLOCK']
  C2 failed to validate: ... linia 2: 'to nie jest key=value'  -> all.conf = ['a=1','b=2']
```

## Uwagi

- `backup.yml` celowo nie jest idempotentny (kroki zmieniają wartość tam i z powrotem) — demonstruje
  kiedy powstają kopie. Dla czytelnego wyniku zaczynaj od `cleanup.yml`.
- `validate_conf.py` zapisuje zrzut do `/tmp/ansible-demo-lvl24/validator_saw.txt` (zmienna
  `VALIDATOR_DUMP` zmienia ścieżkę); jest uruchamiany przez `python3`, nie wymaga bitu `+x`.
- PID w nazwie kopii zapasowej i znaczniki czasu różnią się między przebiegami.
