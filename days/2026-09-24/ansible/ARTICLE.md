<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #1 — 24 września 2026

![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)

## Pierwszy playbook, który naprawdę coś robi

</div>

---

> _"Ansible nie pyta 'co mam zrobić', tylko 'jak ma wyglądać świat' - a potem sam
> dogaduje, czy trzeba cokolwiek ruszać."_

Jeśli znasz .NET, ale nigdy nie dotknąłeś Ansible - dziś zero teorii "na sucho".
Piszemy playbook, który tworzy katalog, zapisuje do niego plik z treścią zbudowaną
ze zmiennej i wypisuje komunikat na konsoli. Uruchamiamy go **naprawdę**, dwa razy
z rzędu, żeby zobaczyć na własne oczy najważniejszą cechę Ansible: idempotencję.
Zero prawdziwych serwerów - wszystko na `localhost`. Kod w [`code/`](code/).

---

### Ansible w jednym zdaniu (dla kogoś z .NET)

Ansible to narzędzie do automatyzacji - "opisz stan, jaki ma mieć maszyna, a Ansible
sam wykona kroki, żeby ten stan osiągnąć". Najbliższa analogia z Twojego świata:
to trochę jak `dotnet ef database update` względem migracji EF Core - nie mówisz
bazie "wykonaj ten konkretny ALTER TABLE", tylko "ma wyglądać jak najnowsza migracja",
a narzędzie samo sprawdza, co już jest zrobione, i wykonuje tylko brakujące kroki.
Ansible robi to samo, tylko dla całych maszyn: plików, pakietów, usług, użytkowników,
konfiguracji.

Nie potrzebujesz agenta zainstalowanego na docelowej maszynie (jak np. Puppet czy
Chef) - Ansible normalnie łączy się po SSH i uruchamia tam małe skrypty Pythona.
W dzisiejszym przykładzie pomijamy nawet SSH: mówimy Ansible "połącz się lokalnie",
żeby zademonstrować składnię bez stawiania serwera.

---

### Pięć pojęć, bez których nic tu nie zrozumiesz

- **Inventory** (inwentarz) - lista maszyn, na których Ansible ma działać. W
  najprostszej postaci to zwykły plik tekstowy z nazwami hostów pogrupowanymi w
  `[grupy]`. U nas: jeden host, `localhost`.
- **Play** - "dla tej grupy hostów wykonaj ten zestaw zadań". Jeden plik `playbook.yml`
  może zawierać kilka playów (np. jeden dla serwerów bazodanowych, drugi dla
  webowych) - dziś mamy jeden.
- **Task** (zadanie) - pojedynczy krok w playu, np. "stwórz katalog", "zapisz plik",
  "zrestartuj usługę". Taski wykonują się po kolei, od góry do dołu.
- **Module** (moduł) - to, co faktycznie robi robotę wewnątrz taska. `file`,
  `copy`, `debug` to moduły - gotowe, przetestowane "cegiełki" dostarczane z
  Ansible. Task = wywołanie modułu z konkretnymi parametrami, mniej więcej jak
  wywołanie metody z konkretnymi argumentami.
- **Idempotencja** - najważniejsza właściwość dobrze napisanego taska: uruchomienie
  go 10 razy z rzędu daje ten sam efekt końcowy co uruchomienie raz. Moduł `file`
  przed utworzeniem katalogu sprawdza, czy katalog już istnieje - jeśli tak, nic nie
  robi i zgłasza `ok` zamiast `changed`. To jest coś, o czym w kodzie C# musisz
  pamiętać sam (np. `if (!Directory.Exists(path))`) - w Ansible dostajesz to za
  darmo z modułu.

---

### Playbook krok po kroku

Dwa pliki, oba w [`code/`](code/):

**`inventory`** - jeden host, połączenie lokalne zamiast SSH:

```ini
[demo]
localhost ansible_connection=local
```

`ansible_connection=local` to sedno tego, że nie potrzebujesz żadnego serwera do
nauki - Ansible uruchamia moduły bezpośrednio w tej samej powłoce, w której
odpalasz `ansible-playbook`.

**`playbook.yml`** - jeden play, trzy taski, sekcja `vars`:

```yaml
---
- name: Pierwszy playbook - katalog roboczy i plik powitalny
  hosts: demo
  gather_facts: false

  vars:
    work_dir: /tmp/ansible-demo
    greeting_file: "{{ work_dir }}/powitanie.txt"
    greeting_message: "Cześć, {{ your_name | default('Świecie') }}! Ten plik stworzył Ansible."

  tasks:
    - name: Upewnij się, że katalog roboczy istnieje
      ansible.builtin.file:
        path: "{{ work_dir }}"
        state: directory
        mode: "0755"

    - name: Zapisz plik powitalny z treścią zbudowaną ze zmiennej
      ansible.builtin.copy:
        dest: "{{ greeting_file }}"
        content: "{{ greeting_message }}\n"

    - name: Pokaż na konsoli, co właśnie zrobiliśmy
      ansible.builtin.debug:
        msg: "Zapisano '{{ greeting_message }}' do {{ greeting_file }}"
```

Kilka rzeczy wartych wyjaśnienia:

- `hosts: demo` odwołuje się do grupy `[demo]` z pliku `inventory` - stąd wiadomo,
  na czym play ma działać.
- `gather_facts: false` wyłącza domyślne (dość powolne) zbieranie informacji o
  systemie docelowym na starcie playa - przy `localhost` i tak prostym playbooku
  nie są nam potrzebne, więc wyłączamy je dla szybkości.
- `vars` to zwykłe podstawianie tekstu w stylu Jinja2 (`{{ nazwa }}`) - jak
  interpolacja stringów, tylko rozwiązywana przez Ansible przed uruchomieniem
  taska. `{{ your_name | default('Świecie') }}` to filtr - "użyj `your_name`,
  a jak nie podano, wstaw `'Świecie'`" (odpowiednik `?? "Świecie"` w C#).
- Moduł `ansible.builtin.file` z `state: directory` = "upewnij się, że ten katalog
  istnieje" (tworzy go, jeśli brakuje; nic nie robi, jeśli już jest).
- Moduł `ansible.builtin.copy` z `content:` = "ten plik ma zawierać dokładnie ten
  tekst" (nadpisuje plik tylko, jeśli treść się różni).
- Moduł `ansible.builtin.debug` = odpowiednik `Console.WriteLine` - nic nie zmienia
  na dysku, tylko wypisuje komunikat. Dlatego zawsze zgłasza `ok`, nigdy `changed`.

---

### Idempotencja na żywo - to samo polecenie, dwa różne wyniki

Uruchomiony **pierwszy raz**, playbook faktycznie coś tworzy - dwa taski kończą się
jako `changed`:

```
TASK [Upewnij się, że katalog roboczy istnieje] ***
changed: [localhost]

TASK [Zapisz plik powitalny z treścią zbudowaną ze zmiennej] ***
changed: [localhost]

TASK [Pokaż na konsoli, co właśnie zrobiliśmy] ***
ok: [localhost] => {
    "msg": "Zapisano 'Cześć, Świecie! Ten plik stworzył Ansible.' do /tmp/ansible-demo/powitanie.txt"
}

PLAY RECAP ***
localhost : ok=3   changed=2   unreachable=0   failed=0   skipped=0
```

Uruchomiony **drugi raz, bez żadnej zmiany w plikach** - katalog już istnieje, plik
ma już dokładnie taką treść, więc Ansible nic nie rusza. Wszystkie taski zgłaszają
`ok`, licznik `changed` spada do zera:

```
TASK [Upewnij się, że katalog roboczy istnieje] ***
ok: [localhost]

TASK [Zapisz plik powitalny z treścią zbudowaną ze zmiennej] ***
ok: [localhost]

PLAY RECAP ***
localhost : ok=3   changed=0   unreachable=0   failed=0   skipped=0
```

To jest cała filozofia Ansible w praktyce: playbook opisuje **stan docelowy**, nie
sekwencję komend. Możesz go uruchamiać codziennie w cronie albo w CI po każdym
deployu - jeśli nic się nie zmieniło, nic się nie wydarzy. Jeśli ktoś ręcznie usunie
plik, kolejny przebieg go odtworzy.

---

### Zmienne z linii poleceń

`greeting_message` korzysta z `your_name`, którego nigdzie nie zdefiniowaliśmy w
`vars` - dlatego zadziałał domyślny `'Świecie'`. Można go nadpisać z zewnątrz flagą
`-e` (extra vars), bez dotykania pliku:

```bash
ansible-playbook -i inventory playbook.yml -e "your_name=Mag"
```

Efekt - task `copy` znowu zgłasza `changed` (bo treść pliku faktycznie się zmieniła
na `"Cześć, Mag! ..."`), ale `file` dalej jest `ok` (katalog przecież nie zmienił się
wcale). To dobrze pokazuje, że idempotencja jest liczona **per task**, nie dla
całego playbooka naraz.

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — instalacja Ansible, wszystkie komendy i
pełny, prawdziwy output z trzech przebiegów (pierwszy, idempotentny drugi, trzeci ze
zmienną z linii poleceń).

---

<div align="center">

[← wróć do wydania #1 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
