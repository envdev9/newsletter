<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #17 — 10 października 2026

![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)
![ansible-core](https://img.shields.io/badge/ansible--core-2.17.14-informational?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)

## Edytuj, nie nadpisuj: `lineinfile`, `blockinfile`, `template` z `validate` i `assemble`

</div>

---

> _"`template` mówi: ten plik ma wyglądać dokładnie tak. A co, gdy plik należy do kogoś innego —
> do pakietu, do admina, do innej roli — i chcesz zmienić w nim jedną linię? Dziś: cztery moduły
> do tej roboty i trzy pułapki, które zmierzyłem."_

Dotąd każdy plik w tej rubryce powstawał od zera (`copy`, `template`). Prawdziwe serwery mają
pliki, których nie wolno nadpisać w całości (`sshd_config`, `hosts`, config instalowany z
pakietu). Tu wchodzi edycja punktowa — i tu Ansible łatwo zepsuć idempotencję.

| Temat | Analogia z .NET | Zweryfikowane? |
|---|---|---|
| `lineinfile` z `regexp`, `insertafter`, `state: absent` | Zmiana jednego klucza w `appsettings.json` | ✅ 2 przebiegi, `changed=0` |
| `blockinfile` z własnym `marker` | Sekcja `#region` zarządzana przez narzędzie | ✅ 2 przebiegi, `changed=0` |
| `template` + `validate` | `dotnet build` przed wdrożeniem configu | ✅ dobry i zepsuty plik |
| `assemble` | Wiele plików `appsettings.*.json` → jeden | ✅ 3 przebiegi, `changed=0` |

Kod: [`code/`](code/). Wszystko pisze tylko do `/tmp/ansible-demo-lvl17`, sprzątanie to `cleanup.yml`.

---

### ✏️ 1. `lineinfile`: regexp to klucz idempotencji

Plik startowy (`copy` z `force: false`, więc tworzony tylko raz):

```
# app.conf - plik startowy
Port 22
LogLevel INFO
#PermitRootLogin yes
MaxSessions 10
```

Pięć zadań: `Port` (regexp `^#?Port\s`), `PermitRootLogin` (odkomentowanie + zmiana),
`ClientAliveInterval` z `insertafter: '^MaxSessions\s'`, usunięcie `LogLevel` (`state: absent`)
i dwa bloki (`blockinfile`, osobne `marker`). Wynik pierwszego przebiegu:

```
"# app.conf - plik startowy",
"Port 2222",
"PermitRootLogin no",
"MaxSessions 10",
"ClientAliveInterval 120",
"# BEGIN ANSIBLE: allow-users",
"AllowUsers deploy",
"AllowUsers ci",
"# END ANSIBLE: allow-users",
"# BEGIN ANSIBLE: limits",
"MaxAuthTries 3",
"LoginGraceTime 30",
"# END ANSIBLE: limits"
```

`changed=8`. Drugi przebieg: **`changed=0`**. Zmiana `-e ssh_port=2200` z `--diff` ruszyła
dokładnie jedną linię (`-Port 2222` / `+Port 2200`), reszta `ok`.

> 💡 **Dlaczego to ważne:** `regexp` odpowiada na pytanie „którą linię uważam za *moją*".
> Bez niego `lineinfile` porównuje całą linię `line:` i, gdy jej nie ma, **dopisuje nową**.

### 🪤 2. Pułapka: `lineinfile` bez `regexp` i zmieniająca się wartość

Zadanie bez `regexp`, uruchomione z `v1`, a potem `v2` (w teście w jednej pętli):

```
+Banner /etc/issue.v1
+Banner /etc/issue.v2
```

Oba wiersze zostały w pliku. Stara wartość nigdy nie znika sama — po kilku zmianach w
repozytorium masz na serwerze historię wszystkich. Przebieg też jest „idempotentny" (kolejny
daje `changed=0`), więc **żaden test idempotencji tego nie wyłapie** — widać to tylko w pliku.

### 🧱 3. `blockinfile`: marker to tożsamość bloku

Każdy blok dostał własny `marker: "# {mark} ANSIBLE: <nazwa>"`. `{mark}` zamieniane jest na
`BEGIN`/`END`; po tych markerach Ansible odnajduje blok przy kolejnym przebiegu. Dwa bloki z
różnymi markerami nie depczą sobie po palcach (oba przeżyły drugi przebieg bez zmian).

> 💡 **Dlaczego to ważne:** domyślny marker to `# {mark} ANSIBLE MANAGED BLOCK` — jeśli dwie role
> użyją domyślnego na tym samym pliku, drugą wersję bloku nadpiszesz pierwszą. Zawsze nadawaj
> własny marker. (Ten konkretny scenariusz opisuję z dokumentacji — nie uruchomiłem go.)

---

### 🛂 4. `template` + `validate`: zepsuty plik nie dociera do celu

`validate: "python3 -m json.tool %s"` — Ansible renderuje szablon do pliku tymczasowego, wywołuje
walidator (`%s` = ścieżka tego pliku) i dopiero przy kodzie 0 podmienia cel. Test: najpierw
poprawny JSON (`workers: 4`), potem `-e broken_json=true -e workers=16` (szablon gubi cudzysłów):

```
fatal: [localhost]: FAILED! => {"changed": false, ..., "exit_status": 1,
  "msg": "failed to validate", "stderr": "Invalid control character at: line 3 column 19 (char 37)\n", ...}
rescue: failed to validate / exit=1 / stderr=Invalid control character at: line 3 column 19 (char 37)
```

Cel po nieudanej walidacji nadal zawiera `"workers": 4` — **ani `16`, ani zepsuty JSON**. Zepsuty
przebieg powtórzony drugi raz: identyczny wynik. Poprawna zmiana (`workers=8`) przeszła normalnie
(`changed=1`); ponowny przebieg poprawnego pliku: `changed=0`.

Haczyk: `validate` **bez** `%s` nie jest „po cichu ignorowane", tylko od razu błąd:
`validate must contain %s: python3 -m json.tool`. Cel pozostał nietknięty.

> 💡 **Dlaczego to ważne:** w klasycznym ręcznym wdrożeniu `nginx -t` / `visudo -c` robisz
> przed przeładowaniem. `validate` robi to *przed podmianą pliku*, więc uszkodzony `sudoers`
> nigdy nie ląduje na dysku. To jedyne zabezpieczenie przed zablokowaniem sobie dostępu.
> (Z `sudoers`/`nginx` nie uruchamiałem — wymagają uprawnień/pakietów; mechanizm jest ten sam.)

### 🧩 5. `assemble`: conf.d w jednym pliku — i dwie pułapki

Trzy fragmenty (`10-base.conf`, `50-app.conf`, `90-end.conf`) → `merged.conf` z
`delimiter: "# ---"`:

```
base=1
# ---
app=on
# ---
end=1
```

Pierwszy przebieg: `changed`; drugi i trzeci: **`changed=0`**.

**Pułapka 1 — kolejność to sortowanie napisów.** Dodałem fragment `5-early.conf`
(`-e bad_name=true`). Wylądował **między `10-` a `50-`**, bo `"10"` < `"5-"` < `"50"`:

```
base=1 / early=1 / app=on / end=1
```

**Pułapka 2 — fragmenty nie znikają.** Po powrocie do przebiegu bez `bad_name` plik
`5-early.conf` nadal leżał w `conf.d`, a `merged.conf` go zawierał (`changed=0`). `assemble` składa
*to, co jest w katalogu* — usunięcie fragmentu z listy w playbooku go nie kasuje. Trzeba
`file: state: absent` albo kasowania całego katalogu przed złożeniem.

> 💡 **Dlaczego to ważne:** ten wzorzec pozwala wielu rolom dokładać swoje kawałki do jednego
> pliku bez wspólnego szablonu. Kosztem jest dyscyplina numerów (zawsze dwucyfrowe `NN-`) i
> sprzątanie po usuniętych fragmentach.

---

### ✅ Co zweryfikowano, a czego nie

| Zweryfikowane (`ansible-core 2.17.14`) | Niezweryfikowane |
|---|---|
| `--syntax-check` trzech playbooków | `blockinfile` z domyślnym markerem w dwóch rolach (kolizja) |
| `lineinfile`/`blockinfile`: 2 przebiegi, `changed=0`; `--diff` zmiany portu; pułapka bez `regexp` | `backup: true`, `create: true`, `validate` w `lineinfile`/`blockinfile` |
| `template` + `validate`: dobry, zepsuty (2×), bez `%s`; cel nietknięty | Czy `validate` odpala się, gdy treść nie zmieniła się (nie sprawdzałem) |
| `assemble`: 3 przebiegi (`changed=0`), sortowanie, fragment-sierota | `assemble` z `validate:`, `remote_src: false`, `ignore_hidden` |
| Sprzątanie `file: state: absent` (`changed=1`) | Własne walidatory typu `nginx -t`/`visudo -c`, SSH/`become`, vault/galaxy/Molecule (blokady środowiska), `set_stats`, parametry roli/`include_role` |

Dodatkowe haczyki, które wyszły przy okazji (prawdziwe komunikaty):
1. `port` jako nazwa zmiennej → `[WARNING]: Found variable using reserved name: port`.
2. `break` jako nazwa zmiennej → **błąd** `'break' is not a valid variable name` (syntax-check go łapie).
3. `lineinfile` bez `regexp` + zmienna wartość = śmieci w pliku, a `changed=0` mówi „wszystko OK".
4. `assemble` nie sprząta fragmentów i sortuje napisowo.

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Pliki testowe powstają w `/tmp/ansible-demo-lvl17`;
usuwa je `cleanup.yml`.

---

<div align="center">

[← wróć do wydania #17 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
