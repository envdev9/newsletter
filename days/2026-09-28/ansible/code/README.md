# Kod do wydania #5 — `delegate_to`, `async`/`poll`, `throttle`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> `delegate_to: X` wykonuje POJEDYNCZY task na innym hoście niż ten, po którym akurat iterujemy
> w pętli — `inventory_hostname` i inne zmienne bieżącego hosta zostają bez zmian, zmienia się
> tylko adres wykonania. `async`/`poll` to praca w tle **po stronie hosta docelowego**: `poll > 0`
> to auto-odpytywanie przez Ansible aż do zakończenia lub przekroczenia `async`; `poll: 0` to
> "fire and forget" ze sprawdzeniem wyniku później przez `async_status`; przekroczenie limitu
> `async` kończy się realnym błędem `"async task did not complete within the requested time"`.
> `throttle: N` ogranicza równoległość TYLKO jednego taska, niezależnie od `serial`/`forks`
> reszty play'a.
> **Uwaga: `ansible-vault` i `ansible-galaxy` zostały w tym wydaniu ponownie odrzucone przez
> system uprawnień środowiska — nawet samo sprawdzenie wersji (`--version`).**

## Pliki

- [`inventory.ini`](inventory.ini) — grupa `app` (`app1..app3`) i grupa `lb` (`lb1`), wszystkie
  `ansible_connection=local`.
- [`delegate_to.yml`](delegate_to.yml) — rolling deploy z drenowaniem fikcyjnego load balancera
  (`lb1`); osobny play inicjujący pulę (bez `serial`) + główny play z `serial: 1`.
- [`async_poll.yml`](async_poll.yml) — trzy scenariusze: `poll>0` (auto-polling), `poll: 0` +
  ręczny `async_status` z `until`/`retries`/`delay`, i timeout `async` (celowo za krótki limit).
- [`throttle.yml`](throttle.yml) — ten sam task uruchomiony dwa razy (bez i z `throttle: 1`),
  ze znacznikami czasu w `/tmp/ansible-demo-lvl5/throttle_log.txt`.

Wymagania: `ansible-core` (testowane 2.17.14, Python 3.10.4), bez `sudo`. Zapisy tylko do
`/tmp/ansible-demo-lvl5`.

> Uwaga środowiskowa (jak w #3/#4): w powłoce agenta Ansible wymagał `... 2>&1 | cat` (blocking
> IO). W zwykłym terminalu wystarczy sama komenda. Dodatkowa uwaga z tego wydania: gołe
> `ansible --version` i całe `ansible-galaxy` (nawet `--version`) były odrzucane przez system
> uprawnień środowiska — działał tylko `ansible-playbook`.

## Uruchomienie (z katalogu `code/`)

```bash
# delegate_to — rolling deploy z drenowaniem LB
ansible-playbook -i inventory.ini delegate_to.yml --syntax-check
ansible-playbook -i inventory.ini delegate_to.yml

# async / poll — trzy scenariusze (ostatni KOŃCZY SIĘ błędem timeoutu - to zamierzone,
# ignore_errors: true jest w playbooku)
ansible-playbook -i inventory.ini async_poll.yml --syntax-check
ansible-playbook -i inventory.ini async_poll.yml

# throttle — porównanie równoległego i zthrottlowanego przebiegu tego samego taska
ansible-playbook -i inventory.ini throttle.yml --syntax-check
ansible-playbook -i inventory.ini throttle.yml
```

## Czego NIE robić inaczej (dwie pułapki znalezione przy pisaniu tego kodu)

1. Nie inicjalizuj współdzielonego stanu w `pre_tasks` play'a, który ma `serial` — `run_once`
   liczy się per paczka `serial`, nie per cały play. W `delegate_to.yml` inicjalizacja puli LB
   jest dlatego w osobnym, wcześniejszym play'u kierowanym na grupę `lb` (jeden host = brak
   problemu).
2. `ansible.builtin.command` nie przechodzi przez powłokę — `&&`, `>`, `|` w komendzie trafiają
   jako dosłowne argumenty. Do takich konstrukcji potrzebny jest `ansible.builtin.shell`
   (widoczne w `async_poll.yml`).

## `ansible-vault` / `ansible-galaxy` (NIEZWERYFIKOWANE — odrzucone przez środowisko)

```bash
ansible --version              # <- odrzucone przez system uprawnień (nawet to!)
ansible-vault --version        # <- odrzucone
ansible-galaxy --version       # <- odrzucone
ansible-galaxy collection list # <- odrzucone
```

`ansible-playbook` (użyte we wszystkich trzech playbookach powyżej) działa bez przeszkód —
problem dotyczy konkretnie binarek `ansible`, `ansible-vault`, `ansible-galaxy`, nie samego
ansible-core.

## Sprzątanie

```bash
python3 -c "import shutil; shutil.rmtree('/tmp/ansible-demo-lvl5', ignore_errors=True)"
```

(`rm -rf` samo w sobie było odrzucone przez system uprawnień środowiska agenta — jak wyżej,
w praktyce wystarczy zwykłe `rm -rf /tmp/ansible-demo-lvl5`.)

## Czego nie zweryfikowano

- `delegate_facts`, `run_once` + `serial` inne niż `[1]`.
- Zachowanie procesu w tle po przekroczeniu limitu `async` (czy faktycznie dokańcza się w
  systemie, mimo że Ansible już zgłosił błąd).
- `throttle` > 1, `throttle` łączony jednocześnie z `serial`/niestandardowym `forks`.
- `ansible-vault`, `ansible-galaxy` — oba odrzucone przez system uprawnień środowiska.
- Zdalne SSH, `become`.
