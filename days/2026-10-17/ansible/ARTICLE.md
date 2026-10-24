<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #24 — 17 października 2026

![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)
![ansible-core](https://img.shields.io/badge/ansible--core-2.17.14-informational?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)

## Edycja plików bez katastrofy: kolizja markerów, `backup` i `validate`

</div>

---

> _"Dwa zespoły dopisują po bloku do tego samego pliku konfiguracyjnego. Playbook się zielenieje,
> a w pliku jest tylko jeden z bloków. Dziś: jak to się dzieje po cichu, czego `backup: true` NIE
> robi i dlaczego `validate` widzi cały plik, a nie Twój blok."_

W wydaniu #17 poznaliśmy `lineinfile`, `blockinfile`, `template` z `validate` i `assemble`. Zostały
trzy pytania „co jeśli": co, gdy dwie role piszą do jednego pliku; kiedy dokładnie powstaje kopia
zapasowa; i co faktycznie dostaje walidator. Dla .NET dewelopera analogia: dwa wątki robiące
`File.WriteAllText` na tym samym pliku, tyle że „wątkami" są role, a wyścig jest deterministyczny.

| Temat | Analogia z .NET | Zweryfikowane? |
|---|---|---|
| Kolizja markerów `blockinfile` w dwóch rolach | Dwa moduły z tym samym kluczem w `Dictionary` | ✅ 2 przebiegi kolizji + 2 po naprawie |
| `create` i `backup` w `lineinfile` | `File.Exists` + `File.Copy` przed zapisem | ✅ 3 przebiegi |
| `validate` w `lineinfile` / `blockinfile` / `assemble` | Walidacja modelu przed `SaveChanges()` | ✅ 2 przebiegi, `changed=0` |

Kod: [`code/`](code/). Wszystko pisze tylko do `/tmp/ansible-demo-lvl24`, sprzątanie: `cleanup.yml`.

---

### 💥 1. Dwie role, jeden marker: ostatnia wygrywa, a `changed` nigdy nie gaśnie

`blockinfile` rozpoznaje „swój" blok po markerze (domyślnie `# BEGIN/END ANSIBLE MANAGED BLOCK`).
Rola `team_a` dopisuje `limit_a`/`timeout_a`, rola `team_b` dopisuje `flag_b`/`retries_b` — obie
z domyślnym markerem, obie do `shared.conf`. Plik po pierwszym przebiegu:

```
# BEGIN ANSIBLE MANAGED BLOCK
flag_b=on
retries_b=5
# END ANSIBLE MANAGED BLOCK
```

Bloku zespołu A **nie ma**. Dla modułu to jeden i ten sam blok, więc `team_b` podmienił zawartość
bloku `team_a`. Przebieg pierwszy: `changed=3`, a drugi, bez żadnej zmiany w kodzie: **`changed=2`**
— każda rola w każdym przebiegu „naprawia" to, co zepsuła druga. Nie ma błędu, nie ma ostrzeżenia.

Poprawka to marker z tożsamością roli (`marker: "# {mark} team_a"`). Po niej:

```
# BEGIN team_a
limit_a=100
timeout_a=30
# END team_a
# BEGIN team_b
flag_b=on
retries_b=5
# END team_b
```

Pierwszy przebieg `changed=3`, drugi **`changed=0`**.

> 💡 **Dlaczego to ważne:** `changed=2` w drugim przebiegu to jedyny sygnał. Jeśli nie pilnujesz
> idempotencji (a w CI często nikt nie uruchamia playbooka dwa razy), stracisz konfigurację zespołu A
> i dowiesz się o tym na produkcji. Zasada: marker to klucz główny bloku — nazwij go po właścicielu.

### 🗂️ 2. `create` i `backup`: dwa mity

**`create` jest domyślnie wyłączone.** `lineinfile` na nieistniejącym pliku kończy się błędem, a nie
utworzeniem pliku:

```
fatal: [localhost]: FAILED! => {"changed": false, "msg": "Destination /tmp/ansible-demo-lvl24/backup/app.conf does not exist !", "rc": 257}
```

**`backup: true` robi kopię tylko wtedy, gdy plik istnieje i faktycznie się zmienia.** Pięć kroków
na jednym pliku (`port=8080` → `9090` → `9090` → `9191`):

```
krok 2: changed=True  backup=                                   # plik dopiero powstał (create)
krok 3: changed=True  backup=app.conf.438194.2026-10-17@00:41:49~
krok 4: changed=False backup=                                   # bez zmiany = bez kopii
krok 5: changed=True  backup=app.conf.438246.2026-10-17@00:41:50~
```

Kopia z kroku 3 zawiera `['port=8080']` — czyli stan *przed* zmianą. W katalogu są trzy pliki:
`app.conf` i dwie kopie (`app.conf.<pid>.<data>@<czas>~`).

Dwa haczyki zmierzone po drodze:

1. **Klucz wyniku nazywa się `backup`, nie `backup_file`.** W `copy`/`template` jest `backup_file`;
   `lineinfile` zwraca `backup`. Rejestr `step3.backup_file` rzuca `undefined`, a `'backup_file' in
   step3` daje `False`. Przy braku kopii `backup` to pusty napis, nie brak klucza.
2. **Kopie się kumulują, bez rotacji.** Każdy przebieg ze zmianą dokłada plik z `~`. Po kolejnych
   przebiegach katalog rósł (w naszym teście 2 kopie po pierwszym przebiegu, 4 po drugim na tym
   samym pliku). Ansible niczego nie sprząta — to Twoje zadanie (np. `find` + `file: absent`).

> 💡 **Dlaczego to ważne:** `backup` to bilet powrotny, ale tylko do stanu tuż przed *ostatnią*
> zmianą, a w nazwie jest PID i znacznik czasu, więc skryptu „przywróć ostatnią kopię" nie napiszesz
> bez `find` i sortowania.

### 🛡️ 3. `validate`: walidator dostaje CAŁY plik

`validate` działa w `lineinfile`, `blockinfile` i `assemble`. Ansible zapisuje wynik do pliku
tymczasowego, uruchamia Twoje polecenie (`%s` = ścieżka) i dopiero przy `rc=0` podmienia cel. Nasz
walidator `validate_conf.py` wymaga formatu `klucz=wartość` (komentarze pomija). Wyniki:

| Przypadek | Wynik | Plik docelowy |
|---|---|---|
| A1 `lineinfile` `port=9090` | ✅ `changed` | zmieniony |
| A2 `lineinfile` `port 9091` | ❌ `failed to validate: rc:1 error:niepoprawny format key=value: linia 1: 'port 9091'` | **bez zmian** (`port=9090`) |
| B1 `blockinfile` `cache=on`, `ttl=60` | ✅ `changed` | blok dopisany |
| B2 `blockinfile` z linią `ttl: 120` | ❌ `... linia 5: 'ttl: 120'` | **bez zmian** |
| C1 `assemble` z `frag_ok` | ✅ `changed` | `['a=1', 'b=2']` |
| C2 `assemble` z `frag_bad` | ❌ `... linia 2: 'to nie jest key=value'` | **bez zmian** (`['a=1', 'b=2']`) |

Zwróć uwagę na numery linii: w B2 błąd jest w „linii 5", bo walidator widzi **cały plik**, łącznie z
istniejącymi liniami i markerami. Zrzut tego, co dostał przy B1:

```
['port=9090', 'mode=prod', '# BEGIN ANSIBLE MANAGED BLOCK', 'cache=on', 'ttl=60', '# END ANSIBLE MANAGED BLOCK']
```

Konsekwencje: walidator musi znosić linie spoza bloku (u nas komentarze markerów są pomijane —
walidator, który nie zna komentarzy, odrzuci każdy `blockinfile`), a cudze błędy w pliku zablokują
Twoją poprawną zmianę. Drugi przebieg całego `validate.yml`: **`changed=0`** (16 zadań, 3 scenariusze
błędu zgodnie z planem trafiają do `rescued=3`).

> 💡 **Dlaczego to ważne:** `validate` to bezpiecznik „nie zepsuj działającej konfiguracji": zły
> wsad kończy się błędem zadania, a nie położonym serwisem po restarcie. W prawdziwym życiu w miejsce
> `validate_conf.py` wstawiasz `nginx -t -c %s` czy `visudo -cf %s`.

---

### ✅ Co zweryfikowano, a czego nie

| Zweryfikowane (`ansible-core 2.17.14`) | Niezweryfikowane |
|---|---|
| `--syntax-check` playbooków `collision`, `backup`, `validate` | `nginx -t`, `visudo -cf` (użyty własny walidator w Pythonie) |
| Kolizja markerów: 2 przebiegi (`changed=3`, potem `2`), po naprawie (`changed=3`, potem `0`) | Kolizja przy równoległych playach / `serial` / wielu hostach |
| `create` (błąd bez), `backup` (kopia tylko przy zmianie, klucz `backup`), 3 przebiegi | `backup` w `blockinfile`/`template`/`copy` (sprawdzony tylko `lineinfile`); zachowanie dwóch zmian w tej samej sekundzie |
| `validate` w `lineinfile`, `blockinfile`, `assemble`: dobre i złe wsady, 2 przebiegi (drugi `changed=0`) | `validate` z `--check`, zachowanie przy błędzie walidatora systemowego (`rc` ≠ 1) |
| Pozostałe: — | SSH/`become`, vault/galaxy/Molecule (blokady środowiska) |

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Pliki testowe powstają w `/tmp/ansible-demo-lvl24`;
usuwa je `cleanup.yml`.

---

<div align="center">

[← wróć do wydania #24 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
