# Kod do wydania #3 — vault, grupy, block/rescue/always, register, tags

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Trzy „hosty" (`web1`, `web2`, `db1`) to ta sama maszyna (`ansible_connection=local`),
> ale Ansible traktuje je jak trzy serwery w dwóch grupach. Wartości przychodzą z
> `group_vars` (`all` → grupa → `host_vars`, najbardziej szczegółowe wygrywa).
> Wdrożenie konfiguracji siedzi w `block`: gdy walidacja padnie, `rescue` przywraca
> ostatnią dobrą wersję, a `always` zapisuje status — host nie jest oznaczony jako
> `failed` (w recapie `rescued=1`). `register` + `failed_when`/`changed_when` uczą
> Ansible, co znaczy „błąd” i „zmiana” dla zwykłego polecenia (rc 3 = degraded to nie
> awaria; „nothing to do” to nie `changed`). `tags` pozwalają uruchomić wycinek
> playbooka. Sekrety mają trafić do `ansible-vault` — **uwaga: w środowisku, w którym
> powstało to wydanie, `ansible-vault` został odrzucony przez system uprawnień, więc
> szyfrowania nie uruchomiłem** (patrz niżej).

## Pliki

- [`inventory.ini`](inventory.ini) — grupy `web` (web1, web2), `db` (db1), `app:children`.
- [`group_vars/all/vars.yml`](group_vars/all/vars.yml), [`group_vars/web.yml`](group_vars/web.yml),
  [`group_vars/db.yml`](group_vars/db.yml), [`host_vars/web2.yml`](host_vars/web2.yml).
- [`group_vars/all/vault.yml`](group_vars/all/vault.yml) — fikcyjne sekrety; w repo **jawne** (patrz niżej).
- [`.vault_pass_demo`](.vault_pass_demo) — jawne, wyraźnie fikcyjne hasło DEMO do vaulta.
- [`site.yml`](site.yml), [`templates/app.conf.j2`](templates/app.conf.j2), [`files/*.sh`](files/).

Wymagania: `ansible-core` (testowane na 2.17.14, Python 3.10), bez `sudo`. Demo pisze
wyłącznie do `/tmp/ansible-demo-lvl3` (zmienna `out_dir`).

> Uwaga środowiskowa: w powłoce agenta Ansible odmawiał startu (`requires blocking IO`);
> pomogło `... 2>&1 | cat`. W zwykłym terminalu wystarczy sama komenda.

## Uruchomienie

Poniższe komendy wykonuj z katalogu `code/` (ścieżki względne), albo podaj ścieżki bezwzględne.

```bash
ansible-playbook -i inventory.ini site.yml --syntax-check
ansible-playbook -i inventory.ini site.yml --list-tags
# 1. pierwszy przebieg: dużo changed, migracja tylko na db1
ansible-playbook -i inventory.ini site.yml
# 2. drugi przebieg: changed=0 na wszystkich hostach
ansible-playbook -i inventory.ini site.yml
# 3. zły port -> validate pada -> rescue przywraca last-good (rescued=1)
ansible-playbook -i inventory.ini site.yml --tags config -e service_port=abc
# 4. powrót do dobrego stanu (deploy.status wraca do "ok")
ansible-playbook -i inventory.ini site.yml --tags config
# 5. podgląd zmian; sekrety (no_log) nie pokazują diffa
ansible-playbook -i inventory.ini site.yml --tags config --limit web1 -e env=prod --check --diff
ansible-playbook -i inventory.ini site.yml --tags secrets --limit web1 -e db_password=DEMO-rotated --check --diff
# 6. tagi: wszystko poza config i secrets, tylko grupa db
ansible-playbook -i inventory.ini site.yml --skip-tags config,secrets --limit db
# 7. failed_when: brak pliku -> rc 2 -> FAILED
ansible-playbook -i inventory.ini site.yml --tags check --limit web1 -e host_dir=/tmp/ansible-demo-lvl3/brak
```

## Vault (niezweryfikowane w wydaniu — do wykonania u siebie)

```bash
ansible-vault encrypt --vault-password-file .vault_pass_demo group_vars/all/vault.yml
ansible-vault view    --vault-password-file .vault_pass_demo group_vars/all/vault.yml
ansible-playbook -i inventory.ini site.yml --vault-password-file .vault_pass_demo
```

Bez `--vault-password-file` po zaszyfrowaniu playbook zgłosi błąd deszyfrowania.
Hasło w `.vault_pass_demo` jest **fikcyjne i jawne** (repo publiczne) — w prawdziwym
projekcie plik z hasłem trafia do `.gitignore` albo do menedżera sekretów.

## Sprzątanie

```bash
rm -rf /tmp/ansible-demo-lvl3
```

W `code/` nic się nie generuje.

## Czego nie zweryfikowano

- `ansible-vault` (encrypt / view / encrypt_string / błąd przy złym haśle) — polecenie odrzucone.
- `ansible-inventory --graph` — odrzucone.
- Zdalne SSH, `become`.
