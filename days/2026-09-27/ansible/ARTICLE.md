<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #4 — 27 września 2026

![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)
![ansible-core](https://img.shields.io/badge/ansible--core-2.17.14-informational?style=for-the-badge)

## Własne filtry i lookupy, `include_tasks` kontra `import_tasks`, `serial` i `strategy` — czyli Ansible, który zaczyna być Twoim frameworkiem

</div>

---

> _"`import_tasks` to `#include` z czasów kompilacji, `include_tasks` to `Assembly.Load` w czasie
> działania. Obie linijki wyglądają prawie tak samo — i właśnie dlatego gryzą."_

W [#1](../../2026-09-24/ansible/ARTICLE.md) były taski, w [#2](../../2026-09-25/ansible/ARTICLE.md)
szablony i handlery, w [#3](../../2026-09-26/ansible/ARTICLE.md) grupy, `block/rescue` i tagi.
Dziś cztery rzeczy, które odróżniają „playbook” od „systemu, który da się utrzymać”:

| Temat | Analogia z .NET | Zweryfikowane? |
|---|---|---|
| własny filtr Jinja2 (`filter_plugins/`) | metoda rozszerzająca | ✅ uruchomione |
| własny lookup (`lookup_plugins/`) | `IConfigurationProvider` po stronie kontrolera | ✅ uruchomione |
| `import_tasks` vs `include_tasks` | `using static` vs ładowanie dynamiczne | ✅ uruchomione |
| `serial`, `max_fail_percentage`, `strategy` | rolling update / `Parallel.ForEach` bez bariery | ✅ uruchomione |
| `ansible-vault` (encrypt / view / encrypt_string) | user-secrets w pliku | ❌ **odrzucone przez środowisko** |
| `ansible-galaxy`, kolekcje, Molecule | NuGet / testy | ❌ nie próbowane |

> ⚠️ **Zastrzeżenie jak w poprzednim wydaniu.** Polecenie `ansible-vault` (encrypt) zostało
> odrzucone przez system uprawnień środowiska, w którym powstało to wydanie. Nie obchodziłem tego.
> Wszystko, co niżej wygląda jak wynik, to **prawdziwy output** (`ansible-core 2.17.14`,
> Python 3.10); vault opisuję na końcu wprost jako niezweryfikowany.
> `ansible-galaxy` i Molecule pominąłem — nie ma tu żadnych ich wyników.

Kod: [`code/`](code/). Cztery „serwery” `web1..web4` to ta sama maszyna (`ansible_connection=local`).

---

### 🧩 1. Własny filtr Jinja2

Filtry wbudowane (`combine`, `hash`…) znasz z #3. Gdy brakuje Ci swojego, wrzucasz plik Pythona do
`filter_plugins/` **obok playbooka** — Ansible sam go załaduje, żadnej rejestracji.

```python
def mask_secret(value, visible=2, mask="*"):
    if not isinstance(value, str):
        raise AnsibleFilterError("mask_secret oczekuje stringa, dostal: %s" % type(value).__name__)
    return value[:visible] + mask * max(len(value) - visible, 0)

class FilterModule(object):
    def filters(self):
        return {"mask_secret": mask_secret, "to_env_lines": to_env_lines}
```

Użycie: `{{ db_password | mask_secret(4) }}`. Prawdziwy wynik:

```
ok: [web1] => {
    "msg": "DEMO****************** / DE**************************"
}
ok: [web1] => {                       # {{ settings | to_env_lines('APP_') }}
    "msg": ["APP_DEBUG=False", "APP_NAME=sklep", "APP_PORT=8080"]
}
```

Zwróć uwagę na `APP_DEBUG=False` — wartość `false` z YAML-a to w Pythonie `bool`, a interpolacja
daje **`False`** z wielkiej litery, nie `false`. Dla aplikacji czytającej `.env` to różnica.
Jeśli ważna jest postać, dodaj w filtrze `str(value).lower()` dla boolów.

Błąd typu też sprawdziłem (`{{ 12345 | mask_secret }}`):

```
fatal: [web1]: FAILED! => {"msg": "mask_secret oczekuje stringa, dostal: int"}
```

> 💡 **Dlaczego to ważne:** logika „jak zmaskować/uformatować X” siedzi w jednym, testowalnym
> pliku Pythona, a nie w skopiowanych do dziesięciu szablonów wyrażeniach `regex_replace`.

---

### 🔎 2. Własny lookup

Lookup to wczytanie danych **na kontrolerze** (nie na hoście docelowym) w trakcie renderowania.
Napisałem `kv_file`: czyta plik `klucz=wartość` i zwraca wartości dla podanych kluczy.

```python
class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        self.set_options(var_options=variables, direct=kwargs)
        found = self.find_file_in_search_path(variables, "files", self.get_option("file"))
        ...
```

```yaml
msg: "{{ lookup('kv_file', 'version', 'channel', file='release.env', wantlist=True) }}"
```

```
ok: [web1] => { "msg": ["2.7.1", "stable"] }
```

Plik `app.env` zapisany przez `copy` z filtrów + lookupa; drugi przebieg z `--tags write` →
`changed=0` (idempotencja). Brak klucza kończy się błędem z moim komunikatem (owiniętym przez
Ansible w „unhandled exception occurred while running the lookup plugin”):

```
fatal: [web1]: FAILED! => {"msg": "An unhandled exception occurred while running the lookup plugin
'kv_file'. Error was a <class 'ansible.errors.AnsibleError'>, original message: kv_file: brak klucza
'nie_ma' w release.env. ..."}
```

> 💡 **Dlaczego to ważne:** lookup to miejsce na „pobierz z mojego systemu konfiguracji/rejestru”,
> zanim task w ogóle ruszy. Ale pamiętaj: wykonuje się lokalnie i przy **każdym** użyciu zmiennej,
> która go wywołuje — nie cache’uj w nim kosztownych zapytań bez zastanowienia.

---

### 📦 3. `import_tasks` vs `include_tasks` — najczęstsza pułapka

| | `import_tasks` | `include_tasks` |
|---|---|---|
| Kiedy przetwarzane | przy **parsowaniu** (statycznie) | w **trakcie wykonania** (dynamicznie) |
| `--list-tasks` | widzi zaimportowane taski | widzi tylko sam `include` |
| `tags` / `when` na dyrektywie | **dziedziczą wszystkie taski** z pliku | dotyczą **tylko** samego include |
| `loop` | ❌ zabronione | ✅ działa |
| Nazwa pliku z `{{ zmienną }}` | ❌ tylko stała | ✅ |

Wszystko poniżej to prawdziwe przebiegi `include_vs_import.yml`. Ten sam plik `tasks/step.yml`
(dwa taski; drugi ma własny tag `inner`) użyty dwoma sposobami.

**`--list-tasks`** — import rozwinięty, include nie:

```
      krok {{ step_name | default('bez-nazwy') }} - debug	TAGS: [imp]
      krok {{ step_name | default('bez-nazwy') }} - task z wlasnym tagiem inner	TAGS: [imp, inner]
      INCLUDE z tagiem i when	TAGS: [inc]
      INCLUDE w petli	TAGS: [loop]
      INCLUDE z apply	TAGS: [applied]
```

Import dostał tag `imp` w **każdym** tasku (i zachował `inner`). Nazwy w `--list-tasks` są
nieszablonowane, bo `step_name` nie jest jeszcze znane; przy wykonaniu jest `krok import - debug`.

**Tag `inc` na include** — uruchomił tylko sam include, wnętrze pliku nie:

```
$ ansible-playbook ... include_vs_import.yml --tags inc
TASK [INCLUDE z tagiem i when] ***
included: .../tasks/step.yml for web1
PLAY RECAP: web1 : ok=1 ...
```

**`--tags inner`** — złapał tylko task z pliku *zaimportowanego*; taski w plikach
załączonych (`include`) nie ruszyły, bo ich include nie miał tagu `inner`:

```
TASK [krok import - task z wlasnym tagiem inner] ***
ok: [web1] => { "msg": "task inner w kroku 'import'" }
PLAY RECAP: web1 : ok=1
```

**Naprawa: `apply`.** `include_tasks: {file: ..., apply: {tags: [applied]}}` + tag na include:
`--tags applied` uruchomiło include **i** oba taski z wnętrza (`ok=3`).

**`when`** — przy `-e do_import=false -e do_include=false --tags imp,inc` (obie flagi to
stringi z linii poleceń, stąd `| bool`, znane z #2): import daje **dwa** `skipping` (warunek
skopiowany do każdego taska), a include jeden (`skipped=3` w sumie):

```
TASK [krok import - debug] ***               skipping: [web1]
TASK [krok import - task z wlasnym tagiem inner] ***  skipping: [web1]
TASK [INCLUDE z tagiem i when] ***           skipping: [web1]
```

**`loop`** — `include_tasks` + `loop_control: {loop_var: step_name}` wykonał plik dla `alfa` i
`beta` (`included: ... (item=alfa)`). To samo z `import_tasks` kończy się **błędem parsowania**,
zanim cokolwiek ruszy:

```
ERROR! You cannot use loops on 'import_tasks' statements. You should use 'include_tasks' instead.
```

> 💡 **Dlaczego to ważne:** reguła kciuka — `import_tasks`, gdy struktura jest stała
> (widać ją w `--list-tasks`, tagi działają „jak trzeba”); `include_tasks`, gdy potrzebujesz pętli,
> nazwy pliku ze zmiennej albo warunku liczonego dopiero w trakcie. Nie mieszaj oczekiwań:
> `--tags` na include to najczęstsze „dlaczego mój task się nie wykonał”.

---

### 🚦 4. `serial` — wdrożenie porcjami

Bez `serial` Ansible rusza wszystkie hosty naraz (do `forks`, domyślnie 5). Z `serial` gra się
dzieli na **paczki**; następna paczka rusza dopiero po zakończeniu poprzedniej — to rolling update.

```yaml
- hosts: web
  serial: [1, 2]          # 1 host (canary), potem 2, potem po 2 do końca
  max_fail_percentage: 0  # jakikolwiek błąd zatrzymuje kolejne paczki
```

Prawdziwy przebieg dla 4 hostów: trzy osobne `PLAY [Rolling update]` z komunikatami
(`run_once` wypisał paczkę):

```
paczka ['web1'] (4 hostow razem)
paczka ['web2', 'web3'] (4 hostow razem)
paczka ['web4'] (4 hostow razem)
```

Teraz awaria na `web2` (`-e fail_host=web2`) — w paczce nr 2. Paczka nr 3 (`web4`) **w ogóle nie
ruszyła**:

```
fatal: [web2]: FAILED! => {... "failed_when_result": true, ...}
ok: [web3]
NO MORE HOSTS LEFT ***

PLAY RECAP
web1 : ok=3  failed=0
web2 : ok=1  failed=1
web3 : ok=1  failed=0
```

W recapie w ogóle **nie ma `web4`** — nie próbowano go. `web3` (ta sama paczka co `web2`)
zdążył wykonać task „Wdrożenie”, ale „Host zdrowy” już nie — gra przerwana.

> 💡 **Dlaczego to ważne:** canary + `max_fail_percentage` to różnica między „zepsułem jeden serwer”
> a „zepsułem całą flotę”. Uwaga: bez `max_fail_percentage` Ansible i tak pomija tylko failed host;
> dopiero próg (`0`) przerywa całą grę dla pozostałych paczek. Ja sprawdziłem wartość `0` —
> wartości pośrednich nie testowałem.

---

### 🏁 5. `strategy: linear` vs `free`

Domyślnie `linear`: task N kończy się na **wszystkich** hostach, zanim ruszy N+1 (bariera). `free`:
każdy host jedzie swoim tempem. Zrobiłem hosta `web1` wolnym (`sleep 3`); ten sam playbook,
`-e strat=free` zmienia strategię (parametr `strategy` przyjął szablon `{{ strat | default('linear') }}`).

`linear` — task 2 zaczyna się dopiero po skończeniu task 1 wszędzie:

```
TASK [Task 1] ***   ok: [web2] ok: [web3] ok: [web4] ok: [web1]
TASK [Task 2] ***   ok: [web1] ok: [web2] ok: [web3] ok: [web4]
```

`free` — szybkie hosty ukończyły task 2, zanim `web1` skończył task 1; nagłówki tasków
powtarzają się (kolejność zależy od tempa hostów):

```
TASK [Task 1] ***   ok: [web3]  ok: [web4]
TASK [Task 2] ***   ok: [web3] 
TASK [Task 1] ***   ok: [web2]
TASK [Task 2] ***   ok: [web4]  ok: [web2]
TASK [Task 1] ***   ok: [web1]
TASK [Task 2] ***   ok: [web1]
```

> 💡 **Dlaczego to ważne:** `free` skraca czas przy nierównych hostach, ale zabiera synchronizację —
> nie używaj go, gdy task N+1 zależy od stanu innych hostów po N (np. „najpierw wszystkie DB,
> potem aplikacje”). Pomiaru czasu nie robiłem — pokazuję tylko kolejność zdarzeń.

---

### 🔐 6. `ansible-vault` — niezweryfikowane (znowu)

Pierwsza próba `ansible-vault encrypt` na `group_vars/all/vault.yml` została **odrzucona przez
system uprawnień**. Nie próbowałem tego obchodzić (np. innym punktem wejścia). Dlatego:

- plik `group_vars/all/vault.yml` w repo jest **jawny** i zawiera fikcyjne wartości (`DEMO-…`);
- `.vault_pass_demo` zawiera fikcyjne hasło demo;
- **nie mam** prawdziwego outputu z `encrypt`, `view`, `encrypt_string` ani błędu złego hasła.

Polecenia do własnego sprawdzenia są w [`code/README.md`](code/README.md). Wzorzec z dokumentacji:
`vault_*` w zaszyfrowanym pliku, w `vars.yml` odwołanie `db_password: "{{ vault_db_password }}"`.
`ansible-galaxy` (kolekcje) i Molecule: **niesprawdzane** — przełożone na kolejne wydanie.

---

### ✅ Co zweryfikowano, a czego nie

| Zweryfikowane (`ansible-core 2.17.14`) | Niezweryfikowane |
|---|---|
| `filter_plugins/` (własne filtry + błąd typu) | `ansible-vault` (encrypt/view/encrypt_string) — odrzucone |
| `lookup_plugins/` (własny lookup, błąd braku klucza) | `--vault-password-file` w praktyce |
| `import_tasks`/`include_tasks`: `--list-tasks`, `--tags`, `when`, `loop`, `apply` | `ansible-galaxy`, kolekcje, Molecule |
| `serial: [1, 2]` + `max_fail_percentage: 0` z symulowaną awarią | `serial` z procentami, `throttle`, `run_once` w paczkach |
| `strategy` `linear` vs `free` (kolejność zdarzeń) | Zdalne SSH, `become`, pomiar czasu |
| `--syntax-check`, idempotencja zapisu `app.env` (`changed=0`) | Zawartość `app.env` (nie odczytałem pliku) |

**Pułapki na przyszłość:** `false` w YAML → `False` w Pythonie; tag na `include_tasks` nie schodzi
do środka (użyj `apply`); `import_tasks` + `loop` = błąd parsowania; komunikat `[WARNING]: Platform
linux ... discovered Python interpreter` wypisuje się przy każdym hoście — wycisza go
`ansible_python_interpreter=auto_silent` w inventory (tego nie testowałem).

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Demo pisze wyłącznie do `/tmp/ansible-demo-lvl4`.

---

<div align="center">

[← wróć do wydania #4 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
