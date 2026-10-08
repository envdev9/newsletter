<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #15 — 8 października 2026

![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)
![ansible-core](https://img.shields.io/badge/ansible--core-2.17.14-informational?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)

## Kto wygrywa, gdy zmienna ma 10 właścicieli? Pierwszeństwo zmiennych w Ansible — zmierzone pojedynek po pojedynku

</div>

---

> _"W .NET wiesz, że `appsettings.json` przegrywa ze zmienną środowiskową, a ta z argumentem
> wiersza poleceń. W Ansible warstw jest **dwadzieścia dwie**. Dziś sprawdzam je nie z tabelki
> w dokumentacji, tylko własnym playbookiem."_

Wszystkie poprzednie wydania zakładały, że zmienna ma jedno miejsce zdefiniowania. W prawdziwych
repozytoriach ta sama zmienna siedzi w `defaults` roli, `group_vars`, `host_vars`, `vars:` playa,
pliku dołączonym i w `-e` — i **wygrywa tylko jedna**. Pomyłka tutaj to klasyczne „zmieniłem
wartość w `group_vars`, a na serwerze dalej stara" (bo rola ma ją w `vars/`, który jest wyżej).

| Pojedynek | Analogia z .NET | Zweryfikowane? |
|---|---|---|
| 10 par warstw: `defaults` ... `-e` | Kolejność dostawców `IConfiguration` | ✅ uruchomione |
| `-e` wygrywa z `set_fact` | Argument CLI wygrywa ze wszystkim | ✅ uruchomione |
| Dwie grupy tego samego poziomu | Dwa dostawcy konfiguracji — wygrywa późniejszy | ✅ uruchomione |
| `ansible_group_priority` | Jawna kolejność dostawców | ✅ uruchomione |

Kod: [`code/`](code/). Metoda: każda zmienna `d01`–`d10` jest zdefiniowana w **dwóch** sąsiednich
warstwach z wartością równą nazwie warstwy, więc w wyniku od razu widać zwycięzcę.

---

### 🥊 1. Dziesięć pojedynków (prawdziwy output)

```
d01 role defaults  vs group_vars/all    -> group_vars/all
d02 group_vars/all vs group_vars/web    -> group_vars/web
d03 group_vars/web vs host_vars         -> host_vars/node1
d04 host_vars      vs play vars         -> play vars
d05 play vars      vs vars_files        -> vars_files
d06 vars_files     vs role vars         -> role vars
d07 role vars      vs task vars         -> task vars
d08 task vars      vs include_vars      -> include_vars
d09 include_vars   vs set_fact          -> set_fact
d10 play+set_fact  vs -e                -> extra_vars   (bez -e: set_fact)
```

Z tego wynika drabinka (od najsłabszej):
`role defaults` < `group_vars/all` < `group_vars/<grupa>` < `host_vars` < `vars:` playa <
`vars_files` < `vars/` roli < `vars:` taska < `include_vars` < `set_fact` < `-e`.
To zgadza się z dokumentacją — ale wynik pochodzi z pomiaru, nie z jej przepisania.

> 💡 **Dlaczego to ważne:** `defaults/main.yml` roli to najniższa półka — **po to istnieje**:
> każdy może to przesłonić. `vars/main.yml` roli to półka wysoka: nadpisze Ci `vars:` playa i
> `vars_files`, a z inventory nie ruszysz go w ogóle. Wartości, które użytkownik roli ma móc
> zmieniać, wkładaj do `defaults`; do `vars` — tylko stałe wewnętrzne.

### 😮 2. Dwie niespodzianki z drabinki

- **`include_vars` wygrał ze zmienną na samym tasku (d08).** Intuicja podpowiada „task jest
  najbliżej, więc wygra" — a nie. `include_vars` (i `set_fact`) wchodzą w *runtime* i leżą wyżej
  niż `vars:` na tasku.
- **`set_fact` bije `group_vars` aż do końca playa.** Raz ustawiony fakt zostaje, więc późniejsza
  zmiana w inventory nie pomoże, dopóki nie zacznie się nowy przebieg. Tylko `-e` jest wyżej.

### 👯 3. Dwie grupy, ta sama zmienna, jeden host

Host `node2` należy do `alpha` i `beta`; obie grupy ustawiają `kolor`.

```
kolor = beta
```

Przy równym priorytecie wygrywa grupa **późniejsza alfabetycznie**. Zmieniamy to jawnie —
`ansible_group_priority=10` w `[alpha:vars]` (inny plik inwentarza `inventory_priority/`):

```
kolor = alpha
```

> 💡 **Dlaczego to ważne:** bez priorytetu wynik zależy od **nazwy** grupy. Zmieniasz nazwę z
> `alpha` na `zeta` — i konfiguracja zmienia się „sama". Jeśli hosty mogą być w kilku grupach z
> tą samą zmienną, ustaw `ansible_group_priority` albo unikaj takiej sytuacji.

---

### ✅ Co zweryfikowano, a czego nie

| Zweryfikowane (`ansible-core 2.17.14`) | Niezweryfikowane |
|---|---|
| `--syntax-check` playbooków | Warstwy poza testowanymi: parametry roli (`roles: - role: x, d: ..`), `block` vars, parametry `include_role`, `vars_prompt`, fakty hosta, rejestr (`register`) |
| 10 pojedynków w jednym przebiegu + wariant z `-e` | Grupy `group_vars` w katalogu playbooka vs inventory |
| Grupy równorzędne: `beta` wygrywa; z `ansible_group_priority` wygrywa `alpha` | `ansible-vault`/`galaxy`/`ansible-doc`, Molecule, SSH/`become` (blokady środowiska) |
| Każdy scenariusz uruchomiony raz | Dynamic inventory przez `-i` (nadal bez `+x`) |

Pułapki z tego wydania:
1. `vars/` roli jest **wyżej** niż `vars:` playa i `vars_files` — nie wkładaj tam rzeczy do nadpisywania.
2. `include_vars` i `set_fact` biją zmienną na tasku.
3. Równorzędne grupy rozstrzyga alfabet; użyj `ansible_group_priority`.
4. Nic z `--syntax-check` nie powie, która warstwa wygra — tylko uruchomienie.

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Kod nic nie zapisuje na dysku.

---

<div align="center">

[← wróć do wydania #15 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
