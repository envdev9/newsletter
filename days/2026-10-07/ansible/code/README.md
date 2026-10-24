# Kod do wydania #14 — walidacja wejścia: `vars_prompt` + `assert`/`fail` + kod wyjścia

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> **`vars_prompt`** pyta o zmienne, których nie podano w `-e`. Bez terminala (CI, pipe) Ansible
> nie czeka — bierze `default` i wypisuje `[WARNING]: Not prompting as we are not in interactive
> mode`. Gdy podasz wszystkie zmienne przez `-e`, nie pyta o nic.
>
> **`assert`** sprawdza listę warunków i raportuje **pierwszy nieprawdziwy** (`"assertion"`), więc
> wartości wszystkich pól wstaw do `fail_msg`. **`fail` + `when`** obsługuje reguły złożone
> (`prod` wymaga portu 443; `dev`/`stage` portu >= 1024). Wejście z `-e k=v` i `vars_prompt` to
> stringi — rzutuj `| int`. Reguły sprzeczne ze sobą przechodzą `--syntax-check` i wychodzą
> dopiero w uruchomieniu.
>
> Kod wyjścia `ansible-playbook`: sukces `0`, awaria taska `2` (zmierzone runnerem `exit_code.yml`).
>
> Czego nie zweryfikowano: wpisywania w prawdziwym terminalu (`private`), kodów wyjścia innych niż
> 0 i 2, dynamic inventory przez `-i`, `ansible-vault`/`galaxy`, Molecule, SSH/`become`.

## Pliki

- [`validate.yml`](validate.yml) — play na `localhost` z `vars_prompt`, `assert` i dwoma `fail`.
- [`exit_code.yml`](exit_code.yml) — runner: odpala `ansible-playbook <child_args>` i pokazuje `rc`.

Wymagania: `ansible-core` (testowane 2.17.14). Bez `sudo`, nic nie jest zapisywane na dysku.

## Uruchomienie

```bash
cd days/2026-10-07/ansible/code

ansible-playbook --syntax-check validate.yml

# Interaktywnie w terminalu: zapyta o 3 wartości (Enter = default)
ansible-playbook validate.yml

# Nieinteraktywnie (default-y), z -e, scenariusze błędów
ansible-playbook validate.yml < /dev/null
ansible-playbook validate.yml -e app_env=prod -e app_port=443
ansible-playbook validate.yml -e app_env=prod -e app_port=8080
ansible-playbook validate.yml -e app_env=dev -e app_port=80
ansible-playbook validate.yml -e app_port=abc
ansible-playbook validate.yml -e app_env=qa -e app_port=80 -e deploy_token=abc

# Kod wyjścia przez runner (rc: 0 lub 2)
ansible-playbook exit_code.yml -e "child_args='validate.yml -e app_env=prod -e app_port=8080'"
```

Jeśli `ansible-playbook` zgłasza `Ansible requires blocking IO on stdin/stdout/stderr`
(powłoka agentowa/CI), dopisz `2>&1 | cat`. Runner uruchamia `ansible-playbook` w bieżącym
katalogu, więc ścieżkę do `validate.yml` podawaj względem miejsca, z którego startujesz (w
moim teście: ścieżki bezwzględne).

## Prawdziwy output (skrót)

```
fatal: [localhost]: FAILED! => {"changed": false, "msg": "prod musi dzialac na 443, a podano 8080"}
"rc: 2",
```

```
fatal: [localhost]: FAILED! => {
    "assertion": "app_env in ['dev', 'stage', 'prod']",
    "evaluated_to": false,
    "msg": "Niepoprawne wejscie: app_env=qa, app_port=80, dlugosc tokenu=3"
}
```

`prod`/443 → `"Wdrazam prod na porcie 443"`, `rc: 0`.

## Uwagi

- Pierwsza wersja `assert` zawierała `port >= 1024`, co przy regule „prod = 443" uniemożliwiało
  `prod` — wyłapane uruchomieniem, naprawione (zakres 1–65535 w `assert`, „>= 1024 dla nie-prod" w `fail`).
- Zadania: domyślne wejście, `qa` i `prod`/443 uruchomione dwukrotnie; pozostałe raz.
- Sprzątanie: nic nie powstało poza katalogiem wydania.
