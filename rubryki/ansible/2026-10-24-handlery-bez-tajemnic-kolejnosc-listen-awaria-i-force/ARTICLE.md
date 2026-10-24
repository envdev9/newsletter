<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #29 — 24 października 2026

![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)
![ansible-core](https://img.shields.io/badge/ansible--core-2.17.14-informational?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)

## Handlery bez tajemnic: kolejność, `listen`, awaria i `force_handlers`, łańcuchy

</div>

---

> _"Zmieniłeś konfigurację, następny krok padł, pipeline jest czerwony — a usługa nigdy nie dostała
> restartu. Następny przebieg: konfiguracja już jest 'ok', więc handler nie ruszy w ogóle. Dziś:
> dlaczego tak się dzieje i jak się przed tym bronić."_

Handlery pojawiły się w wydaniu #2 (`notify`, `flush_handlers`). Tu schodzimy poziom niżej, do
reguł, które w prawdziwych wdrożeniach decydują, czy usługa dostanie restart. Analogia dla .NET
dewelopera: handler to coś jak zdarzenie z odroczonym wykonaniem — `notify` to „zaznacz flagę",
a właściwe wywołanie następuje dopiero na końcu play'a (jak `finally` po całej sekwencji kroków).

| Temat | Analogia z .NET | Zweryfikowane? |
|---|---|---|
| Kolejność handlerów = kolejność **definicji**, nie `notify` | Kolejność `IHostedService` z rejestracji w DI, nie z momentu użycia | ✅ |
| Wielokrotny `notify` = jedno wykonanie; `listen` (topic) | Subskrypcja tematu pub/sub | ✅ |
| Awaria play'a gubi zgłoszone handlery; `force_handlers`, `flush_handlers` | `finally` zamiast „zwykłego" kodu po `try` | ✅ |
| Handler zgłaszający handler | Zdarzenie wyzwalające zdarzenie | ✅ (z niespodzianką) |

Kod: [`code/`](code/). Wszystko lokalne (`localhost`, `ansible_connection=local`), moduły `debug`/`fail`,
nic nie zapisuje na dysk.

---

### 🔢 1. Kolejność handlerów, deduplikacja i `listen`

Zadania zmieniają stan w kolejności **Z → Y → Y2 → X**. Handlery zdefiniowano w kolejności
**X, Y, Z, X2**. Zadanie Y i Y2 zgłaszają ten sam handler Y; X zgłasza **topic** `config changed`,
na który „słuchają" (`listen`) dwa handlery: X i X2. Zadanie N niczego nie zmienia (`changed_when: false`)
i zgłasza `handler NIGDY`.

```yaml
- name: "zadanie X (notify przez topic 'config changed')"
  ansible.builtin.debug: { msg: "robie X" }
  changed_when: true
  notify: config changed
# ...
handlers:
  - name: handler X (przez listen)
    ansible.builtin.debug: { msg: "HANDLER X (zdefiniowany 1.)" }
    listen: config changed
```

Prawdziwy output (skrót, bez treści `msg`):

```
RUNNING HANDLER [handler X (przez listen)]
RUNNING HANDLER [handler Y]
RUNNING HANDLER [handler Z]
RUNNING HANDLER [handler X2 (tez przez listen)]
PLAY RECAP: ok=9 changed=4 ...
```

Wnioski:

- **Kolejność = kolejność definicji w `handlers:`**, choć zadania zgłaszały Z jako pierwszy. Zgłoszenie
  to tylko flaga „uruchom", nie pozycja w kolejce.
- **Handler Y wykonał się raz**, mimo dwóch `notify` z dwóch zadań.
- **Jeden topic uruchamia wszystkich słuchaczy** (X i X2) — każdy w swoim miejscu kolejności definicji
  (X2 poszedł na końcu, bo był zdefiniowany jako czwarty).
- **`handler NIGDY` nie ruszył**: zadanie bez zmiany nie zgłasza. To mechanizm idempotencji z #2.

> 💡 **Dlaczego to ważne:** jeśli handlery mają zależność („najpierw przeładuj konfigurację, potem
> restartuj"), porządek ustala układ pliku, nie przebieg zadań. Ktoś „uporządkuje" alfabetycznie
> sekcję `handlers:` i zmieni semantykę wdrożenia — bez żadnego błędu składni. `listen` pozwala
> odpiąć zgłaszającego od nazw: zadanie mówi „config changed", a rola decyduje, co z tym zrobić.

### 💥 2. Awaria po zmianie: handler przepada

Zadanie zmienia konfigurację (zgłasza `restart uslugi`), kolejny krok kończy się `fail`. Trzy uruchomienia
tego samego playbooka (prawdziwy output, skrót):

```
# bez niczego
TASK [zmiana konfiguracji]      changed
TASK [ryzykowny krok]           fatal: FAILED!
PLAY RECAP: ok=1 changed=1 failed=1            <- brak "RUNNING HANDLER"

# -e force=true  (force_handlers: true na play'u)
TASK [ryzykowny krok]           fatal: FAILED!
RUNNING HANDLER [restart uslugi]                 <- handler uruchomiony po awarii
PLAY RECAP: ok=2 changed=1 failed=1

# -e flush=true  (meta: flush_handlers przed ryzykownym krokiem)
RUNNING HANDLER [restart uslugi]                 <- handler PRZED awarią
TASK [ryzykowny krok]           fatal: FAILED!
PLAY RECAP: ok=2 changed=1 failed=1
```

Domyślnie handlery odpalają się **na końcu play'a, a awaria go przerywa** — zgłoszony restart przepada.
Nie jest to teoretyczne: konfiguracja została już zmieniona na hoście. Przy kolejnym przebiegu zadanie
zgłosi `ok` zamiast `changed` (wniosek z idempotencji, tego scenariusza dwóch przebiegów nie uruchamiałem
na prawdziwym module), więc **handler nie zostanie zgłoszony** — usługa
działa na starej konfiguracji, a Ansible uważa stan za zgodny. Dwie obrony:

- `force_handlers: true` na play'u (u nas `"{{ force | default(false) | bool }}"` — `-e` przychodzi
  jako string, `| bool` jest konieczne) — zgłoszone handlery biegną mimo awarii.
- `meta: flush_handlers` — wymuszasz uruchomienie handlerów w konkretnym miejscu, przed ryzykownym krokiem.

> 💡 **Dlaczego to ważne:** to klasyczny „cichy dryf" — pipeline się wywalił, naprawiasz drobiazg,
> puszczasz ponownie, wszystko zielone, a restartu nie było. Jeśli handler jest niezbędny dla
> spójności (restart po zmianie konfiguracji), albo `force_handlers`, albo flush bezpośrednio po zmianie.

> ⚠️ **Zakres pomiaru:** sprawdziłem awarię zadania na jednym hoście (`fail`). Nie sprawdzałem, jak
> `force_handlers` zachowuje się przy `unreachable` hosta ani w połączeniu z `serial`/`any_errors_fatal`.

### 🔗 3. Handler zgłaszający handler — niespodzianka z kolejnością

Handlery mogą mieć własne `notify`. Zdefiniowano je w kolejności: **D, A, B, C**. A zgłasza B (B jest
zdefiniowany *po* A), C zgłasza D (D jest zdefiniowany *przed* C). Zadanie startowe zgłasza A i C.
Prawdziwy output (skrót):

```
RUNNING HANDLER [handler A]
RUNNING HANDLER [handler B]
RUNNING HANDLER [handler C]
RUNNING HANDLER [handler D (zdefiniowany pierwszy, zgłaszany przez C)]
PLAY RECAP: ok=5 changed=3 ...
```

Kolejność jest **A, B, C, D**, a nie według definicji (D, A, B, C). Czyli handler zgłoszony *przez
handler* wykonuje się od razu po zgłaszającym — nawet gdy według definicji powinien być wcześniej.
Zadziałało też w drugim przebiegu (ta sama kolejność). Wniosek z pomiaru, nie z dokumentacji:
zgłoszenia z handlera są obsługiwane „na bieżąco", a tylko zgłoszenia z zadań idą w kolejności definicji.

> 💡 **Dlaczego to ważne:** łańcuchy („restart A → po nim zweryfikuj B") działają, ale reguła z sekcji 1
> przestaje obowiązywać. Zauważ też, że A i C miały `changed_when: true` — handler `debug` domyślnie
> zwraca `ok`, a **zgłasza dalej tylko wtedy, gdy sam coś zmienił**. Prawdziwy handler (np. `service`)
> robi to naturalnie, więc przy `debug` musieliśmy to wymusić.

---

### ✅ Co zweryfikowano, a czego nie

| Zweryfikowane (`ansible-core 2.17.14`) | Niezweryfikowane |
|---|---|
| `--syntax-check` trzech playbooków | `force_handlers` przy `unreachable`, z `serial`, `any_errors_fatal` |
| Kolejność definicji, deduplikacja, `listen` z dwoma słuchaczami (1 przebieg) | Handlery w rolach (`handlers/main.yml`) i `listen` między rolami |
| Awaria: brak handlera / `force_handlers` / `flush_handlers` (po 1 przebiegu) | `notify` w `block`/`rescue`, `--check` z handlerami |
| Handler zgłaszający handler (2 przebiegi, ta sama kolejność) | Prawdziwy `service` + `become`; SSH; vault/galaxy/Molecule (blokady środowiska) |

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wszystkie artykuły: 🔧 Ansible](../README.md) · [spis rubryk](../../../README.md)

</div>
