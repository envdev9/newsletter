# Kod do wydania #6 — `delegate_facts`, `run_once` + `serial: 2`, `throttle: 2`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> `delegate_to` mówi WYKONAJ TU. `delegate_facts` mówi ZAPISZ TU. To dwie zupełnie różne
> decyzje i domyślnie Ansible podejmuje tylko pierwszą — wynik `set_fact` i tak wraca do hosta
> z pętli, nawet jeśli fizycznie policzony został gdzie indziej. `delegate_facts: true` naprawia
> to i dodatkowo sprawia, że fakt jest globalnie widoczny dla WSZYSTKICH kolejnych hostów
> przebiegu, nie tylko dla tego, który go ustawił.
>
> `run_once` w playu z `serial: N` wykonuje task **raz na każdą paczkę N hostów** (liczba
> wykonań = liczba_hostów / N), a nie raz na cały play — i robi to **pierwszy host danej
> paczki**. Bez `serial` (jedna paczka = cała grupa) `run_once` wykonuje się naprawdę raz.
>
> `throttle: N` ogranicza równoległość TYLKO jednego taska do N hostów naraz, niezależnie od
> `serial`/`forks` reszty play'a — przy 4 hostach i `throttle: 2` wychodzą dokładnie dwie fale
> po dwa hosty.
>
> Niezaplanowane odkrycie: nagłówek `TASK [...]` w logu, gdy `name:` zawiera
> `{{ inventory_hostname }}`, bywa wyrenderowany raz i "zamrożony" dla kolejnych hostów tego
> samego taska w ramach jednego przebiegu playbooka — samo wykonanie (`ok: [host] =>`, treść
> `msg`) pozostaje poprawne per host, myli tylko wyświetlany tekst nazwy.
>
> **Uwaga: `ansible-vault` i `ansible-galaxy` zostały w tym wydaniu ponownie odrzucone przez
> system uprawnień środowiska — nawet samo sprawdzenie wersji (`--version`), identycznie jak
> w wydaniach #3–#5.**

## Pliki

- [`inventory.ini`](inventory.ini) — grupa `app` (`app1..app4` — **czwarty host dołączył w tym
  wydaniu**, potrzebny do sensownego `serial: 2`/`throttle: 2`) i grupa `lb` (`lb1`), wszystkie
  `ansible_connection=local`.
- [`delegate_facts.yml`](delegate_facts.yml) — `set_fact` + `delegate_to: lb1` bez i z
  `delegate_facts: true`, z dowodem globalnej widoczności faktu dla kolejnych hostów (`serial: 1`).
- [`run_once_serial.yml`](run_once_serial.yml) — trzy playe: `run_once` + `serial: 2` (2 paczki
  z 4 hostów), `run_once` bez `serial` (cała grupa = jedna paczka), i podsumowanie odczytujące
  oba znaczniki.
- [`throttle2.yml`](throttle2.yml) — ten sam task uruchomiony dwa razy (bez `throttle` i z
  `throttle: 2`) na 4 hostach, ze znacznikami czasu w `/tmp/ansible-demo-lvl5/throttle2_log.txt`.

Wymagania: `ansible-core` (testowane 2.17.14, Python 3.10.4), bez `sudo`. Zapisy tylko do
`/tmp/ansible-demo-lvl5` (ten sam katalog co w #5 — świadoma kontynuacja tego samego scenariusza
rolling-deployowego, plik `lb_pool.txt` z #5 nie jest tu używany).

> Uwaga środowiskowa (jak w #3–#5): w powłoce agenta `ansible-playbook` wymagał
> `... 2>&1 | cat` (blocking IO). W zwykłym terminalu wystarczy sama komenda. Gołe
> `ansible --version`, `ansible-vault --version` i `ansible-galaxy --version` były odrzucane
> przez system uprawnień środowiska — działał tylko `ansible-playbook`.

## Uruchomienie

```bash
cd days/2026-09-29/ansible/code

# delegate_facts — gdzie ląduje set_fact + delegate_to, bez i z delegate_facts: true
ansible-playbook -i inventory.ini delegate_facts.yml --syntax-check
ansible-playbook -i inventory.ini delegate_facts.yml

# run_once + serial: 2 vs run_once bez serial
ansible-playbook -i inventory.ini run_once_serial.yml --syntax-check
ansible-playbook -i inventory.ini run_once_serial.yml

# throttle: 2 — dwie fale po dwa hosty na czterech dostępnych
ansible-playbook -i inventory.ini throttle2.yml --syntax-check
ansible-playbook -i inventory.ini throttle2.yml
```

Jeśli w Twoim terminalu `ansible-playbook` zgłasza `ERROR: Ansible requires blocking IO on
stdin/stdout/stderr` (typowe w niektórych środowiskach CI/agentowych, nie w zwykłym terminalu),
dopisz `2>&1 | cat` na końcu polecenia.

## Prawdziwy output (skrót, pełny w [`../ARTICLE.md`](../ARTICLE.md))

`delegate_facts.yml` (fragment dla `app1`, play ma `serial: 1`):

```
TASK [BEZ delegate_facts: set_fact leci na lb1, ale fakt ma wylądować tutaj]
ok: [app1 -> lb1]

TASK [Pokaz gdzie fakt NAPRAWDE wyladowal (bez delegate_facts)]
ok: [app1] => {
    "msg": "hostvars[app1].lb_seen_without_delegate_facts = ustawil app1 o 01:03:41 || hostvars['lb1'].lb_seen_without_delegate_facts = BRAK"
}

TASK [Z delegate_facts: set_fact leci na lb1 I fakt ma tam wylądować]
ok: [app1 -> lb1]

TASK [Pokaz gdzie fakt NAPRAWDE wyladowal (z delegate_facts)]
ok: [app1] => {
    "msg": "hostvars[app1].lb_seen_with_delegate_facts = BRAK || hostvars['lb1'].lb_seen_with_delegate_facts = ustawil app1 o 01:03:41"
}
```

`run_once_serial.yml` (podsumowanie na końcu):

```
"msg": [
    "=== serial: 2 (oczekiwane 2 linie, jedna na paczke) ===",
    [
        "run_once wykonany przez app1 o 01:04:10.945 | paczka widziana przez ten host (ansible_play_batch) = ['app1', 'app2']",
        "run_once wykonany przez app3 o 01:04:12.080 | paczka widziana przez ten host (ansible_play_batch) = ['app3', 'app4']"
    ],
    "=== bez serial (oczekiwana 1 linia, caly play to jedna paczka) ===",
    [
        "run_once wykonany przez app1 o 01:04:13.114 | ansible_play_batch = ['app1', 'app2', 'app3', 'app4']"
    ]
]
```

`throttle2.yml` (znaczniki czasu z logu):

```
start 01:04:21.350 app2        <- bez throttle: wszystkie 4 razem
start 01:04:21.361 app3
start 01:04:21.379 app1
start 01:04:21.382 app4
koniec 01:04:23.359 app2
koniec 01:04:23.365 app3
koniec 01:04:23.384 app1
koniec 01:04:23.388 app4
start 01:04:23.821 app1        <- throttle=2, fala 1: app1+app2 razem
start 01:04:23.873 app2
koniec 01:04:25.825 app1
koniec 01:04:25.879 app2
start 01:04:26.206 app3        <- throttle=2, fala 2: dopiero PO zakonczeniu fali 1
start 01:04:26.268 app4
koniec 01:04:28.211 app3
koniec 01:04:28.271 app4
```

## Czego NIE robić inaczej (wnioski z pułapek znalezionych przy pisaniu tego kodu)

1. Jeśli chcesz, żeby zapis `set_fact` po `delegate_to: X` trafił do hostvars `X`, a nie do
   hostvars bieżącego hosta z pętli — musisz dodać `delegate_facts: true`. Samo `delegate_to`
   przenosi tylko MIEJSCE WYKONANIA, nie miejsce zapisu faktu.
2. Nie polegaj na tekście w `name:` taska (np. `{{ inventory_hostname }}`) jako źródle prawdy w
   logach przy `serial`/pętlach po hostach — bywa wyrenderowany raz i "zamrożony". Do
   identyfikacji hosta używaj lewej strony (`ok: [host]`/`changed: [host]`) albo `debug: msg`.
3. `run_once` w playu z `serial: N` liczy się per paczka, nie per cały play (kontynuacja
   pułapki z #5, teraz sprawdzona precyzyjnie z `serial: 2`). Jeśli chcesz naprawdę "raz na cały
   play", usuń `serial` z tego konkretnego playa/taska (jak w osobnym playu w
   `run_once_serial.yml`).

## `ansible-vault` / `ansible-galaxy` (NIEZWERYFIKOWANE — odrzucone przez środowisko)

```bash
ansible --version               # <- odrzucone przez system uprawnień
ansible-vault --version         # <- odrzucone
ansible-galaxy --version        # <- odrzucone
```

`ansible-playbook` (użyte we wszystkich trzech playbookach powyżej) działa bez przeszkód.

## Sprzątanie

```bash
rm -rf /tmp/ansible-demo-lvl5
```

## Czego nie zweryfikowano

- `delegate_facts` z prawdziwym `gather_facts`/`setup` na zdalnym hoście (tu tylko `set_fact`).
- Zachowanie przy równoległym (nie `serial: 1`) zapisie tego samego faktu przez kilka hostów
  naraz (potencjalny wyścig przy `delegate_facts`).
- `run_once` + `serial` z nierówną listą, np. `serial: [1, 3]`.
- `throttle` połączony jednocześnie z `serial` (obie warstwy ograniczeń naraz).
- Czy "zamrożenie" nazwy taska z `{{ inventory_hostname }}` występuje też bez `serial` (jedna
  paczka, wiele hostów) — nietestowane osobno w tym wydaniu.
- `ansible-vault`, `ansible-galaxy` — oba odrzucone przez system uprawnień środowiska.
- Zdalne SSH, `become`.
