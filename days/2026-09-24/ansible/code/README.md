# Kod do wydania #1 — Pierwszy playbook, który naprawdę coś robi

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić
od zera + prawdziwy output z uruchomienia.

## Fragment prasówki, którego dotyczy ten kod

> Playbook tworzy katalog, zapisuje do niego plik z treścią zbudowaną ze zmiennej i
> wypisuje komunikat na konsoli. `ansible_connection=local` w inwentarzu oznacza, że
> Ansible uruchamia moduły bezpośrednio w tej samej powłoce — bez SSH, bez
> prawdziwego serwera. Uruchomiony dwa razy z rzędu bez zmian w plikach, drugi raz
> nic nie rusza (`changed=0`) — to jest idempotencja w praktyce.

## Pliki

- [`inventory`](inventory) — jeden host (`localhost`), połączenie lokalne.
- [`playbook.yml`](playbook.yml) — jeden play, trzy taski (`file`, `copy`, `debug`),
  sekcja `vars`.

## 0. Instalacja Ansible (jeśli go jeszcze nie masz)

W tym środowisku Ansible nie był zainstalowany. Zadziałało `pip` (bez `sudo`,
lokalnie dla użytkownika):

```bash
python3 -m pip install --user ansible-core
```

Po instalacji binarki lądują w `~/.local/bin` — upewnij się, że jest w `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
ansible-playbook --version
```

Wynik u nas:

```
ansible-playbook [core 2.17.14]
  config file = None
  configured module search path = ['/home/mag/.ansible/plugins/modules', '/usr/share/ansible/plugins/modules']
  ansible python module location = /home/mag/.local/lib/python3.10/site-packages/ansible
  ansible collection location = /home/mag/.ansible/collections:/usr/share/ansible/collections
  executable location = /home/mag/.local/bin/ansible-playbook
  python version = 3.10.4 (main, Apr  2 2022, 09:04:19) [GCC 11.2.0] (/usr/bin/python3)
  jinja version = 3.1.6
  libyaml = True
```

## 1. Sprawdzenie składni (bez uruchamiania)

```bash
cd days/2026-09-24/ansible/code
ansible-playbook -i inventory playbook.yml --syntax-check
```

Wynik:

```
playbook: playbook.yml
```

## 2. Pierwsze uruchomienie — playbook faktycznie coś tworzy

```bash
ansible-playbook -i inventory playbook.yml
```

Prawdziwy output (fragment `[WARNING]` o interpreterze Pythona to nieszkodliwy szum
środowiskowy, nie błąd):

```
PLAY [Pierwszy playbook - katalog roboczy i plik powitalny] ********************

TASK [Upewnij się, że katalog roboczy istnieje] ********************************
changed: [localhost]

TASK [Zapisz plik powitalny z treścią zbudowaną ze zmiennej] *******************
changed: [localhost]

TASK [Pokaż na konsoli, co właśnie zrobiliśmy] *********************************
ok: [localhost] => {
    "msg": "Zapisano 'Cześć, Świecie! Ten plik stworzył Ansible.' do /tmp/ansible-demo/powitanie.txt"
}

PLAY RECAP ***********************************************************************
localhost                  : ok=3    changed=2    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

Zawartość utworzonego pliku:

```bash
cat /tmp/ansible-demo/powitanie.txt
```

```
Cześć, Świecie! Ten plik stworzył Ansible.
```

## 3. Drugie uruchomienie — idempotencja (te same komendy, nic się nie zmienia)

```bash
ansible-playbook -i inventory playbook.yml
```

```
PLAY [Pierwszy playbook - katalog roboczy i plik powitalny] ********************

TASK [Upewnij się, że katalog roboczy istnieje] ********************************
ok: [localhost]

TASK [Zapisz plik powitalny z treścią zbudowaną ze zmiennej] *******************
ok: [localhost]

TASK [Pokaż na konsoli, co właśnie zrobiliśmy] *********************************
ok: [localhost] => {
    "msg": "Zapisano 'Cześć, Świecie! Ten plik stworzył Ansible.' do /tmp/ansible-demo/powitanie.txt"
}

PLAY RECAP ***********************************************************************
localhost                  : ok=3    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

Wszystko `ok`, `changed=0` — nic nie zostało ruszone, bo stan docelowy już był
osiągnięty.

## 4. Trzecie uruchomienie — zmienna z linii poleceń (`-e`)

```bash
ansible-playbook -i inventory playbook.yml -e "your_name=Mag"
```

```
PLAY [Pierwszy playbook - katalog roboczy i plik powitalny] ********************

TASK [Upewnij się, że katalog roboczy istnieje] ********************************
ok: [localhost]

TASK [Zapisz plik powitalny z treścią zbudowaną ze zmiennej] *******************
changed: [localhost]

TASK [Pokaż na konsoli, co właśnie zrobiliśmy] *********************************
ok: [localhost] => {
    "msg": "Zapisano 'Cześć, Mag! Ten plik stworzył Ansible.' do /tmp/ansible-demo/powitanie.txt"
}

PLAY RECAP ***********************************************************************
localhost                  : ok=3    changed=1    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

Katalog dalej `ok` (nie zmienił się), ale plik `changed` — bo treść faktycznie jest
inna niż poprzednio:

```bash
cat /tmp/ansible-demo/powitanie.txt
```

```
Cześć, Mag! Ten plik stworzył Ansible.
```

## Sprzątanie

```bash
rm -rf /tmp/ansible-demo
```

---

Wszystkie cztery kroki powyżej uruchomione naprawdę, lokalnie, na `ansible-core
2.17.14` (Python 3.10.4) przed publikacją tego wydania.
