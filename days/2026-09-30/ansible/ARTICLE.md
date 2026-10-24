<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #7 — 30 września 2026

![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)
![ansible-core](https://img.shields.io/badge/ansible--core-2.17.14-informational?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)

## `serial` + `throttle` w jednym playu i nierówne paczki `run_once` — co się dzieje, gdy nakładasz dwa ograniczenia naraz

</div>

---

> _"`serial` dzieli play na osobne mini-playe wykonywane jeden po drugim. `throttle` ogranicza
> równoległość jednego taska. To dwie zupełnie różne warstwy — pytanie brzmi, czy druga działa
> WEWNĄTRZ pierwszej, czy obie się wykluczają. Odpowiedź: WEWNĄTRZ, i da się to zmierzyć co do
> milisekundy."_

W [#6](../../2026-09-29/ansible/ARTICLE.md) sprawdziliśmy `serial` i `throttle` **osobno**:
`run_once` + `serial: 2` (dokładnie 2 wykonania na 4 hostach) i `throttle: 2` (dwie realne fale
zamiast jednej). Na końcu zostały dwa pytania otwarte: co się stanie, gdy **połączysz obie
warstwy w jednym tasku**, i czy hipoteza "`run_once` wykonuje się raz na paczkę, zawsze przez
pierwszy host paczki" utrzyma się, gdy paczki `serial` **nie są równej wielkości**. Dziś
odpowiadamy na oba pytania realnym uruchomieniem — plus siódma z rzędu próba
`ansible-vault`/`ansible-galaxy`.

| Temat | Analogia z .NET | Zweryfikowane? |
|---|---|---|
| `ansible-vault` / `ansible-galaxy` / gołe `ansible --version` | user-secrets / NuGet | ❌ **odrzucone przez środowisko (siódmy raz z rzędu, #3–#7)** |
| `serial: 4` + `throttle: 2` na tym samym tasku, 8 hostów | `Parallel.ForEachAsync` z `MaxDegreeOfParallelism` zagnieżdżone wewnątrz kolejki paczek zadań | ✅ uruchomione, zmierzone znacznikami czasu |
| `run_once` + `serial: [1, 3]` (nierówne paczki, 5 hostów) | `lock`/singleton wykonany raz na "falę" — teraz z falami różnej wielkości | ✅ uruchomione, potwierdzone `ansible_play_batch` |

> ⚠️ **`ansible-vault`/`ansible-galaxy` — siódma próba, ten sam wynik.** Dziś sprawdzone na nowo,
> empirycznie, nie z założenia: `ansible-vault encrypt_string 'sekret' --name 'moj_sekret' | cat`
> i `ansible-galaxy --version | cat` zostały **odrzucone przez system uprawnień środowiska agenta**
> zanim jakikolwiek proces Ansible ruszył — komunikat to *"Permission to use Bash has been denied
> because Claude Code is running in don't ask mode"*, czyli odmowa na poziomie narzędzia Bash tej
> sesji, nie błąd samego `ansible-vault`. Co ciekawe, gołe `ansible --version | cat` też zostało
> odrzucone tym samym komunikatem, a `ansible-playbook --version 2>&1 | cat` zadziałał bez
> przeszkód (`ansible-core 2.17.14`) — więc konkretnie te dwie komendy (i goły `ansible`) są na
> jakiejś liście blokad, a `ansible-playbook` nie. Identyczny wzorzec jak w #3–#6. Nowe dziś:
> nawet goła komenda `ansible` w trybie **ad-hoc** (`ansible localhost -m ansible.builtin.file
> -a "..." -c local`) została odrzucona identycznie — blokada dotyczy więc binarki `ansible` jako
> takiej, nie tylko flagi `--version`. Wszystko poniżej w artykule to **prawdziwy output** z
> `ansible-playbook`, Python 3.10.4.

Kod: [`code/`](code/). Osiem fikcyjnych serwerów `app1..app8` (grupa `app_all`) — cztery więcej
niż w #6, bo `serial: 4` + `throttle: 2` na sensownej próbce wymaga liczby podzielnej przez 4, a
`serial: [1, 3]` (druga część) używa osobnej podgrupy `app_uneven` = pierwszych pięciu z nich.
Wszystko `ansible_connection=local` — bez prawdziwej floty SSH.

---

### 🎯 1. `serial: 4` + `throttle: 2` na tym samym tasku — kto tu naprawdę rządzi równoległością

Scenariusz: play ma `serial: 4` (8 hostów → 2 paczki po 4), a jeden konkretny task w tym playu ma
dodatkowo `throttle: 2`. Pytanie z #6 zostawione otwarte: czy `throttle` ogranicza równoległość
**wewnątrz** paczki `serial`, czy jest z nią w konflikcie (np. `throttle` przegrywa, bo `serial`
"już" ograniczył hosty), czy jest redundantny (np. Ansible i tak serializuje wszystko przez
`serial`, więc `throttle` nic nie zmienia)?

Dla kontrastu w tym samym pliku najpierw leci **baseline** — identyczny task, też w playu z
`serial: 4`, ale bez `throttle`:

```yaml
- name: "BASELINE - serial: 4 BEZ throttle (oczekiwane: 4 hosty naraz w kazdej z 2 paczek)"
  hosts: app_all
  serial: 4
  tasks:
    - name: "Task BEZ throttle (paczka 4-hostowa, forks domyslnie 5 -> caly serial batch naraz)"
      ansible.builtin.shell: >
        echo "BASELINE start $(date +%H:%M:%S.%3N) {{ inventory_hostname }}
        paczka={{ ansible_play_batch }}" >> {{ log_file }};
        sleep 2;
        echo "BASELINE koniec $(date +%H:%M:%S.%3N) {{ inventory_hostname }}" >> {{ log_file }}

- name: "KOMBINACJA - serial: 4 + throttle: 2 na tym samym tasku (glowny temat wydania)"
  hosts: app_all
  serial: 4
  tasks:
    - name: "Task z throttle: 2 WEWNATRZ paczki serial: 4"
      throttle: 2
      ansible.builtin.shell: >
        echo "COMBO start $(date +%H:%M:%S.%3N) {{ inventory_hostname }}
        paczka={{ ansible_play_batch }}" >> {{ log_file }};
        sleep 2;
        echo "COMBO koniec $(date +%H:%M:%S.%3N) {{ inventory_hostname }}" >> {{ log_file }}
```

Prawdziwy log (pełny output w [`code/README.md`](code/README.md)). Baseline potwierdza punkt
wyjścia znany z #6: `forks` domyślnie to 5, więc **cała 4-hostowa paczka** startuje naraz:

```
BASELINE start 01:26:14.775 app1 paczka=['app1', 'app2', 'app3', 'app4']
BASELINE start 01:26:14.776 app3 paczka=['app1', 'app2', 'app3', 'app4']
BASELINE start 01:26:14.830 app2 paczka=['app1', 'app2', 'app3', 'app4']
BASELINE start 01:26:14.833 app4 paczka=['app1', 'app2', 'app3', 'app4']
BASELINE koniec 01:26:16.780 app3
BASELINE koniec 01:26:16.781 app1
BASELINE koniec 01:26:16.834 app2
BASELINE koniec 01:26:16.836 app4
BASELINE start 01:26:17.549 app5 paczka=['app5', 'app6', 'app7', 'app8']   <- druga paczka dopiero PO pierwszej
...
```

A teraz kombinacja `serial: 4` + `throttle: 2` — w KAŻDEJ z dwóch paczek widać **dwie osobne
fale po 2 hosty**, nie 4 naraz i nie 4 po kolei:

```
COMBO start 01:26:20.101 app1 paczka=['app1', 'app2', 'app3', 'app4']   <- fala 1, paczka 1
COMBO start 01:26:20.163 app2 paczka=['app1', 'app2', 'app3', 'app4']
COMBO koniec 01:26:22.104 app1
COMBO koniec 01:26:22.169 app2
COMBO start 01:26:22.486 app3 paczka=['app1', 'app2', 'app3', 'app4']   <- fala 2, paczka 1 (PO fali 1)
COMBO start 01:26:22.593 app4 paczka=['app1', 'app2', 'app3', 'app4']
COMBO koniec 01:26:24.489 app3
COMBO koniec 01:26:24.596 app4
COMBO start 01:26:24.994 app5 paczka=['app5', 'app6', 'app7', 'app8']   <- fala 1, PACZKA 2 (PO calej paczki 1)
COMBO start 01:26:25.060 app6 paczka=['app5', 'app6', 'app7', 'app8']
COMBO koniec 01:26:26.998 app5
COMBO koniec 01:26:27.063 app6
COMBO start 01:26:27.387 app7 paczka=['app5', 'app6', 'app7', 'app8']   <- fala 2, paczka 2
COMBO start 01:26:27.465 app8 paczka=['app5', 'app6', 'app7', 'app8']
COMBO koniec 01:26:29.391 app7
COMBO koniec 01:26:29.468 app8
```

Odpowiedź jest jednoznaczna i widoczna w znacznikach czasu: **`throttle` działa WEWNĄTRZ paczki
`serial`, nie zamiast niej i nie równolegle do niej.** `app3`/`app4` (fala 2 paczki 1) startują o
`22.486`/`22.593` — dopiero **po** zakończeniu obu hostów fali 1 (`22.104`/`22.169`), mimo że
wszyscy czterej należą do tej samej paczki `serial` i przy baseline (bez `throttle`) startowali
razem. Analogicznie `app5` (pierwszy host paczki 2) nie startuje, zanim **cała** paczka 1 (obie
fale, 4 hosty) się nie skończy — `24.994` jest już po `24.596` (koniec fali 2 paczki 1). Zero
konfliktu, zero redundancji: to dwie zagnieżdżone warstwy ograniczeń, `serial` na zewnątrz
(sekwencyjne mini-playe po `N` hostów), `throttle` w środku (limit równoległości pojedynczego
taska w obrębie AKTUALNIE przetwarzanej paczki).

> 💡 **Dlaczego to ważne:** to dokładny odpowiednik zagnieżdżonego `Parallel.ForEachAsync` — jeśli
> masz zewnętrzną kolejkę "paczek" zadań (np. batch deployu co N maszyn, żeby nie przeciążyć
> load balancera) i wewnątrz każdej paczki chcesz dodatkowo ograniczyć równoległość jednego
> konkretnego, kosztownego kroku (np. migracja bazy, do której tylko 2 połączenia naraz są
> bezpieczne) — `serial` + `throttle` na tym samym tasku dają ci dokładnie to, bez pisania
> własnej logiki kolejkowania. Gdybyś się bał, że te dwa mechanizmy "się gryzą" — nie gryzą się,
> po prostu się składają.

---

### 🔁 2. `run_once` + `serial: [1, 3]` — nierówne paczki, ta sama zasada

W #6 `run_once` + `serial: 2` na 4 hostach dało dokładnie 2 wykonania (po jednym na równą,
2-hostową paczkę). Dziś sprawdzamy, czy zasada "raz na paczkę, przez pierwszy host paczki"
utrzymuje się, gdy paczki **nie są równe** — `serial: [1, 3]` na 5 hostach. Zgodnie z
dokumentacją Ansible lista `serial` jest konsumowana po kolei, a gdy się wyczerpie, **ostatnia
wartość jest powtarzana** dla kolejnych paczek. Tu lista ma 2 pozycje (`1`, `3`), a hostów jest
5 — więc trzecia paczka teoretycznie "chce" być rozmiaru 3, ale zostaje już tylko 1 host:

```yaml
- name: "run_once + serial: [1, 3] na 5 hostach (nierowne paczki + reszta po wyczerpaniu listy)"
  hosts: app_uneven
  serial: [1, 3]
  tasks:
    - name: "[batch] Zapisz znacznik run_once"
      run_once: true
      ansible.builtin.lineinfile:
        path: "{{ marker_file }}"
        line: >-
          run_once wykonany przez {{ inventory_hostname }} o
          {{ lookup('pipe', 'date +%H:%M:%S.%3N') }} | rozmiar paczki = {{ ansible_play_batch | length }}
          | paczka (ansible_play_batch) = {{ ansible_play_batch }}
        create: true
```

Prawdziwy wynik — dokładnie **3 wpisy**, jeden na paczkę, każdy przez pierwszego hosta tej
paczki:

```
run_once wykonany przez app1 o 01:26:37.337 | rozmiar paczki = 1 | paczka (ansible_play_batch) = ['app1']
run_once wykonany przez app2 o 01:26:37.943 | rozmiar paczki = 3 | paczka (ansible_play_batch) = ['app2', 'app3', 'app4']
run_once wykonany przez app5 o 01:26:38.366 | rozmiar paczki = 1 | paczka (ansible_play_batch) = ['app5']
```

Dokładnie tak, jak przewidywała dokumentacja i hipoteza z #6, teraz potwierdzona na nierównych
paczkach: paczka 1 ma rozmiar `1` (`app1`), paczka 2 ma rozmiar `3` (`app2`, `app3`, `app4` —
`run_once` wykonuje `app2`, pierwszy z tej trójki), a paczka 3 **próbowała** być rozmiaru `3`
(powtórzona ostatnia wartość z listy), ale że zostało tylko `app5`, dostała rozmiar `1` — i
`run_once` i tak wykonał się dokładnie raz, przez jedynego (więc też pierwszego) hosta tej
paczki. `PLAY RECAP` to potwierdza wprost: `app3`/`app4` mają `changed=0` (widziały wynik, ale
nie liczyły go), `app2` i `app5` mają `changed=1` (one faktycznie wykonały task).

> 💡 **Dlaczego to ważne:** `serial: [1, 3, 5]` (rosnące paczki — typowy wzorzec "canary, potem
> coraz szersze fale") to nie jest tylko kontrola tempa deployu — jeśli w tym samym playu masz
> `run_once` (np. "wyślij jedno powiadomienie na start fali"), dostaniesz **jedno powiadomienie
> na KAŻDĄ falę**, niezależnie od jej rozmiaru, także od tej "obciętej" ostatniej, gdy hostów
> zabraknie. Jeśli chcesz jednego powiadomienia na cały deploy, a nie na falę — to nadal ten sam
> wniosek co w #6: wyciągnij ten task do osobnego playa bez `serial`.

---

### 🧩 3. Co zostało jeszcze nieprzebadane (świadomie odłożone)

Trzeci punkt z listy na dziś — czy "zamrażanie" nazwy hosta w `TASK [...]` (zaobserwowane w #6
przy `serial` i `{{ inventory_hostname }}` w `name:`) występuje też w zwykłym playu **bez**
`serial`, tylko z pętlą `loop` po hostach przez `delegate_to` — **nie został dziś zbadany**,
żeby nie rozmywać głównego tematu (kombinacja `serial`+`throttle` i nierówne paczki to już dwa
pełne, samodzielne eksperymenty). Zostaje jawnie na liście "do zrobienia" w `STATE.md`.

---

### ✅ Co zweryfikowano, a czego nie

| Zweryfikowane (`ansible-core 2.17.14`) | Niezweryfikowane |
|---|---|
| `serial: 4` + `throttle: 2` na tym samym tasku — dwie fale po 2 hosty W KAŻDEJ z 2 paczek serial, potwierdzone znacznikami czasu | Czy "zamrażanie" nazwy taska z `{{ inventory_hostname }}` w `name:` występuje bez `serial` (pętla `loop` + `delegate_to`) |
| Baseline: `serial: 4` bez `throttle` — cała 4-hostowa paczka naraz (kontrola kontrastowa) | `throttle` łączony z `serial: N` gdzie `N` NIE jest wielokrotnością wartości `throttle` (np. `serial: 3` + `throttle: 2`) |
| `run_once` + `serial: [1, 3]` na 5 hostach — dokładnie 3 wykonania, po jednym na paczkę (rozmiary 1/3/1), zawsze przez pierwszy host paczki | `run_once` + `serial` z wartościami procentowymi (`serial: "25%"`) |
| Zachowanie listy `serial` po wyczerpaniu (powtórzenie ostatniej wartości, obcięte do liczby pozostałych hostów) | Zdalne SSH, `become` |
| `--syntax-check` na obu playbookach | `ansible-vault`, `ansible-galaxy`, gołe `ansible --version` — odrzucone przez środowisko (7. raz z rzędu, #3–#7) |

**Pułapki/spostrzeżenia z tego wydania:**
1. `throttle` na tasku wewnątrz playu z `serial` NIE konkuruje z `serial` ani nie jest przez nie
   "nadpisany" — działa jako dodatkowy, zagnieżdżony limit równoległości w obrębie *aktualnie
   przetwarzanej* paczki `serial`. Obie warstwy się składają, nie wykluczają.
2. Paczka `serial` z kolejnym tasku typu `throttle: 2` na paczce 4-hostowej to zawsze `ceil(N/T)`
   fal — tu 2 fale na paczkę, więc cały play (2 paczki) to 4 fale sekwencyjne total, nie 2.
3. `run_once` + nierówna lista `serial` (`[1, 3]`) — liczba wykonań to liczba PACZEK (nie liczba
   hostów ani długość listy `serial`), a rozmiar ostatniej, "obciętej" paczki nie psuje reguły
   "pierwszy host paczki wykonuje task" — działa identycznie jak przy równych paczkach z #6.

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Demo pisze wyłącznie do `/tmp/ansible-demo-lvl7`
(nowy katalog na to wydanie — sprzątnięty po zakończeniu weryfikacji, patrz sekcja "Sprzątanie"
w `code/README.md`).

---

<div align="center">

[← wróć do wydania #7 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
