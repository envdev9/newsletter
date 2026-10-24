# Kod do wydania #29 — handlery: kolejność, `listen`, awaria i `force_handlers`, łańcuchy

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Handlery wykonują się w kolejności **definicji** w `handlers:`, nie w kolejności `notify`; wielokrotny
> `notify` daje jedno wykonanie; topic `listen` uruchamia wszystkich słuchaczy; zadanie bez zmiany nie
> zgłasza. Gdy po zmianie konfiguracji padnie kolejny krok, zgłoszony handler domyślnie przepada (a
> następny przebieg zobaczy `ok` i nie zgłosi go ponownie). Obrona: `force_handlers: true` albo
> `meta: flush_handlers` zaraz po zmianie. Handler zgłoszony przez inny handler wykonuje się od razu
> po zgłaszającym, niezależnie od kolejności definicji (zmierzone, nie z dokumentacji).
>
> Czego nie zweryfikowano: `force_handlers` przy `unreachable`/`serial`/`any_errors_fatal`, handlery w
> rolach, `notify` w `block`/`rescue`, SSH/`become`, vault/galaxy/Molecule.

## Pliki

- [`order_listen.yml`](order_listen.yml) — kolejność, deduplikacja, `listen`.
- [`failure.yml`](failure.yml) — awaria po zmianie; `-e force=true`, `-e flush=true`.
- [`chain.yml`](chain.yml) — handler zgłaszający handler.
- [`inventory.ini`](inventory.ini) — `localhost` z `ansible_connection=local`.

Wymagania: `ansible-core` (testowane 2.17.14). Bez `sudo`, nic nie zapisuje na dysk.

## Uruchomienie

```bash
cd days/2026-10-24/ansible/code

ansible-playbook --syntax-check -i inventory.ini order_listen.yml
ansible-playbook --syntax-check -i inventory.ini failure.yml
ansible-playbook --syntax-check -i inventory.ini chain.yml

ansible-playbook -i inventory.ini order_listen.yml            # handlery: X, Y, Z, X2
ansible-playbook -i inventory.ini failure.yml                 # brak handlera
ansible-playbook -i inventory.ini failure.yml -e force=true   # handler po awarii
ansible-playbook -i inventory.ini failure.yml -e flush=true   # handler przed awarią
ansible-playbook -i inventory.ini chain.yml                   # A, B, C, D
```

`failure.yml` kończy się błędem celowo (kodu wyjścia dziś nie mierzyłem). Jeśli `ansible-playbook` zgłasza
`Ansible requires blocking IO on stdin/stdout/stderr` (powłoka agentowa/CI), dopisz `2>&1 | cat`.

## Prawdziwy output (skrót)

```
order_listen.yml : RUNNING HANDLER X, Y, Z, X2 ; ok=9 changed=4 ; "handler NIGDY" nie ruszył
failure.yml      : ok=1 changed=1 failed=1 (bez handlera)
failure.yml force: RUNNING HANDLER [restart uslugi] po fatal ; ok=2 changed=1 failed=1
failure.yml flush: RUNNING HANDLER [restart uslugi] przed fatal ; ok=2 changed=1 failed=1
chain.yml        : RUNNING HANDLER A, B, C, D ; ok=5 changed=3 (2 przebiegi, ta sama kolejność)
```

## Uwagi

- W nazwach zadań/handlerów nie używaj `: ` bez cudzysłowu — YAML czyta to jako mapę (pierwsza wersja
  `order_listen.yml` padła na tym przy parsowaniu).
- `changed_when: true` na `debug` jest tylko po to, by zasymulować zmianę; prawdziwe moduły robią to same.
