<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #18 — 11 października 2026

![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)
![ansible-core](https://img.shields.io/badge/ansible--core-2.17.14-informational?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)

## Rola jak metoda: parametry, `argument_specs`, `include_role`, `block` vars i `set_stats`

</div>

---

> _"Rola w Ansible to metoda bez sygnatury: wołasz ją z jakimiś zmiennymi i masz nadzieję, że
> dobrze. Dziś: jak nadać jej sygnaturę, co faktycznie 'wycieka' do playbooka po jej wywołaniu
> i dlaczego Ansible potrafi po cichu przepuścić rolę dwa razy albo ani razu."_

Do tej pory role były dla nas katalogiem z taskami. Teraz traktujemy je jak **publiczne API**:
parametry, walidacja, zakres widoczności. Dla .NET dewelopera najbliższa analogia to klasa z
konstruktorem i `required init` — tyle że domyślnie Ansible niczego nie sprawdza.

| Temat | Analogia z .NET | Zweryfikowane? |
|---|---|---|
| Parametry roli + deduplikacja (`allow_duplicates`) | Singleton vs transient w DI | ✅ realny przebieg + 2. przebieg `changed=0` |
| `include_role` w pętli, `tasks_from` | Wywołanie metody w `foreach`, inna metoda tej samej klasy | ✅ |
| `meta/argument_specs.yml` | `required`, typy, `enum` w modelu | ✅ 5 przypadków |
| Wyciek zmiennych: `roles:` / `include_role` / `public` / `import_role` | Zakres `public` vs `private` | ✅ 4 warianty |
| `vars:` na `block` | Zmienna w zakresie `{ }` | ✅ |
| `set_stats` | Metryka całego przebiegu (nie hosta) | ✅ (własny callback do wypisania) |

Kod: [`code/`](code/). Wszystko pisze tylko do `/tmp/ansible-demo-lvl18`, sprzątanie: `cleanup.yml`.

---

### 🔁 1. Ta sama rola dwa razy: kiedy Ansible ją pominie

Rola `svc_note` (jeden task `debug`) wywołana pięć razy w `roles:`: parametry `one`, `two`, `one`;
potem rola `svc_unit_dup` (z `allow_duplicates: true`) dwa razy z identycznym `tag: same`.
Faktycznie wykonały się **cztery** wywołania:

```
svc_note wykonana (parametr tag=one)
svc_note wykonana (parametr tag=two)
svc_unit_dup wykonana (parametr tag=same)
svc_unit_dup wykonana (parametr tag=same)
```

Trzecie wywołanie `svc_note` z `tag: one` — **pominięte bez ostrzeżenia**, bo jest identyczne z
pierwszym. Zasada: rola z `roles:` wykonuje się raz dla danej kombinacji nazwa + parametry, chyba że
w `meta/main.yml` roli jest `allow_duplicates: true`.

> 💡 **Dlaczego to ważne:** jeśli parametr „zależy od środowiska" i dwa razy wyliczy się do tej
> samej wartości, druga instancja zniknie. Dla roli „utwórz użytkownika X" to dobrze (idempotencja),
> dla roli „dopisz wpis do dziennika" — cicha utrata zdarzenia.

### 🔄 2. `include_role` w pętli: tu nic nie jest deduplikowane

Ta sama rola `svc_unit`, ale `include_role` + `loop` z trzema elementami (`alpha`, `beta`, `alpha`):

```
included: svc_unit for localhost => (item=alpha)
included: svc_unit for localhost => (item=beta)
included: svc_unit for localhost => (item=alpha)
...
"msg": "alpha: port=9001 env=dev replicas=1 changed=True"
"msg": "beta: port=9002 env=stage replicas=3 changed=True"
"msg": "alpha: port=9001 env=dev replicas=1 changed=False"
```

Trzeci przebieg (duplikat `alpha`) **wykonał się** — i zgłosił `changed=False`, bo plik już istniał.
To jest właśnie idempotencja zamiast deduplikacji. `roles:` to lista statyczna; `include_role` to
**zwykły task**, który można zapętlić, obwarować `when`, i który zawsze się wykona.

Bonus: `include_role` z `tasks_from: health` uruchamia inny punkt wejścia roli
(`tasks/health.yml`) — rola może mieć kilka „metod publicznych".

Drugi przebieg całego playbooka: `changed=0` (22 zadania).

### 🛡️ 3. `meta/argument_specs.yml`: sygnatura roli

Plik `roles/svc_unit/meta/argument_specs.yml` opisuje typy, wymagalność i `choices`. Ansible dodaje
na początku roli zadanie `Validating arguments against arg spec 'main'`. Pięć przypadków:

| # | Wywołanie | Wynik |
|---|---|---|
| 1 | brak `svc_name` | ❌ `missing required arguments: svc_name` |
| 2 | `svc_env: qa` | ❌ `value of svc_env must be one of: dev, stage, prod, got: qa` |
| 3 | `svc_port: "osiem"` | ❌ `unable to convert to int` |
| 4 | `svc_color: red` (nieznany parametr) | ✅ **przeszło** |
| 5 | `svc_port: "9500"` (napis) | ✅ **przeszło**, skonwertowane do `int` |

Przypadki 4 i 5 są ciekawsze niż błędy. **Nieznany parametr nie jest błędem**: przy `include_role`
`svc_color` to po prostu kolejna zmienna, a nie argument metody. Literówka w nazwie parametru
(`svc_prot` zamiast `svc_port`) nie zostanie wyłapana — rola cicho użyje domyślnego `8080`.
Napis `"9500"` zadziałał, bo walidator rzutuje typy.

> 💡 **Dlaczego to ważne:** `required: true` zastępuje całe bloki `assert` na początku roli i daje
> błąd *przed* pierwszą zmianą na hoście, a nie w połowie wdrożenia. Ale pamiętaj o przypadku 4 —
> to nie jest kompilator.

Haczyk, który wyszedł przy pisaniu: `vars: "{{ case.args }}"` (cały słownik jako zmienne) w
`include_role` kończy się błędem `Vars in a IncludeRole must be specified as a dictionary`. Zmienne
trzeba wypisać literalnie.

### 💧 4. Co wycieka po wywołaniu roli? (Zaskoczenie)

Rolę `svc_unit` (domyślny `svc_port: 8080`) wołamy z `svc_port: 9100…9400`, a następnie, w tym
samym playu, odczytujemy `svc_port`, `svc_env` i `svc_unit_result` (to `register` z wnętrza roli):

| Sposób | `svc_port` w playu | `svc_env` (default roli) | `svc_unit_result` (`register`) |
|---|---|---|---|
| `roles:` | `8080` | `dev` | zdefiniowane |
| `include_role` | niezdefiniowane | niezdefiniowane | **zdefiniowane** |
| `include_role` + `public: true` | `8080` | `dev` | zdefiniowane |
| `import_role` | `8080` | `dev` | zdefiniowane |

Dwie niespodzianki:

1. **Wycieka *default*, nie parametr.** `svc_port` w playu to `8080` — wartość z `defaults/main.yml`
   — a nie `9100`, którą przekazaliśmy do roli. Parametr żyje tylko w roli, ale `defaults` roli
   zostają „widoczne" dla reszty playa. Kod po roli, który odczyta `svc_port`, dostanie wartość,
   której nikt nie podał.
2. **`register` wycieka zawsze.** Nawet z domyślnym (niepublicznym) `include_role` zmienna
   `svc_unit_result` jest widoczna dla reszty playa — `register` to fakt hosta, nie zmienna zakresu.

> 💡 **Dlaczego to ważne:** dwie role z `register: result` i tak samo nazwanymi zmiennymi depczą
> sobie po palcach. Prefiksuj wszystko nazwą roli (`svc_unit_result`, nie `result`) — tak jak tu.

### 🧱 5. `vars:` na bloku — zakres leksykalny

```
env=play-level          # przed blokiem
env=outer-block region=eu
env=inner-block region=eu   # blok zagnieżdżony nadpisuje
env=task-level              # vars na tasku bije blok
env=outer-block             # po bloku wewnętrznym wraca zewnętrzny
env=play-level region=NIEDEFINIOWANE   # po bloku zewnętrznym
```

Zmienne bloku działają jak zakres w C#: zagnieżdżone nadpisują, po wyjściu znikają. Co więcej,
działają **przez granicę roli**: blok z `vars: {svc_env: prod, svc_replicas: 4}` wokół
`include_role` bez własnych `vars` dał `env=prod replicas=4` (a rola przeszła walidację
`argument_specs`). Blok jest więc tanim sposobem na „wspólne parametry dla grupy ról".

### 📊 6. `set_stats`: liczby z całego przebiegu — i pułapka z `aggregate`

`set_stats` zapisuje dane **na poziomie przebiegu**, nie hosta. Normalnie widać je w sekcji
`CUSTOM STATS` po `PLAY RECAP`, o ile włączysz `show_custom_stats` (`ANSIBLE_SHOW_CUSTOM_STATS=true`
albo `[defaults] show_custom_stats = true`). W tym środowisku nie mogłem ustawić zmiennej
środowiskowej, więc dołączyłem krótki callback `dump_custom_stats.py`, który wypisuje
`stats.custom`. Trzy hosty (`units` = 2, 5, 3), cztery wersje wpisu:

```
CUSTOM_STATS_JSON: {"_run": {"aggregate_off": "3", "hosts_done": 3, "last_host": "n3",
  "units_sum_once": "10", "units_total": "253"},
  "n1": {"written_changed": false}, "n2": {...}, "n3": {...}}
```

| Wpis | Efekt |
|---|---|
| `hosts_done: 1`, `aggregate: true` | `3` — liczby zsumowane po hostach ✅ |
| `units_total: "{{ units \| int }}"`, `aggregate: true` | **`"253"`** ❌ — napisy sklejone: `"2"+"5"+"3"` |
| `aggregate: false` | ostatni zapis wygrywa (`last_host: n3`) |
| `per_host: true` | osobny wpis pod nazwą hosta |
| `run_once` + suma w Jinja | `"10"` ✅ poprawna wartość |

> 💡 **Dlaczego to ważne:** szablon Jinja zawsze zwraca napis, więc `| int` w `data:` nie
> daje liczby — a agregacja napisów to konkatenacja. Raport „łączna liczba jednostek: 253" zamiast
> 10 wygląda wiarygodnie. Albo licz raz (`run_once` + `sum`), albo używaj literałów `1`.

---

### ✅ Co zweryfikowano, a czego nie

| Zweryfikowane (`ansible-core 2.17.14`) | Niezweryfikowane |
|---|---|
| `--syntax-check` 6 playbooków | `show_custom_stats` jako wbudowane wyjście (`env ...` odrzucone przez środowisko — użyty własny callback) |
| Deduplikacja `roles:` (różne / identyczne parametry, `allow_duplicates`) | `include_role` z `apply:` i tagami, `rolespec_validate: false` |
| `include_role` w pętli (2 przebiegi, `changed=0`), `tasks_from` | Walidacja `argument_specs` dla `tasks_from` innego niż `main` (w tym wydaniu `health` nie ma własnej specyfikacji) |
| `argument_specs`: 5 przypadków (3 błędy, 2 przejścia) | `private_role_vars` (ustawienie wyłączające wyciek defaultów) |
| Wyciek zmiennych: 4 sposoby wywołania | `set_stats` w playbookach z wieloma playami |
| `block` vars: zagnieżdżenie, role w bloku | SSH/`become`, vault/galaxy/Molecule (blokady środowiska) |
| `set_stats`: aggregate / bez / `per_host` / `run_once`, 2 przebiegi | Kolejność zapisu `aggregate: false` przy innej liczbie forków (u nas `n3` było ostatnie) |

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Pliki testowe powstają w `/tmp/ansible-demo-lvl18`;
usuwa je `cleanup.yml`.

---

<div align="center">

[← wróć do wydania #18 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
