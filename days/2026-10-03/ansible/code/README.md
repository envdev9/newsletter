# Kod do wydania #10 — `throttle` i `run_once` spotykają `serial` procentowy

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> `throttle` operuje na GOTOWYM rozmiarze paczki, bez względu na to, czy ten rozmiar powstał z
> liczby wpisanej wprost (`serial: 3`), czy z zaokrąglenia procentu (`serial: "40%"` → 3).
> Zaokrąglenie procentu (floor + min. 1, z #8) i liczenie fal `throttle` (`ceil`, z #7) to dwa
> **niezależne, sekwencyjne** kroki — nie wchodzą sobie w drogę, nie trzeba liczyć ich razem.
> Na 8 hostach `serial: "40%"` + `throttle: 2` na tym samym tasku daje paczki 3/3/2 (jak w #8)
> z falami `2+1`, `2+1`, `1` — identyczny wzorzec co na `serial` liczbowym w #7/#8.
>
> Pułapka `run_once` + `serial` z #5 (inicjalizacja odpala się raz NA PACZKĘ, nie raz na cały
> play) reprodukuje się identycznie na procentowo wyliczonych, nierównych paczkach (3, 3, 2) —
> nie jest to artefakt tylko równych, "ładnych" podziałów liczbowych. Umiejscowienie `run_once`
> w `pre_tasks` kontra zwykłych `tasks` **nie ma żadnego wpływu** na tę pułapkę — obie sekcje
> playu dzielą ten sam mechanizm batchowania `serial`. Jedyna skuteczna poprawka to osobny play
> **bez `serial`**. Przy nierównych paczkach `run_once` zawsze woła pierwszy host AKTUALNEJ
> paczki (`ansible_play_batch[0]`), nie pierwszy host całej inventory.
>
> **Uwaga: `ansible-vault`, `ansible-galaxy` i goła komenda `ansible --version` zostały w tym
> wydaniu ponownie odrzucone przez system uprawnień środowiska agenta — dziewiąty raz z rzędu
> (#3–#10). `ansible-playbook` działa bez przeszkód. Dodatkowo sprawdzono w tej sesji (nowość):
> nawet polecenia potrzebne tylko do SPRAWDZENIA dostępności `sshd` (`dpkg -l`, `service ssh
> status`) zostały odrzucone — stąd dzisiejszy temat nie obejmuje zdalnego SSH/`become`, bo nie
> dało się tego zweryfikować bez zgadywania.**

## Pliki

- [`inventory.ini`](inventory.ini) — jedna grupa, `flota` (`n1..n8`), wszystkie
  `ansible_connection=local`. Ta sama flota używana w obu playbookach, żeby podział na paczki
  3/3/2 (z `serial: "40%"`, 8 × 0,40 = 3,2 → floor → 3, reszta 2 w ostatniej paczce — patrz #8)
  był tym samym punktem odniesienia w obu eksperymentach.
- [`percent_throttle.yml`](percent_throttle.yml) — cztery playe: reset logu, `BASELINE`
  (`serial: "40%"` bez `throttle`, kontrola — powinna odtworzyć dokładnie wynik z #8), `COMBO`
  (`serial: "40%"` + `throttle: 2` NA TYM SAMYM tasku — główny temat), podsumowanie wypisujące
  cały log.
- [`percent_run_once.yml`](percent_run_once.yml) — pięć playów: reset logu, `PRE_TASKS_BUG`
  (`run_once` w `pre_tasks` playu z `serial: "40%"` — odtwarza pułapkę z #5 na procentach),
  `TASK_IN_SERIAL` (ten sam `run_once`, ale jako zwykły `task`, nie `pre_tasks`, w tym samym
  playu z `serial: "40%"` — pokazuje, że umiejscowienie nie ma znaczenia), `SEPARATE_FIX`
  (`run_once` w OSOBNYM playu BEZ `serial` — poprawka z #5), podsumowanie.

Wymagania: `ansible-core` (testowane 2.17.14, Python 3.10.4), bez `sudo`. Zapisy tylko do
`/tmp/ansible-demo-lvl9` (nowy katalog na to wydanie, posprzątany po weryfikacji — patrz sekcja
"Sprzątanie" niżej).

> Uwaga środowiskowa (jak w #3–#8): w powłoce agenta `ansible-playbook` wymagał `2>&1 | cat`
> (blocking IO) — w zwykłym terminalu wystarczy sama komenda. Gołe `ansible --version`,
> `ansible-vault` i `ansible-galaxy` były odrzucane przez system uprawnień środowiska agenta,
> niezależnie od blocking IO — działał tylko `ansible-playbook`.
>
> Nowa obserwacja środowiskowa z DZISIAJ: próby sprawdzenia dostępności `sshd`
> (`dpkg -l | grep openssh-server`, `ls /etc/ssh/`, `service ssh status`) zostały odrzucone przez
> system uprawnień środowiska agenta — nie tylko binarki `ansible`/`ansible-vault`/
> `ansible-galaxy` (jak w #3–#8), ale też ogólne narzędzia diagnostyczne niezwiązane z Ansible.
> Dlatego temat "zdalne SSH/`become`" z listy "następny poziom" w #8 został dziś świadomie
> pominięty — nie dało się zweryfikować nawet samej dostępności `sshd`, a pisanie o tym bez
> weryfikacji łamałoby zasadę zero fikcji tej rubryki.

## Uruchomienie

```bash
cd days/2026-10-03/ansible/code

# throttle: 2 na paczce wyliczonej z serial: "40%" (8 hostow -> paczki 3/3/2)
ansible-playbook -i inventory.ini percent_throttle.yml --syntax-check
ansible-playbook -i inventory.ini percent_throttle.yml

# run_once + serial: "40%" - pre_tasks vs zwykly task vs osobny play bez serial
ansible-playbook -i inventory.ini percent_run_once.yml --syntax-check
ansible-playbook -i inventory.ini percent_run_once.yml
```

Jeśli w Twoim terminalu `ansible-playbook` zgłasza `ERROR: Ansible requires blocking IO on
stdin/stdout/stderr` (typowe w niektórych środowiskach CI/agentowych, nie w zwykłym terminalu),
dopisz `2>&1 | cat` na końcu polecenia.

## Prawdziwy output (skrót, pełny w [`../ARTICLE.md`](../ARTICLE.md))

`percent_throttle.yml` (podsumowanie, przebieg 1 — identyczny podział na fale w przebiegu 2):

```
BASELINE start 01:03:38.458 n1 rozmiar_paczki=3 paczka=['n1', 'n2', 'n3']
BASELINE start 01:03:38.562 n2 rozmiar_paczki=3 paczka=['n1', 'n2', 'n3']
BASELINE start 01:03:38.577 n3 rozmiar_paczki=3 paczka=['n1', 'n2', 'n3']
... (paczka 2: 3 hosty naraz, paczka 3: 2 hosty naraz - bez throttle) ...

COMBO start 01:03:43.034 n1 rozmiar_paczki=3 paczka=['n1', 'n2', 'n3']
COMBO start 01:03:43.112 n2 rozmiar_paczki=3 paczka=['n1', 'n2', 'n3']
COMBO koniec 01:03:44.037 n1
COMBO koniec 01:03:44.115 n2
COMBO start 01:03:44.408 n3 rozmiar_paczki=3 paczka=['n1', 'n2', 'n3']   <- fala 2, tylko 1 host
COMBO koniec 01:03:45.411 n3
... (paczka 2: ten sam wzorzec 2+1) ...
COMBO start 01:03:48.588 n8 rozmiar_paczki=2 paczka=['n7', 'n8']         <- paczka 3: throttle=2=rozmiar, 1 fala
COMBO start 01:03:48.641 n7 rozmiar_paczki=2 paczka=['n7', 'n8']
```

`percent_run_once.yml` (podsumowanie, przebieg 1 — identyczny wzorzec w przebiegu 2):

```
PRE_TASKS_BUG run_once-init 01:03:56.468 wykonal=n1 rozmiar_paczki=3 paczka=['n1', 'n2', 'n3']
PRE_TASKS_BUG per-host     01:03:56.931 n2
PRE_TASKS_BUG per-host     01:03:57.084 n1
PRE_TASKS_BUG per-host     01:03:57.112 n3
PRE_TASKS_BUG run_once-init 01:03:57.482 wykonal=n4 rozmiar_paczki=3 paczka=['n4', 'n5', 'n6']  <- 2. wykonanie
PRE_TASKS_BUG per-host     01:03:57.921 n6
PRE_TASKS_BUG per-host     01:03:58.066 n4
PRE_TASKS_BUG per-host     01:03:58.107 n5
PRE_TASKS_BUG run_once-init 01:03:58.476 wykonal=n7 rozmiar_paczki=2 paczka=['n7', 'n8']          <- 3. wykonanie
PRE_TASKS_BUG per-host     01:03:58.870 n8
PRE_TASKS_BUG per-host     01:03:58.881 n7

TASK_IN_SERIAL run_once 01:03:59.256 wykonal=n1 rozmiar_paczki=3 paczka=['n1', 'n2', 'n3']
TASK_IN_SERIAL run_once 01:03:59.623 wykonal=n4 rozmiar_paczki=3 paczka=['n4', 'n5', 'n6']
TASK_IN_SERIAL run_once 01:03:59.988 wykonal=n7 rozmiar_paczki=2 paczka=['n7', 'n8']              <- tak samo 3x

SEPARATE_FIX run_once 01:04:00.337 wykonal=n1                                                     <- dokladnie 1x
```

## Czego NIE robić inaczej (wnioski z pułapek znalezionych przy pisaniu tego kodu)

1. Żeby porównać `throttle` na paczce liczbowej (#7/#8) i procentowej (dziś), użyj TEJ SAMEJ
   floty i tego samego procentu, który w #8 już dał znany podział na paczki (`"40%"` na 8
   hostach → 3/3/2) — inaczej porównujesz dwa różne eksperymenty, nie jedną zmienną na raz.
2. Do testu `run_once` + `serial` zawsze loguj `ansible_play_batch` razem z `inventory_hostname`
   wykonującego hosta — bez tego nie da się odróżnić "`run_once` wykonał się raz na paczkę" od
   "wykonał się raz dla całego playu, ale przypadkiem przez innego hosta niż oczekiwany".
3. Test trzech wariantów `run_once` (`pre_tasks`, zwykły `task`, osobny play bez `serial`) musi
   być w JEDNYM playbooku z WSPÓLNYM plikiem logu — inaczej trudno jednoznacznie porównać liczbę
   wykonań, bo każdy przebieg miałby własny, osobny log.
4. Przed wyborem tematu dnia sprawdź realnie, czy poprzednie ograniczenia środowiska
   (`ansible-galaxy`, `sshd`) się zmieniły — nie zakładaj z góry na podstawie poprzednich
   wydań. W tej sesji sprawdzono to na nowo i wynik się NIE zmienił (patrz niżej).

## `ansible-vault` / `ansible-galaxy` / `sshd` (NIEZWERYFIKOWANE — odrzucone przez środowisko)

```bash
ansible --version                                          # <- odrzucone przez system uprawnien
ansible-vault encrypt_string 'sekret' --name 'moj_sekret'  # <- odrzucone
ansible-galaxy --version                                   # <- odrzucone
dpkg -l | grep -i openssh-server                            # <- odrzucone (nowe dzisiaj)
service ssh status                                           # <- odrzucone (nowe dzisiaj)
```

Dokładny komunikat we wszystkich przypadkach: `Permission to use Bash has been denied because
Claude Code is running in don't ask mode` — to odmowa na poziomie narzędzia Bash tej sesji
agenta, nie błąd programu Ansible. `ansible-playbook` (użyte we obu playbookach powyżej) działa
bez przeszkód, także z `--version`:

```
ansible-playbook [core 2.17.14]
  config file = None
  configured module search path = ['/home/mag/.ansible/plugins/modules', '/usr/share/ansible/plugins/modules']
  ansible python module location = /home/mag/.local/lib/python3.10/site-packages/ansible
  ansible collection location = /home/mag/.ansible/collections:/usr/share/ansible/collections
```

## Sprzątanie

Wykonane już w trakcie pisania tego wydania (poniższa komenda służy do odtworzenia, gdybyś sam
odpalał kod lokalnie):

```bash
rm -rf /tmp/ansible-demo-lvl9
```

Jeśli w Twoim środowisku gołe `rm` na ścieżce w `/tmp` z jakiegoś powodu nie zadziała (jak w
sesji tego agenta w poprzednich wydaniach), zamiast tego użyj małego, jednorazowego playbooka z
modułem `file`:

```yaml
# cleanup.yml
- hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - ansible.builtin.file:
        path: /tmp/ansible-demo-lvl9
        state: absent
```

```bash
ansible-playbook cleanup.yml
```

## Czego nie zweryfikowano

- Molecule — nadal niemożliwe, bo `ansible-galaxy` (potrzebny do instalacji kolekcji/zależności)
  jest zablokowany przez środowisko (9. raz z rzędu, #3–#10).
- `ansible-vault`, `ansible-galaxy`, gołe `ansible --version` — odrzucone przez system uprawnień
  środowiska (9. raz z rzędu, #3–#10).
- Zdalne SSH, `become` — w tej sesji nie dało się nawet sprawdzić dostępności `sshd` (polecenia
  diagnostyczne odrzucone), więc temat świadomie pominięty zamiast zgadywany.
