<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #14 — 7 października 2026

![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)
![ansible-core](https://img.shields.io/badge/ansible--core-2.17.14-informational?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)

## Walidacja wejścia w playbooku: `vars_prompt`, `assert`, `fail` — i kod wyjścia, który zobaczyłem na własne oczy

</div>

---

> _"W ASP.NET Core nikt rozsądny nie przyjmuje `[FromQuery] int port` bez walidacji — a w
> playbooku `-e app_port=abc` przechodzi bez mrugnięcia okiem, bo to zawsze tylko string. Dziś
> dorabiamy Ansible-owi `[Range]` i `ModelState.IsValid`."_

Dziś ostatni punkt z listy „Następny poziom": **`vars_prompt` + `assert`/`fail` jako walidacja
wejścia**. Bonus: zamiast zgadywać, **zmierzyłem kod wyjścia** `ansible-playbook` przy awarii
(czego brakowało w #13) — przez playbook-runner, bo w powłoce agenta nie ma `$?`.

| Temat | Analogia z .NET | Zweryfikowane? |
|---|---|---|
| `vars_prompt` (pytanie, `default`, `private`) | `Console.ReadLine()` z wartością domyślną | ⚠️ tylko tryb nieinteraktywny (brak TTY) |
| `-e` przesłania pytanie | Argument CLI wygrywa z promptem | ✅ uruchomione |
| `assert` z `fail_msg` | `Debug.Assert` / FluentValidation | ✅ uruchomione |
| `fail` + `when` na regułę złożoną | Walidacja zależna od pola (`IValidatableObject`) | ✅ uruchomione |
| Kod wyjścia przy awarii: `rc: 2` | `Environment.ExitCode` | ✅ zmierzony |

Kod: [`code/`](code/). Dwa pliki: `validate.yml` (walidacja) i `exit_code.yml` (runner pokazujący `rc`).

---

### ❓ 1. `vars_prompt` — pytanie tylko wtedy, gdy nikt nie podał `-e`

```yaml
vars_prompt:
  - name: app_env
    prompt: "Srodowisko (dev/stage/prod)"
    default: "dev"
    private: false
  - name: deploy_token
    prompt: "Token wdrozeniowy (nie bedzie widoczny)"
    default: "demo-token-nie-prawdziwy"
    private: true        # bez echa, jak hasło
```

Dwie rzeczy, które **zmierzyłem**:

1. **Bez terminala (CI, pipe, agent) Ansible nie czeka, tylko bierze `default`** — z ostrzeżeniem:

```
[WARNING]: Not prompting as we are not in interactive mode
...
"msg": "Wdrazam dev na porcie 8080"
```

2. **`-e` wygrywa z pytaniem.** Gdy podałem wszystkie trzy zmienne (`-e app_env=qa -e app_port=80
   -e deploy_token=abc`), ostrzeżenia o promptowaniu **nie było** w ogóle — nie było o co pytać.
   Przy częściowym `-e` pytane są tylko brakujące zmienne.

> 💡 **Dlaczego to ważne:** ten sam playbook działa interaktywnie na laptopie i nieinteraktywnie
> w pipeline, **o ile każda zmienna ma sensowny `default`**. Pułapka odwrotna: `default` dla
> środowiska typu `prod` byłby groźny — domyślne wartości powinny być bezpieczne (`dev`).
> **Nie sprawdziłem** faktycznego wpisywania w terminalu (brak TTY w moim środowisku) — to wiedza
> z dokumentacji, nie z pomiaru.

---

### ✅ 2. `assert` i `fail` — dwa narzędzia do dwóch rodzajów reguł

`assert` = lista warunków „muszą być prawdziwe", z własnym `fail_msg`. `fail` + `when` = reguła
**złożona** lub zależna od innych pól, z dokładnym komunikatem.

```yaml
- ansible.builtin.assert:
    that:
      - app_env in ['dev', 'stage', 'prod']
      - app_port is match('^[0-9]+$')
      - (app_port | int) >= 1
      - (app_port | int) <= 65535
      - deploy_token | length >= 8
    fail_msg: "Niepoprawne wejscie: app_env={{ app_env }}, app_port={{ app_port }}, dlugosc tokenu={{ deploy_token | length }}"

- ansible.builtin.fail:
    msg: "prod musi dzialac na 443, a podano {{ app_port }}"
  when: app_env == 'prod' and (app_port | int) != 443
```

Wyniki (każdy zmierzony realnym `ansible-playbook`):

| Wejście | Wynik | `rc` |
|---|---|---|
| brak `-e` (nieinteraktywnie) | `Wdrazam dev na porcie 8080` | **0** |
| `app_env=prod app_port=443` | `Wdrazam prod na porcie 443` | **0** |
| `app_env=prod app_port=8080` | `fatal … "prod musi dzialac na 443, a podano 8080"` | **2** |
| `app_env=dev app_port=80` | `fatal … "dev wymaga portu >= 1024, a podano 80"` | **2** |
| `app_port=abc` | assert: `Niepoprawne wejscie: … app_port=abc …` | **2** |
| `app_env=qa app_port=80 deploy_token=abc` | assert, `"assertion": "app_env in ['dev', 'stage', 'prod']"` | **2** |

Fragment prawdziwego outputu dla ostatniego wiersza:

```
fatal: [localhost]: FAILED! => {
    "assertion": "app_env in ['dev', 'stage', 'prod']",
    "changed": false,
    "evaluated_to": false,
    "msg": "Niepoprawne wejscie: app_env=qa, app_port=80, dlugosc tokenu=3"
}
```

Trzy pułapki, które wyszły w praktyce:

- **`assert` raportuje tylko pierwszą nieprawdziwą regułę** (`"assertion"`). W tym przykładzie
  złe były trzy rzeczy (env, port 80 vs reguła, token 3 znaki), a w polu `assertion` widać jedną.
  Własny `fail_msg` z wartościami wszystkich pól ratuje sprawę — zobacz `dlugosc tokenu=3`.
- **Własny błąd logiki reguł.** Pierwsza wersja miała w `assert` `port >= 1024` (bo „porty
  uprzywilejowane są złe"), a regułę „prod = 443" obok. Efekt: `prod`+`443` **nie przechodziło
  nigdy** (`rc: 2`). Złapane dopiero uruchomieniem — reguły sprzeczne ze sobą nie wykryje
  `--syntax-check`. Poprawka: `assert` sprawdza tylko zakres 1–65535, a „≥ 1024 dla nie-prod"
  to osobny `fail` z `when`.
- **`vars_prompt` i `-e k=v` dają stringi** (`type_debug` → `AnsibleUnicode`/`str`), więc
  `| int` przed porównaniem jest obowiązkowe. `-e '{"app_port": 8080}'` (JSON) daje natomiast
  `int` i `is match` mimo to zadziałało — ale nie polegaj na tym, rzutuj jawnie.

> 💡 **Dlaczego to ważne:** błąd walidacji na **początku** playbooka kosztuje sekundę; ten sam
> błąd po `Gathering Facts`, instalacji i restarcie usługi — kwadrans i bałagan do sprzątania.
> `assert` na górze to `guard clause` playbooka. A `rc: 2` oznacza, że pipeline CI widzi porażkę
> bez parsowania tekstu.

---

### 🔢 3. Kod wyjścia — jak go zobaczyć bez `$?`

W poprzednim wydaniu zapisałem, że kodu wyjścia nie sprawdzę. Obejście: playbook-runner
`exit_code.yml` odpala `ansible-playbook` jako podproces (`command` + `register` +
`failed_when: false`) i wypisuje `child.rc`:

```
"args: …/validate.yml -e app_env=prod -e app_port=8080",
"rc: 2",
```

Zmierzone: sukces → `rc: 0`, awaria taska (`fail`/`assert`) → `rc: 2`. Inne kody (np. 4 dla
niedostępnych hostów, 1 dla błędu składni) znam z dokumentacji — **nie zmierzyłem ich dziś**.

---

### ✅ Co zweryfikowano, a czego nie

| Zweryfikowane (`ansible-core 2.17.14`) | Niezweryfikowane |
|---|---|
| `--syntax-check` obu playbooków | Prawdziwe wpisywanie w terminalu (`private: true` bez echa), `confirm`, `unsafe`, szyfrowanie hasha (`encrypt`) |
| Tryb nieinteraktywny → `default` + `[WARNING]` | Kody wyjścia inne niż 0 i 2 |
| `-e` pomija pytanie (brak ostrzeżenia przy komplecie) | `any_errors_fatal` + kod wyjścia (`rc` przy przerwaniu flotowym) |
| 6 scenariuszy wejścia, `rc` 0 i 2; domyślne wejście, `qa` i `prod`/443 uruchomione 2×, pozostałe 1× (prod/8080 i `abc` przed drobną edycją nazwy tasku i regułami portu — logika tych przypadków bez zmian) | Dynamic inventory przez `-i` (nadal bez `+x` → nie ruszane) |
| `assert` raportuje pierwszą regułę; typ `str` vs `int` | `ansible-vault`/`galaxy`/`ansible`, Molecule, SSH/`become` (blokady środowiska) |

**Pułapki z tego wydania:**
1. Bez TTY `vars_prompt` po cichu bierze `default` — tylko `[WARNING]`.
2. `assert` pokazuje pierwszą nieprawdziwą regułę; wartości dodaj do `fail_msg`.
3. Sprzeczne reguły przechodzą `--syntax-check` — wychodzą dopiero w uruchomieniu.
4. Wejście z `-e`/`vars_prompt` to stringi; rzutuj `| int`.

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Kod nic nie zapisuje na dysku.

---

<div align="center">

[← wróć do wydania #14 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
