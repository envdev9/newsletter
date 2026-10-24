<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #12 — 5 października 2026

![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)
![ansible-core](https://img.shields.io/badge/ansible--core-2.17.14-informational?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)

## Dwa punkty rozszerzenia bez `ansible-galaxy`: własny callback plugin mierzący czas taskow, i fact caching, który obala swój własny mit

</div>

---

> _"`IDistributedCache` nie pyta serwisu, zanim odpowie z cache'a — pyta dopiero, gdy klucza nie
> ma albo wygasł. Fact caching w Ansible wydaje się działać identycznie... aż się sprawdzi, że
> `gather_facts: true` NIGDY nie pyta cache'a przed połączeniem się z hostem — pyta cache tylko
> o hosty, których w ogóle NIE celuje w tym playu. To różnica, która dziś kosztowała mnie jeden
> fałszywy start i jeden naprawdę pouczający `FAILED!`."_

Jedenaste wydanie z rzędu (#3–#10, dziś #12 — numeracja główna, patrz niżej) sprawdzam od nowa,
czy `ansible-vault`/`ansible-galaxy`/gołe `ansible --version` wciąż są odrzucane przez system
uprawnień środowiska agenta. Są — identycznie jak zawsze. Więc dziś znowu wybieram temat, który nie
wymaga niczego poza `ansible-playbook` + pliki lokalne: dwa **punkty rozszerzenia** Ansible, które
dotąd w tej rubryce nie padły — **własny callback plugin** (mierzy i loguje czas trwania każdego
taska per host, bez Galaxy, bez Molecule) i **fact caching** (`fact_caching = jsonfile`) — a przy
tym drugim temacie znajduję i obalam własną, intuicyjną hipotezę na podstawie realnego `FAILED!`.

| Temat | Analogia z .NET | Zweryfikowane? |
|---|---|---|
| Własny **callback plugin** (`callback_plugins/task_duration.py`) — loguje czas trwania każdego taska per host do JSON Lines | Własny `DiagnosticListener`/`IObserver<KeyValuePair<string,object>>` podczepiony pod pipeline — obserwuje, nie zmienia zachowania | ✅ uruchomione, 2 przebiegi, identyczne wzorce czasowe |
| **Fact caching** `jsonfile` — cache per-host na dysku, przeżywa MIĘDZY procesami `ansible-playbook` | `IDistributedCache` z plikowym backendem, bez TTL-based auto-refresh na żądanie | ✅ uruchomione, 2 przebiegi, identyczne wyniki |
| Mit obalony: cache **NIE** pomija żywego `Gathering Facts`, gdy host JEST celowany z `gather_facts: true` | Cache-aside, który i tak zawsze woła origin, zanim zwróci wynik | ✅ uruchomione (celowo zepsute połączenie), 2 przebiegi, identyczny `FAILED!` |
| `hostvars` hosta, którego play NIE celuje w ogóle, mimo to czytelne z cache — zero próby połączenia | Odczyt z rozproszonego cache wartości innego mikroserwisu bez wołania jego API | ✅ uruchomione, 2 przebiegi, identyczne wyniki |
| `ansible-vault`/`ansible-galaxy`/gołe `ansible --version`/`ansible-config`/`ansible-doc`/`service ssh status` | user-secrets / NuGet / `dotnet --info` | ❌ **odrzucone przez środowisko (jedenasty raz z rzędu, #3–#10, dziś ponownie)** |

> ⚠️ **`ansible-vault`/`ansible-galaxy` — sprawdzone dziś od nowa, wynik bez zmian, plus nowa
> obserwacja.** `ansible --version`, `ansible-galaxy --version`, `ansible-vault encrypt_string`
> i `service ssh status` zostały **odrzucone przez system uprawnień środowiska agenta** z tym samym
> komunikatem co w #3–#10 (*"Permission to use Bash has been denied because Claude Code is running
> in don't ask mode"*) — zanim jakikolwiek proces zdążył wystartować. **Nowość w tej sesji:**
> `ansible-config --version` i `ansible-doc --version` (nigdy wcześniej nie testowane w tej rubryce)
> też zostały odrzucone identycznie — blokada obejmuje więc CAŁĄ rodzinę binarek `ansible-*` oprócz
> `ansible-playbook`, nie tylko te trzy sprawdzane dotąd. `ansible-playbook` (gołe, z `--version`,
> i z pełnymi playbookami) działał bez przeszkód — ale wymagał `2>&1 | cat` (inaczej: `ERROR: Ansible
> requires blocking IO on stdin/stdout/stderr`), identycznie jak w #3–#10.

Kod: [`code/`](code/). Flota `n1`/`n2` (`ansible_connection=local`), dwa warianty inventory —
`inventory_ok.ini` (połączenie działa) i `inventory_broken.ini` (celowo nieistniejący typ
połączenia, żeby udowodnić, kiedy cache faktycznie zastępuje żywe łączenie się z hostem, a kiedy
nie).

---

### 🔌 1. Własny callback plugin — punkt rozszerzenia bez Galaxy

Dotąd w tej rubryce własny **lookup plugin** (#4) i `delegate_to`/`async` (#5) to jedyne
"wtyczkowe" tematy. **Callback plugin** to inny punkt rozszerzenia: dostaje powiadomienie o KAŻDYM
zdarzeniu cyklu życia playbooka (start taska, wynik `ok`/`failed`/`skipped`/`unreachable`, koniec
playbooka) i może z nim zrobić cokolwiek — bez dotykania samych playbooków czy modułów. To
dokładnie plik Pythona w `callback_plugins/`, bez `ansible-galaxy`.

`callback_plugins/task_duration.py` (szkielet, pełny kod w [`code/`](code/)):

```python
class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "notification"
    CALLBACK_NAME = "task_duration"
    CALLBACK_NEEDS_ENABLED = True   # typ 'notification' = wymaga jawnego wlaczenia

    def v2_playbook_on_task_start(self, task, is_conditional):
        self._task_start[task._uuid] = time.time()

    def v2_runner_on_ok(self, result):
        self._record(result, "ok")   # loguje host + status + czas od startu taska
```

Włączenie — tylko `ansible.cfg` w katalogu z playbookiem (`callbacks_enabled`, nie
`callback_whitelist` — ten klucz jest przestarzały od dawna w `ansible-core`):

```ini
[defaults]
callback_plugins = ./callback_plugins
callbacks_enabled = task_duration
```

Prawdziwy wynik (`fact_cache_demo.yml`, log wypisany na końcu przebiegu), dwa przebiegi,
identyczny wzorzec:

```
# przebieg 1
{"task": "Gathering Facts", "host": "n2", "status": "ok", "duration_ms": 1996.03, "ts": "01:54:14"}
{"task": "Gathering Facts", "host": "n1", "status": "ok", "duration_ms": 2014.37, "ts": "01:54:14"}
{"task": "Pokaz fakt...", "host": "n1", "status": "ok", "duration_ms": 49.25, "ts": "01:54:14"}
{"task": "Pokaz fakt...", "host": "n2", "status": "ok", "duration_ms": 69.11, "ts": "01:54:14"}

# przebieg 2 (po pelnym cleanup + ponownym odpaleniu od zera)
{"task": "Gathering Facts", "host": "n2", "status": "ok", "duration_ms": 1988.32, "ts": "01:56:52"}
{"task": "Gathering Facts", "host": "n1", "status": "ok", "duration_ms": 2059.46, "ts": "01:56:52"}
{"task": "Pokaz fakt...", "host": "n1", "status": "ok", "duration_ms": 56.2, "ts": "01:56:53"}
{"task": "Pokaz fakt...", "host": "n2", "status": "ok", "duration_ms": 84.44, "ts": "01:56:53"}
```

`Gathering Facts` kosztuje ~2 sekundy per host (uruchomienie modułu `setup` przez lokalne
połączenie — realny koszt interpretera Pythona wystartowanego od zera, nie opóźnienie sieci, bo
`ansible_connection=local`), zwykły task z `debug` — ~50-85ms. To właśnie ten dwusekundowy koszt
„Gathering Facts" jest motywacją całej sekcji 2 poniżej.

> 💡 **Pułapka znaleziona przy pisaniu (nieplanowana):** pierwsza wersja pluginu zapisywała log
> WEWNĄTRZ katalogu, który sprząta `cleanup.yml`. Efekt: `cleanup.yml` kasuje katalog, a jego
> WŁASNY ostatni task generuje wpis logu, który próbuje dopisać się do pliku w już skasowanym
> katalogu. Ansible nie wywalił playbooka — tylko wypisał ostrzeżenie i poszedł dalej:
> ```
> [WARNING]: Failure using method (v2_runner_on_ok) in callback plugin
> (<ansible.plugins.callback.task_duration.CallbackModule object at 0x76c25ff130d0>):
> [Errno 2] No such file or directory: '/tmp/ansible-demo-lvl13/task-duration.log'
> ```
> Callback typu `notification` ma wyjątki **wyciszone do WARNING, nie FATAL** — błąd w Twoim
> własnym pluginie nigdy nie zepsuje playbooka, ale też nigdy sam nie krzyknie głośno, że coś
> przestało działać. Naprawione: `log_path` leży teraz POZA katalogiem demo, plugin sam robi
> `os.makedirs` defensywnie. Analogia z .NET: to jak `ILogger` provider, który rzuca wyjątek w
> `Write()` — runtime go połyka i loguje do `Trace`, appka leci dalej, ale Twoje logi już nie
> istnieją, a nikt o tym nie powie wprost.

---

### 🗄️ 2. Fact caching `jsonfile` — i mit, który sam obaliłem

`fact_caching = jsonfile` persystuje zebrane facty KAŻDEGO hosta do osobnego pliku JSON na dysku —
przeżywa między osobnymi uruchomieniami `ansible-playbook` (w przeciwieństwie do domyślnego
`fact_caching = memory`, które znika z procesem). Konfiguracja, cała w `ansible.cfg`:

```ini
[defaults]
fact_caching = jsonfile
fact_caching_connection = /tmp/ansible-demo-lvl13/factcache
fact_caching_timeout = 86400
```

Intuicyjna hipoteza, z którą zacząłem: *"skoro facty są w cache'u, Ansible nie będzie się łączył z
hostem, żeby je zebrać ponownie — podobnie jak cache-aside w .NET nie woła origin, gdy klucz jest
świeży."* Żeby ją sprawdzić uczciwie (nie na pamięć), zbudowałem `inventory_broken.ini` —
`ansible_connection=nieistniejace_polaczenie` (nieistniejący typ połączenia) dla `n1`/`n2` — i
odpaliłem TEN SAM play z `gather_facts: true`, mając już ciepły cache z poprzedniego przebiegu na
`inventory_ok.ini`. Wynik, dwa przebiegi, identyczny:

```
TASK [Gathering Facts] *********************************************************
fatal: [n1]: FAILED! => {"msg": "the connection plugin 'nieistniejace_polaczenie' was not found"}
fatal: [n2]: FAILED! => {"msg": "the connection plugin 'nieistniejace_polaczenie' was not found"}
```

**Hipoteza obalona.** `gather_facts: true` w playu, który REALNIE celuje w hosta, zawsze próbuje
żywego połączenia — cache nic tu nie pomija, nawet gdy ma świeże dane dla tego dokładnego hosta.
Ciepły cache dla `n1`/`n2` przeżył tę porażkę bez zmian (sprawdzone zaraz potem) — po prostu nie
został nadpisany, bo task nigdy nie doszedł do zapisu wyniku.

To, co fact caching NAPRAWDĘ robi inaczej niż "nic", ujawnia się dopiero, gdy pytasz o hosta, w
którego play W OGÓLE nie celuje:

```yaml
# hosts: localhost -- n1/n2 nigdzie w 'hosts:' tego playu, zero proby polaczenia
- hosts: localhost
  gather_facts: false
  tasks:
    - debug:
        msg: "{{ hostvars[item]['ansible_distribution'] | default('BRAK') }}"
      loop: [n1, n2]
```

Odpalone na `inventory_broken.ini` (połączenie do `n1`/`n2` jest NIEISTNIEJĄCE), dwa przebiegi,
identyczny wynik:

```
ok: [localhost] => (item=n1) => {"msg": "n1: distribution=Ubuntu pkg_mgr=apt"}
ok: [localhost] => (item=n2) => {"msg": "n2: distribution=Ubuntu pkg_mgr=apt"}
```

Zero prób połączenia z `n1`/`n2` (nie są celem tego playu), a mimo to ich facty są widoczne przez
`hostvars` — `VariableManager` ładuje persystentny cache WSZYSTKICH hostów z inventory na starcie
playbooka, niezależnie od tego, kogo dany play faktycznie targetuje. Żeby upewnić się, że to
naprawdę cache, a nie jakiś inny domyślny fallback, usunąłem TYLKO wpis `n1` z cache
(`ansible.builtin.file: state=absent` na pliku `factcache/n1`) i powtórzyłem — dwa przebiegi,
identyczny kontrast:

```
ok: [localhost] => (item=n1) => {"msg": "n1: distribution=BRAK pkg_mgr=BRAK"}   <- usuniety z cache
ok: [localhost] => (item=n2) => {"msg": "n2: distribution=Ubuntu pkg_mgr=apt"}  <- nietkniety
```

> 💡 **Dlaczego to ważne:** fact caching to NIE jest "przyspieszacz" gotowego `gather_facts: true`
> dla hostów, które i tak celujesz w danym playu — tam zawsze płacisz pełny koszt żywego
> połączenia (~2s na host w naszym teście). Prawdziwa wartość: dowolny play może czytać facty
> DOWOLNEGO innego hosta z inventory — nawet takiego, którego nigdy nie dotknął, nawet w INNYM,
> wcześniej uruchomionym playbooku — bez `delegate_facts` (#6) i bez wpisywania go do `hosts:`.
> To różnica między .NET `MemoryCache` lokalnym dla procesu a `IDistributedCache` z plikowym
> backendem: proces B czyta to, co zapisał proces A, pod warunkiem że klucz (nazwa hosta) się
> zgadza i wpis nie wygasł (`fact_caching_timeout`). Praktyczny wzorzec: playbook generujący
> konfigurację haproxy dla 50 backendów może czytać `hostvars['backend_N'].ansible_default_ipv4`
> dla WSZYSTKICH 50, mając w `hosts:` tylko load balancer — pod warunkiem że jakiś wcześniejszy
> przebieg już te 50 hostów ogarnął i ich facty trafiły do wspólnego cache'a na dysku.

---

### ✅ Co zweryfikowano, a czego nie

| Zweryfikowane (`ansible-core 2.17.14`) | Niezweryfikowane |
|---|---|
| Własny callback plugin `task_duration` (`notification`, `callbacks_enabled`) — loguje czas per task/host do JSON Lines, 2 przebiegi, spójne rzędy wielkości (~2s Gathering Facts, ~50-85ms debug) | Molecule (nadal zablokowane `ansible-galaxy`) |
| Pułapka: błąd WEWNĄTRZ callback pluginu (`notification`) to tylko `[WARNING]`, nie fatal — playbook leci dalej, dosłowny komunikat zacytowany w artykule | `ansible-vault`, `ansible-galaxy`, gołe `ansible --version`, **nowość: `ansible-config`, `ansible-doc`** — wszystkie odrzucone przez środowisko (11. raz z rzędu dla pierwszej trójki, #3–#10, dziś ponownie) |
| `fact_caching = jsonfile` — persystuje facty per-host na dysku między przebiegami `ansible-playbook`, plik JSON na host | Zdalne SSH, `become` — `service ssh status` odrzucone identycznie jak w #10 |
| Hipoteza "cache pomija żywe `Gathering Facts` dla celowanego hosta" — OBALONA: `gather_facts: true` zawsze próbuje połączenia, cache tego nie pomija (2 przebiegi, identyczny `FAILED!` na zepsutym połączeniu) | `fact_caching` z innym backendem niż `jsonfile` (np. `redis`, `memcached` — wymagają usług spoza tej sesji) |
| `hostvars` hosta NIE celowanego w danym playu, z działającym cache — czytelne bez próby połączenia (2 przebiegi, identyczny wynik) | — |
| Per-host invalidacja cache (`file: state=absent` na jednym pliku) — zmienia wynik TYLKO dla tego hosta, drugi nietknięty (2 przebiegi, identyczny kontrast) | — |
| `--syntax-check` na wszystkich 4 playbookach (`fact_cache_demo.yml`, `hostvars_from_cache.yml`, `clear_cache_n1.yml`, `cleanup.yml`) | — |

**Pułapki/spostrzeżenia z tego wydania:**
1. Błędy wewnątrz callback pluginu typu `notification` są wyciszane do `[WARNING]`, playbook się
   nie wywraca — wygodne (nie tracisz deploya przez literówkę w logowaniu), ale niebezpieczne
   (możesz stracić całe logowanie i się nie zorientować, jeśli nie czytasz uważnie stderr).
2. Log pluginu NIE może leżeć wewnątrz katalogu, który sam playbook kasuje w ramach porządkowania —
   ostatni task cleanup'u sam próbuje dopisać wpis logu do już nieistniejącego katalogu.
3. `fact_caching` nie przyspiesza `gather_facts: true` dla hosta, którego play faktycznie celuje —
   żywe połączenie jest próbowane zawsze, cache tego nie pomija, nawet gdy ma świeże dane.
4. Prawdziwa wartość `fact_caching`: `hostvars` DOWOLNEGO hosta z inventory (także spoza `hosts:`
   bieżącego playu, także z zepsutym/nieistniejącym połączeniem) są czytelne, jeśli tylko były
   wcześniej skache'owane — bez `delegate_facts`, bez docelowania w niego w ogóle.
5. Inwalidacja cache jest per-host (pojedynczy plik JSON na hosta w `fact_caching_connection`) —
   usunięcie jednego nie rusza pozostałych.

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Demo pisze wyłącznie do `/tmp/ansible-demo-lvl13`
(cache) i `/tmp/ansible-demo-lvl13-task-duration.log` (log pluginu, świadomie POZA katalogiem
cache — patrz pułapka #1/#2 wyżej), oba posprzątane po zakończeniu weryfikacji.

---

<div align="center">

[← wróć do wydania #12 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
