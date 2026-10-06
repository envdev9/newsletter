# Kod do wydania #13 — własny inventory plugin + `any_errors_fatal` vs `max_fail_percentage`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> **Inventory plugin** `fleet_json` (Python w `inventory_plugins/`) buduje hosty, grupy i zmienne z
> `fleet.json`. Nie potrzebuje bitu `+x` (skrypt `dyn_inventory.py` bez `+x` dał
> `Permission denied`, a potem kaskadę fałszywych błędów z parsera `ini`) ani `ansible.cfg` —
> plugin `auto` czyta klucz `plugin:` z pliku `inventory.fleet.yml` i sam go ładuje.
> Zepsute `source:` albo zła nazwa pliku (`verify_file`) to tylko `[WARNING]` i
> `skipping: no hosts matched` — playbook „kończy się" na zero hostach.
>
> **`any_errors_fatal`** przerywa cały playbook po awarii (krok 2 i drugi play nie startują;
> hosty, które nie zawiniły, mają w recapie `failed=0`). **`max_fail_percentage`** przerywa dopiero,
> gdy odsetek porażek jest **większy** niż próg: 2 awarie z 6 hostów (33,3%) → `33` przerywa, `34`
> jedzie dalej; 1 awaria z 2 hostów (50%) → `50` jedzie dalej, `49` przerywa.
>
> Czego nie zweryfikowano: `dyn_inventory.py` przez `-i` (brak `+x`), efektu braku `_meta`,
> kodu wyjścia przy pustym inventory, `vars_prompt`, Molecule, SSH/`become`.

## Pliki

- [`inventory_plugins/fleet_json.py`](inventory_plugins/fleet_json.py) — inventory plugin.
- [`inventory.fleet.yml`](inventory.fleet.yml) — konfiguracja pluginu (to jest to, co dajesz do `-i`). Nazwa musi kończyć się `.fleet.yml` (`verify_file`).
- [`fleet.json`](fleet.json) — źródło danych: 6 hostów, `w2` i `k1` z `healthy: false`.
- [`dyn_inventory.py`](dyn_inventory.py) — wariant skryptowy (`--list`/`--host`). Wymaga `chmod +x`.
- [`bad_source.fleet.yml`](bad_source.fleet.yml), [`wrongname.yml`](wrongname.yml) — celowo zepsute inventory.
- [`inv_show.yml`](inv_show.yml) — pokazuje grupy i zmienne każdego hosta.
- [`fail_default.yml`](fail_default.yml), [`fail_any.yml`](fail_any.yml), [`fail_pct.yml`](fail_pct.yml) (`-e pct=NN`) — scenariusze awarii.

Wymagania: `ansible-core` (testowane 2.17.14, Python 3.10.4), bez `sudo`/`become`, wszystko
lokalnie (`ansible_connection=local`). Nic nie jest zapisywane poza katalogiem repo
(poza `inventory_plugins/__pycache__` tworzonym przez Pythona).

## Uruchomienie

```bash
cd days/2026-10-06/ansible/code

# 1. Inventory z pluginu
ansible-playbook -i inventory.fleet.yml inv_show.yml

# 2. Zepsute inventory: tylko WARNING + "skipping: no hosts matched"
ansible-playbook -i bad_source.fleet.yml inv_show.yml
ansible-playbook -i wrongname.yml inv_show.yml

# 3. Scenariusze awarii
ansible-playbook -i inventory.fleet.yml fail_default.yml
ansible-playbook -i inventory.fleet.yml fail_any.yml
ansible-playbook -i inventory.fleet.yml fail_pct.yml -e pct=33
ansible-playbook -i inventory.fleet.yml fail_pct.yml -e pct=34
ansible-playbook -i inventory.fleet.yml fail_pct.yml -e pct=50 -l w1,w2
ansible-playbook -i inventory.fleet.yml fail_pct.yml -e pct=49 -l w1,w2
ansible-playbook -i inventory.fleet.yml fail_pct.yml -e pct=0

# 4. (opcjonalnie) wariant skryptowy - po nadaniu bitu wykonywalnego
chmod +x dyn_inventory.py
ansible-playbook -i dyn_inventory.py inv_show.yml
```

Jeśli `ansible-playbook` zgłasza `Ansible requires blocking IO on stdin/stdout/stderr`
(powłoka agentowa/CI), dopisz `2>&1 | cat`.

## Prawdziwy output (skrót, pełny w [`../ARTICLE.md`](../ARTICLE.md))

`fail_any.yml` — po awarii `w2` i `k1` nic więcej się nie wykonuje, niewinne hosty mają `failed=0`:

```
fatal: [w2]: FAILED! => {"changed": false, "msg": "w2 niezdrowy"}
fatal: [k1]: FAILED! => {"changed": false, "msg": "k1 niezdrowy"}
w1 : ok=0 changed=0 unreachable=0 failed=0 skipped=1 rescued=0 ignored=0
w2 : ok=0 changed=0 unreachable=0 failed=1 skipped=0 rescued=0 ignored=0
```

`fail_pct.yml -e pct=33` (przerwanie) kontra `-e pct=34` (jedzie dalej na `w1`, `w3`, `w4`, `k2`):

```
NO MORE HOSTS LEFT *************************************************************
```

`fail_pct.yml -e pct=50 -l w1,w2` — jedna awaria z dwóch = 50%, nie jest "większe niż 50":

```
TASK [Krok 2 - wdrozenie] ******************************************************
ok: [w1] => {"msg": "wdrazam na w1"}
```

`dyn_inventory.py` bez `+x` (`-i` bezpośrednio):

```
[WARNING]:  * Failed to parse …/dyn_inventory.py with script plugin: problem running
…/dyn_inventory.py --list ([Errno 13] Permission denied: '…/dyn_inventory.py')
…
skipping: no hosts matched
```

## Uwagi

- Wszystkie powyższe uruchomienia wykonano raz (nie dwa razy jak w niektórych wcześniejszych
  wydaniach); wyniki są deterministyczne, kolejność hostów w logu może się różnić.
- Krok 4 (`chmod +x` + `-i dyn_inventory.py`) **nie został uruchomiony** — środowisko odrzuciło
  `chmod`. JSON ze skryptu sprawdzono tylko bezpośrednio (`python3 dyn_inventory.py --list`).
- Dziś odrzucone przez środowisko: `chmod`, `rm -r`, `rmdir`. `ansible-vault`/`ansible-galaxy`
  dziś nie próbowane (blokowane w #3–#12).
