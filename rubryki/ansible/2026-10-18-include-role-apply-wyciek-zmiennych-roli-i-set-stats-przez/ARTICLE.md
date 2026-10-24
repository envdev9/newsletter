<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #25 — 18 października 2026

![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)
![ansible-core](https://img.shields.io/badge/ansible--core-2.17.14-informational?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)

## `include_role` + `apply:`, wyciek zmiennych roli i `set_stats` przez wiele playów

</div>

---

> _"Dodałeś tag do `include_role`, odpaliłeś `--tags deploy` i... nic się nie wydarzyło. Zadania roli
> po cichu pominięto. Dziś: dlaczego tag nie wchodzi do środka, jak to naprawia `apply:` i jak zbierać
> liczniki z całego przebiegu."_

W wydaniu #18 rola była „metodą z sygnaturą" (parametry, `argument_specs`, wyciek zmiennych). Zostały
trzy wątki, które w prawdziwych repozytoriach gryzą najmocniej: dynamiczne dołączanie roli z
dziedziczeniem tagów i środowiska, zmienne roli widoczne poza nią oraz statystyki zbierane z wielu playów.
Analogia dla .NET dewelopera: `include_role` to wywołanie metody w runtime (jak `Activator.CreateInstance`
— Ansible decyduje w trakcie przebiegu), a `apply:` to `using`/kontekst, który przekazujesz do środka.

| Temat | Analogia z .NET | Zweryfikowane? |
|---|---|---|
| `include_role` + `apply:` (`tags`, `environment`) | Przekazanie `AsyncLocal`/kontekstu do wywoływanej metody | ✅ 3 przebiegi |
| `environment` bezpośrednio na `include_role` | Atrybut na niewłaściwym elemencie — błąd kompilacji | ✅ syntax-check |
| `private_role_vars` | `private` zamiast `public` dla pól klasy | ⚠️ tylko stan bazowy (bez flagi) |
| `set_stats` w wielu playach (`aggregate`, `per_host`) | Metryki zbierane do jednego licznika w całym żądaniu | ✅ 2 przebiegi |

Kod: [`code/`](code/). Wszystko jest lokalne (`localhost` i 3 hosty z `ansible_connection=local`),
nic nie pisze na dysk poza `__pycache__` pluginu.

---

### 🏷️ 1. Tag na `include_role` nie wchodzi do środka

Ansible ma dwa światy: **statyczny** (`import_*`, `roles:`) — parsowany przed startem, tagi
dziedziczone — i **dynamiczny** (`include_*`) — rozwijany dopiero w trakcie przebiegu. Tag na
`include_role` dotyczy tylko samego zadania „dołącz", a nie zadań wewnątrz roli. Rola `probe` ma
dwa zadania bez żadnych tagów. Dwa include'y:

```yaml
- name: "A) include_role z samym tagiem"
  ansible.builtin.include_role: { name: probe }
  tags: [only_tag]

- name: "B) include_role z tagiem + apply"
  ansible.builtin.include_role:
    name: probe
    apply:
      tags: [applied_tag]
      environment:
        DEMO_ENV: "ustawione-przez-apply"
  tags: [applied_tag]
```

`--tags only_tag` (prawdziwy output):

```
TASK [A) include_role z samym tagiem] ******************************************
included: probe for localhost

PLAY RECAP ... ok=1
```

Rola została dołączona, ale **ani jedno jej zadanie się nie wykonało**. `--tags applied_tag`:

```
TASK [B) include_role z tagiem + apply (tags, environment)] ********************
included: probe for localhost
TASK [probe : probe: odczyt DEMO_ENV na hoście] ********************************
TASK [probe : probe: zadanie roli] *********************************************
    "msg": "rola probe wykonana, DEMO_ENV=ustawione-przez-apply"
PLAY RECAP ... ok=3
```

`apply:` przyklejło tag do każdego zadania wewnątrz roli (dlatego `--tags applied_tag` je łapie), a
razem z nim `environment` — zmienną widzi proces uruchomiony na hoście. Pełny przebieg bez `--tags`
daje `ok=6`: obie role, ale `DEMO_ENV=(brak)` w A i `ustawione-przez-apply` w B.

> 💡 **Dlaczego to ważne:** w pipeline'ie `ansible-playbook --tags deploy` „zielony i pusty" jest
> gorszy niż czerwony. Przy `include_role` tag musi być w DWÓCH miejscach: na include (żeby w ogóle
> go wykonać) i w `apply:` (żeby wykonać wnętrze). (Dla statycznych `roles:` / `import_role` tagi dziedziczą się według dokumentacji — tego dziś nie mierzyłem.)

**Haczyk 1: `environment` nie działa na `include_role`.** Próba umieszczenia go na samym zadaniu
`include_role` (nie w `apply:`) kończy się już na parsowaniu:

```
ERROR! 'environment' is not a valid attribute for a IncludeRole
```

To `--syntax-check` łapie, ale tylko dlatego, że to błąd strukturalny. Dozwolone słowa kluczowe
przekazujesz przez `apply:`.

**Haczyk 2: `lookup('env', ...)` nie widzi `environment:`.** Lookup działa na kontrolerze, a
`environment:` dotyczy procesu modułu na hoście. Pierwsza wersja naszej roli czytała `DEMO_ENV` przez
`lookup` i w obu wariantach pokazywała `(brak)` — to nie błąd `apply:`, tylko złe narzędzie pomiaru.
Odczyt trzeba zrobić modułem wykonywanym na hoście (u nas `shell`).

### 🔒 2. Zmienne roli po jej wywołaniu: stan bazowy

Zanim przejdziemy do `private_role_vars`, kontrola — co widać domyślnie. Rola `probe` ma
`defaults/main.yml` (`probe_default`) i `vars/main.yml` (`probe_fixed`). Po `roles: [probe]` oraz po
`include_role` z `public: true`, zadanie w playu pyta o obie zmienne:

```
"probe_default": "z defaults roli",
"probe_fixed": "z vars/ roli"
```

Obie **wyciekły** poza rolę i w obu wariantach są widoczne dla kolejnych zadań playa. Ansible ma
ustawienie `private_role_vars` (`ANSIBLE_PRIVATE_ROLE_VARS=true` lub `private_role_vars = True` w
`ansible.cfg`), które to wyłącza — zmienne roli mają być widoczne tylko wewnątrz niej.

> ⚠️ **Niezweryfikowane:** nie udało się uruchomić wariantu z włączoną flagą. W tym środowisku nie
> mogłem ustawić zmiennej środowiskowej (polecenie z prefiksem `env` odrzucone), a `ansible.cfg` jest
> czytany z bieżącego katalogu roboczego, którego nie mogłem zmienić. Weryfikację wpisuję do README jako
> polecenie do samodzielnego odpalenia; **nie twierdzę, jaki będzie wynik** — pomiar opisany wyżej to
> tylko stan bez flagi.

> 💡 **Dlaczego to ważne:** wyciek `defaults` to częsta przyczyna „działa, bo inna rola przypadkiem
> ustawiła tę zmienną". Znasz to z .NET: pole `public static` zmieniane z dowolnego miejsca.

### 📊 3. `set_stats` przez wiele playów: liczniki całego przebiegu

W #18 `set_stats` działało w jednym playu. Tu trzy playe na trzech hostach (`fleet`: n1–n3). Play 1:
każdy host dodaje `pliki: 2`, play 2: każdy `pliki: 3` (oba z `aggregate: true`). Play 3 pokazuje
`aggregate: false` (nadpisanie) i `per_host: true`. Zrzut `stats.custom` naszego własnego callbacku
(prawdziwy output, identyczny w dwóch przebiegach):

```
CUSTOM_STATS[_run]: {"etap": "play1play1play1play2play2play2", "ostatni_etap": "play3-n3", "pliki": 15}
CUSTOM_STATS[n1]: {"wersja": "v1"}
CUSTOM_STATS[n2]: {"wersja": "v1"}
CUSTOM_STATS[n3]: {"wersja": "v1"}
```

Co z tego wynika:

- **Liczniki sumują się przez play'e:** 3×2 + 3×3 = **15**. Statystyka żyje przez cały przebieg,
  nie jest resetowana między playami.
- **Globalny klucz to `_run`** (`per_host: false`, domyślne); `per_host: true` zakłada osobny klucz
  na host.
- **Napisy się konkatenują:** `etap` to sklejone `play1play1play1play2play2play2`, a nie „ostatnia
  wartość". Suma działa tylko dla liczb (w #18 poprawiliśmy to `run_once` + `sum`).
- **`aggregate: false` = ostatni zapis wygrywa:** `ostatni_etap` ma `play3-n3`. Wartość zależy od
  kolejności zakończenia hostów, więc przy `forks > 1` nie traktuj jej jako deterministycznej (w naszym
  teście w obu przebiegach było `n3`, ale tego nie gwarantuję).

> 💡 **Dlaczego to ważne:** to najprostszy sposób na „raport z wdrożenia" (ile plików zmieniono, ile
> hostów przeszło) bez parsowania logu. Pułapka: wartości liczbowe sumują się tylko wtedy, gdy są
> faktycznie liczbami — napis `"2"` skleja się jako `"222"`.

---

### ✅ Co zweryfikowano, a czego nie

| Zweryfikowane (`ansible-core 2.17.14`) | Niezweryfikowane |
|---|---|
| `--syntax-check` playbooków `apply`, `private`, `stats`; błąd `environment` na `include_role` | `private_role_vars` z włączoną flagą (brak możliwości ustawienia env/cfg) |
| `apply:` (`tags`, `environment`): `--tags only_tag`, `--tags applied_tag`, bez tagów | `apply:` z `become`/`when` i innymi słowami kluczowymi |
| Wyciek `defaults`/`vars` po `roles:` i `include_role public: true` (bez flagi) | `include_role` z `apply:` w pętli |
| `set_stats` w 3 playach: suma, konkatenacja napisów, `aggregate: false`, `per_host` — 2 przebiegi | Wbudowany `show_custom_stats` (użyty własny callback); `set_stats` przy `--check` |
| Pozostałe: — | SSH/`become`, vault/galaxy/Molecule (blokady środowiska) |

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wszystkie artykuły: 🔧 Ansible](../README.md) · [spis rubryk](../../../README.md)

</div>
