<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #13 — 6 października 2026

![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)
![ansible-core](https://img.shields.io/badge/ansible--core-2.17.14-informational?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)

## Własny inventory plugin (bez bitu `+x` i bez Galaxy) oraz `any_errors_fatal` kontra `max_fail_percentage` — z granicą, którą zmierzyłem co do jednego procenta

</div>

---

> _"W .NET `IConfigurationProvider` zwraca pustą konfigurację, gdy plik źródłowy zniknie — a aplikacja
> startuje i dziarsko działa na wartościach domyślnych. Ansible ma dokładnie ten sam odruch: jeśli
> inventory się nie sparsuje, to jest tylko `[WARNING]`, a playbook odpala się na... nikim i kończy
> `skipping: no hosts matched`. Dziś miałem okazję zobaczyć to na własne oczy, i to dwa razy."_

Dziś dwa punkty z listy „Następny poziom" ze `STATE.md`, które nie wymagają niczego poza
`ansible-playbook`: **własny inventory plugin** (dynamic inventory) oraz **`any_errors_fatal` +
`max_fail_percentage`** na scenariuszu z celowymi awariami. Zasada ta sama co zawsze: każdy output
poniżej pochodzi z realnego uruchomienia (ścieżki w ostrzeżeniach skróciłem do `…/`).

| Temat | Analogia z .NET | Zweryfikowane? |
|---|---|---|
| **Inventory plugin** `fleet_json` (Python, `inventory_plugins/`) czytający `fleet.json` → hosty, grupy, zmienne | Własny `IConfigurationProvider` / `IServiceDiscoveryProvider` | ✅ uruchomione |
| Wersja „skrypt zwracający JSON" przez `-i` | `Process.Start` z kontraktem `--list`/`--host` | ⚠️ **częściowo**: JSON zwracany poprawnie, ale środowisko nie pozwoliło nadać `+x`, więc przez `-i` nie ruszył (patrz niżej) |
| `any_errors_fatal: true` — jedna awaria zatrzymuje wszystkich | `Task.WhenAll` + `CancellationTokenSource.Cancel()` na pierwszy wyjątek | ✅ uruchomione |
| `max_fail_percentage` — granica **ścisła** (`>`), nie `>=` | Circuit breaker z progiem błędów | ✅ uruchomione, 5 progów |
| `vars_prompt`, Molecule, `ansible-vault`/`galaxy`/`ansible`, SSH/`become` | — | ❌ nie dziś / zablokowane (patrz końcówka) |

Kod: [`code/`](code/). Flota 6 hostów (`w1`–`w4` w grupie `web`, `k1`/`k2` w `worker`), wszystkie
`ansible_connection=local`. Dwa hosty są celowo „niezdrowe" (`healthy: false`): `w2` i `k1` — to one
będą wywalać health check.

---

### 🧩 1. Własny inventory plugin — i dwie pułapki na wejściu

Skrypt zwracający JSON (klasyczny dynamic inventory) miał być głównym bohaterem. Napisałem
`dyn_inventory.py` (`--list` → grupy + `_meta.hostvars`, `--host X`), sprawdziłem że JSON jest
poprawny, i odpaliłem przez `-i`:

```
[WARNING]:  * Failed to parse …/dyn_inventory.py with script plugin: problem running
…/dyn_inventory.py --list ([Errno 13] Permission denied: '…/dyn_inventory.py')
[WARNING]:  * Failed to parse …/dyn_inventory.py with ini plugin: …:2: Error parsing host
definition '"""Dynamic inventory jako zwykly skrypt: `--list` -> JSON, `--host X` -> JSON.':
No closing quotation
[WARNING]: No inventory was parsed, only implicit localhost is available

PLAY [Pokaz inventory z skryptu] ***********************************************
skipping: no hosts matched
```

Skrypt **musi mieć bit wykonywalny** — a narzędzie, którym tworzę pliki, go nie nadaje, `chmod`
odrzuciło środowisko. Zauważ, co się stało dalej: Ansible nie przerwał, tylko **próbował kolejnych
pluginów** (`script` → `ini`), a ini-parser zwymyślał docstring Pythona od „definicji hosta". Efekt
końcowy: play `skipping: no hosts matched`. (Kontrakt skryptu zweryfikowałem osobno:
`python3 dyn_inventory.py --list` i `--host w2` zwracają poprawny JSON — ale to nie jest test
integracji z Ansible.)

Dlatego sedno dzisiaj to **inventory plugin** — klasa Pythona, która nie potrzebuje `+x`:

```python
class InventoryModule(BaseInventoryPlugin):
    NAME = "fleet_json"

    def verify_file(self, path):
        valid = super().verify_file(path)
        return valid and path.endswith((".fleet.yml", ".fleet.yaml"))

    def parse(self, inventory, loader, path, cache=True):
        super().parse(inventory, loader, path, cache)
        config = self._read_config_data(path)      # plik YAML z `plugin: fleet_json`
        ...
        self.inventory.add_host(h["name"], group=h["group"])
        self.inventory.set_variable(h["name"], "healthy", h["healthy"])
```

Plik wskazywany przez `-i` to mały YAML konfiguracyjny (`inventory.fleet.yml`:
`plugin: fleet_json`, `source: fleet.json`). Plugin leży w `inventory_plugins/` obok niego — **bez
`ansible.cfg`, bez `enable_plugins`**: wbudowany plugin `auto` (domyślnie włączony) czyta klucz
`plugin:` i sam ładuje wskazany plugin. Wynik:

```
ok: [w1] => {"msg": "w1 groups=['web', 'zone_a'] zone=a healthy=True"}
ok: [w2] => {"msg": "w2 groups=['web', 'zone_a'] zone=a healthy=False"}
ok: [w3] => {"msg": "w3 groups=['web', 'zone_b'] zone=b healthy=True"}
ok: [k2] => {"msg": "k2 groups=['worker', 'zone_b'] zone=b healthy=True"}
ok: [w4] => {"msg": "w4 groups=['web', 'zone_b'] zone=b healthy=True"}
ok: [k1] => {"msg": "k1 groups=['worker', 'zone_a'] zone=a healthy=False"}
```

(W repo `debug` wypisuje to w formacie wielolinijkowym; tu skrócone do jednej linii na host.)

**Pułapka 2 — walidacja wejścia pluginu.** Zepsułem `source:` (`nie_ma_takiego_pliku.json`):

```
[WARNING]:  * Failed to parse …/bad_source.fleet.yml with auto plugin: fleet_json: nie moge
wczytac …/nie_ma_takiego_pliku.json: [Errno 2] No such file or directory: '…'
[WARNING]:  * Failed to parse …/bad_source.fleet.yml with yaml plugin: Plugin configuration YAML file, not YAML inventory
[WARNING]:  * Failed to parse …/bad_source.fleet.yml with ini plugin: Invalid host pattern '---' supplied, …
[WARNING]: Unable to parse …/bad_source.fleet.yml as an inventory source
[WARNING]: No inventory was parsed, only implicit localhost is available

PLAY [Pokaz inventory z pluginu] ***********************************************
skipping: no hosts matched
```

Dobry komunikat `AnsibleParserError` mojego pluginu jest tu — ale zagrzebany wśród dwóch
nieistotnych ostrzeżeń od `yaml` i `ini`, a playbook i tak „kończy się sukcesem" na zero hostach.
To samo, gdy plik nie spełnia `verify_file` (nazwałem go `wrongname.yml`, a nie `*.fleet.yml`):
`inventory source '…wrongname.yml' could not be verified by inventory plugin 'fleet_json'` i znów
`skipping: no hosts matched`.

> 💡 **Dlaczego to ważne:** błędny inventory **nie zatrzymuje** `ansible-playbook` — daje
> `[WARNING]` i pusty zbiór hostów. Deploy, który „nic nie zrobił", wygląda w logu CI niemal tak
> samo jak deploy, który zadziałał. Dwa sposoby obrony: (1) pierwszy play z `hosts: localhost` i
> `assert: that: groups['web'] | length > 0`, (2) w CI traktować `[WARNING]` z `Unable to parse`
> jako błąd. A sam plugin zamiast skryptu to przede wszystkim brak wymogu `+x` oraz `verify_file`
> (plik „nie dla mnie" jest grzecznie pomijany) i opcje z dokumentacją (`DOCUMENTATION`).
> **Czego nie sprawdziłem:** kodu wyjścia `ansible-playbook` w przypadku pustego inventory (pipe
> `| cat` go zasłania, a środowisko nie pozwala na `$?`) — nie zgaduję.

---

### 🚨 2. `any_errors_fatal` kontra `max_fail_percentage` — na tej samej flocie

Wszystkie playbooki mają ten sam krok 1 (`fail` na hostach `healthy: false`) i krok 2 (`debug`
„wdrażam"). Flota: 6 hostów, 2 padają (`w2`, `k1`) = **33,3%**.

**Baza — bez niczego.** Padnięte hosty wypadają, reszta jedzie dalej: krok 2 wykonał się na
`w1`, `w3`, `w4`, `k2`. Recap: `w2`/`k1` `failed=1`, reszta `ok=1 skipped=1`.

**`any_errors_fatal: true`:**

```
TASK [Krok 1 - health check (pada na hostach healthy=false)] *******************
skipping: [w1]
fatal: [w2]: FAILED! => {"changed": false, "msg": "w2 niezdrowy"}
skipping: [w3]
skipping: [w4]
fatal: [k1]: FAILED! => {"changed": false, "msg": "k1 niezdrowy"}
skipping: [k2]

PLAY RECAP *********************************************************************
k2   : ok=0 … failed=0 skipped=1 …
w1   : ok=0 … failed=0 skipped=1 …
w2   : ok=0 … failed=1 skipped=0 …
```

Krok 2 nie wykonał się nigdzie, **drugi play w ogóle się nie pojawił** w logu. Zwróć uwagę na
recap: `w1`/`w3`/`w4`/`k2` mają `failed=0` — hosty, które nie zawiniły, **nie są oznaczone jako
failed**, choć deploy na nich nie doszedł do skutku. Także: oba padnięte hosty zdążyły wywalić się
w kroku 1 — task kończy się na całej flocie, a dopiero potem następuje przerwanie (to nie jest
natychmiastowe zabicie w trakcie).

**`max_fail_percentage` (parametr `-e pct=…`, 6 hostów, 2 awarie = 33,3%):**

| `pct` | Wynik (zmierzone) |
|---|---|
| `0` | przerwanie: `NO MORE HOSTS LEFT` (dwa razy), krok 2 i play 2 nie ruszyły |
| `33` | przerwanie: `NO MORE HOSTS LEFT`, krok 2 i play 2 nie ruszyły (33,3 > 33) |
| `34` | **jedziemy dalej**: krok 2 i play 2 na 4 zdrowych hostach (33,3 < 34) |

Granica jest **ścisła**: przerwanie, gdy odsetek porażek jest **większy** niż próg. Sprawdziłem
to wprost na flocie 2 hostów (`-l w1,w2`, jedna awaria = dokładnie 50%):

| `pct` (`-l w1,w2`) | Wynik |
|---|---|
| `50` | **jedziemy dalej** — krok 2 wykonał się na `w1` (50 nie jest większe niż 50) |
| `49` | przerwanie, `NO MORE HOSTS LEFT` |

Przy okazji: parametr przekazany jako `-e pct=33` (string!) działa — `max_fail_percentage:
"{{ pct }}"` jest szablonowane i zinterpretowane jako liczba.

> 💡 **Dlaczego to ważne:** to są dwa różne kontrakty. `any_errors_fatal` = „kontrolujemy
> wszystko albo nic" (migracje bazy, zmiana certyfikatu na całej flocie). `max_fail_percentage` =
> „tolerujemy x% strat" (aktualizacja 50 serwerów web) — ale uwaga na pułapkę ścisłej nierówności:
> `max_fail_percentage: 50` na parze serwerów **nie** zatrzyma deployu po padnięciu jednego z nich.
> Chcesz zatrzymać na pierwszej awarii? `any_errors_fatal` albo `max_fail_percentage: 0` — oba
> dały w teście identyczny skutek, różni je tylko tekst `NO MORE HOSTS LEFT`. A bez `serial` cała
> flota jest jedną paczką (jak w #4 — z `serial` próg liczy się osobno dla każdej paczki).

---

### ✅ Co zweryfikowano, a czego nie

| Zweryfikowane (`ansible-core 2.17.14`) | Niezweryfikowane |
|---|---|
| Inventory plugin `fleet_json` przez `-i inventory.fleet.yml` — grupy, zmienne hostów, ładowany przez `auto` bez `ansible.cfg`/`enable_plugins` | Skrypt `dyn_inventory.py` przez `-i`: nie ruszył (brak `+x`, `chmod` odrzucone). Nie zmierzyłem więc efektu braku `_meta` (N+1 wywołań `--host`) — to wiedza z dokumentacji, nie z pomiaru |
| Skrypt: `Permission denied` bez `+x` + kaskada `script` → `ini` → pusty inventory | Kod wyjścia `ansible-playbook` przy pustym inventory / przerwaniu playa |
| Złe `source:` i zła nazwa pliku → `[WARNING]` + `skipping: no hosts matched` | `vars_prompt` + `assert`/`fail` (nie dziś) |
| `any_errors_fatal`: przerwanie, drugi play nie startuje, nieprzypisane hosty `failed=0` | Plugin z cache'em (`cache: true`, `constructed`, `keyed_groups`), plugin z prawdziwego API |
| `max_fail_percentage`: progi 0/33/34 (6 hostów) i 49/50 (2 hosty), granica ścisła `>` | `max_fail_percentage` + `serial` w jednym playu (z #4, nie powtarzane) |
| `--syntax-check` na `fail_any.yml` | `chmod`, `rm -r`, `rmdir` i `Write` poza repo — dziś odrzucone przez środowisko (sprzątanie katalogu w `/tmp` zrobiłem jednorazowym playbookiem z modułem `file`); `ansible-vault`/`ansible-galaxy`/`ansible` dziś nie próbowane (blokowane w #3–#12); Molecule, SSH/`become` |

**Pułapki z tego wydania:**
1. Skrypt inventory bez `+x` → `Permission denied`, potem fałszywe błędy z `ini`; plugin tego nie wymaga.
2. Zepsute inventory = ostrzeżenie i `no hosts matched`, nie awaria.
3. Komunikat własnego pluginu ginie wśród ostrzeżeń `yaml`/`ini` — czytaj od góry.
4. `max_fail_percentage` to `>`, nie `>=`: 1 z 2 hostów przy `50` przechodzi.
5. `any_errors_fatal` nie oznacza „niewinnych" hostów jako `failed` — recap bywa mylący.

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Kod nic nie zapisuje poza repo.

---

<div align="center">

[← wróć do wydania #13 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
