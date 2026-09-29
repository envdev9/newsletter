<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #6 — 29 września 2026

![AI](https://img.shields.io/badge/AI_%2F_Claude_Code-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Testy](https://img.shields.io/badge/skaner-2%2F2%20(bez%20Node%2FAngular%20CLI)-yellow?style=for-the-badge)

## Skill do Angulara: `effect()` nie jest gorszym `computed()`

</div>

---

> _"`effect()` czytający cztery sygnały i ustawiający piąty to nie reaktywność — to ręcznie
> napisany, niedokumentowany `computed()`, tylko wolniejszy i bez cache'a."_

W wydaniu #4 był skill do SQL. Dziś wracamy do zapowiedzianego w `STATE.md` kroku: **skill
do code-review komponentu Angular, ale konkretny** — nie ogólne "sprawdź komponent" (to było
w wydaniu #1), tylko wąski, sprawdzalny zestaw antywzorców wokół Signals. Kod: [`code/`](code/).

---

## 1️⃣ 🅰️ Dlaczego samo "code review Angulara" to za mało

Signals w Angularze (stabilne od wersji 17, dziś fundament reaktywności) mają prostą
powierzchnię API — `signal()`, `computed()`, `effect()`, `input()` — ale łatwo jej użyć
tak, że kod się kompiluje i *wygląda* na reaktywny, a w praktyce robi coś innego, niż autor
zakładał: liczy się dwa razy za dużo, nie liczy się wcale, albo wpada w pętlę. To są błędy,
których TypeScript nie złapie (typy się zgadzają), a code review "na oko" łatwo przeoczy,
bo kod jest krótki i "wygląda dobrze". Stąd skill z **deterministycznym skanerem** — jak w
skillach z poprzednich wydań, najpierw regex/parsowanie tekstu wyłapuje kandydatów, dopiero
potem model ocenia sens.

## 2️⃣ 🐛 Sześć antywzorców, które skaner wyłapuje

| Reguła | Poziom | Skrót |
|---|---|---|
| `EFFECT-STATE-SYNC` | WARN | `effect()` liczy wartość z sygnałów i `.set()`-uje nią inny sygnał → to `computed()` |
| `EFFECT-SELF-WRITE` | WARN | `effect()` czyta i zapisuje ten sam sygnał w jednym ciele |
| `COMPUTED-SIDE-EFFECT` | WARN | `computed()` wywołuje `.set()`/`.update()` na innym sygnale — nie jest czyste |
| `MUTATING-UPDATE` | WARN | `.update(x => { x.push(...); return x; })` — mutacja w miejscu zamiast nowej referencji |
| `ONPUSH-MISSING` | WARN | komponent używa signals, ale `@Component` nie ma `ChangeDetectionStrategy.OnPush` |
| `UNTRACKED-CANDIDATE` | INFO | `effect()` czyta ≥2 sygnały bez `untracked()` — do sprawdzenia, nie na pewno błąd |

### `effect()` zamiast `computed()` — najczęstszy grzech

```ts
// ŹLE — samples/bad.component.ts
firstName = signal('Jan');
lastName = signal('Kowalski');
fullName = signal('Jan Kowalski');

constructor() {
  effect(() => {
    this.fullName.set(`${this.firstName()} ${this.lastName()}`);
  });
}
```

Problem nie jest kosmetyczny. `effect()` uruchamia się **po** cyklu detekcji zmian, poza
głównym przebiegiem — więc `fullName` przez chwilę ma starą wartość, każdy inny `computed()`
zależny od `fullName` przelicza się dwa razy (raz "za wcześnie", raz po `effect()`), a sam
`effect()` trzeba osobno posprzątać, gdyby komponent wymagał czegoś więcej niż prosty
`OnDestroy`. `computed()` nie ma żadnego z tych problemów — liczy się leniwie, cache'uje
wynik, nie ma efektu ubocznego do posprzątania:

```ts
// DOBRZE — samples/good.component.ts
fullName = computed(() => `${this.firstName()} ${this.lastName()}`);
```

### Mutacja w `.update()` — działa "przez przypadek"

```ts
// ŹLE
this.items.update((list) => {
  list.push({ name, price });
  return list; // ta sama referencja co przed push()
});
```

Domyślna równość sygnału to `===` (referencyjna). Tu `update()` i tak zauważy zmianę, bo
`list` to ten sam obiekt co poprzednia wartość sygnału — `push()` mutuje go w miejscu, więc
"nowa" i "stara" wartość to dosłownie ten sam obiekt w pamięci. To działa tylko dlatego, że
Angular nie porównuje głębokości — porównuje referencję do tego, co `update()` **zwróci**.
Prawdziwy problem: jeśli ktoś gdzie indziej trzyma referencję do starej tablicy (np. w
`computed()` policzonym chwilę wcześniej, w migawce do porównania, w historii undo), zobaczy
push już wykonany, mimo że "nie powinien". Poprawka to zawsze nowa referencja:

```ts
// DOBRZE
this.items.update((list) => [...list, { name, price }]);
```

### `untracked()` — INFO, nie WARN, celowo

```ts
// bad.component.ts — effect czyta 2 sygnały, jeden może nie musieć wyzwalać re-runu
effect(() => {
  console.log(`count=${this.count()}, items=${this.items().length}`);
});
```

Skaner nie wie, czy autor *chciał* reagować na oba sygnały (wtedy kod jest poprawny) czy
tylko na jeden (wtedy drugi odczyt powinien być w `untracked()`, żeby nie wyzwalał
niepotrzebnych przebiegów). Dlatego to jedyna reguła na poziomie `INFO` — sugestia do
sprawdzenia, nie zarzut. `good.component.ts` pokazuje wersję, gdzie `count()` ma wyzwalać
efekt, a `items()` służy tylko do odczytania aktualnej długości w logu:

```ts
effect(() => {
  const c = this.count();
  untracked(() => {
    console.log(`count=${c}, items=${this.items().length}`);
  });
});
```

## 3️⃣ 🔧 Jak działa skaner (i gdzie kłamie)

[`scan_signals.py`](code/claude-skills/angular-signals-review/scan_signals.py) to **regex +
ręczne równoważenie nawiasów**, nie parser TypeScript (dokładnie jak `scan_sql.py` z
wydania #4). Dla każdego wywołania `effect(...)`/`computed(...)`/`.update(...)` znajduje
domykający nawias licząc głębokość znak po znaku (z grubsza omijając stringi), wycina ciało
i szuka w nim odczytów (`nazwa(`) i zapisów (`nazwa.set(`/`nazwa.update(`) znanych sygnałów.

Sygnały rozpoznaje po deklaracji w stylu `nazwa = signal(...)` / `computed(...)` /
`input(...)`, zakotwiczonej na **początku linii** (`^` z `re.MULTILINE`). To nie przypadek —
pierwsza wersja bez tego zakotwiczenia miała realnego, znalezionego testem buga:
nienastawiony na granice linii wzorzec typu adnotacji (`(?::\s*[^=;]+?)?`) potrafił
"przeskoczyć" przez komentarz i całą deklarację klasy aż do pierwszego pasującego `= signal(`
w zupełnie innym miejscu pliku, gubiąc po drodze prawdziwą nazwę sygnału. Objawiało się to
tak: `firstName` znikał z listy sygnałów, a w jego miejsce pojawiała się fałszywa nazwa
wyłowiona z komentarza. Naprawka: `^\s*(?:...)*(\w+)...` z `re.MULTILINE` i wykluczenie
`\n` ze znaków dozwolonych w adnotacji typu. To samo znalazło drugiego, głupszego buga:
komentarz w `bad.component.ts` tłumaczący regułę `ONPUSH-MISSING` zawierał dosłowny tekst
`ChangeDetectionStrategy.OnPush`, więc sprawdzenie `"ChangeDetectionStrategy.OnPush" not in
body` wychodziło fałszywie ujemnie — skaner "widział" frazę we własnym komentarzu-wyjaśnieniu.
Wniosek praktyczny, nie tylko dla tego skryptu: **skaner tekstowy nie odróżnia kodu od
komentarza o tym kodzie** — trzeba na to uważać przy pisaniu przykładów testowych.

### Prawdziwy output (nie wymyślony — wklejony z terminala)

```
$ python3 claude-skills/angular-signals-review/scan_signals.py samples/bad.component.ts
samples/bad.component.ts:6 | WARN | ONPUSH-MISSING | komponent uzywa signal()/computed()/input(), ale @Component nie ma changeDetection: ChangeDetectionStrategy.OnPush - ...
samples/bad.component.ts:35 | WARN | EFFECT-STATE-SYNC | effect() czyta ['firstName', 'lastName'] i ustawia ['fullName'] - to synchronizacja stanu wyliczanego z innych sygnalow, klasyczny przypadek dla computed(), nie effect()
samples/bad.component.ts:35 | INFO | UNTRACKED-CANDIDATE | effect() czyta 2 sygnaly (['firstName', 'lastName']) bez untracked() - ...
samples/bad.component.ts:43 | WARN | EFFECT-SELF-WRITE | effect() odczytuje i w tym samym ciele zapisuje ten sam sygnal (['count']) - ryzyko petli ...
samples/bad.component.ts:53 | INFO | UNTRACKED-CANDIDATE | effect() czyta 2 sygnaly (['count', 'items']) bez untracked() - ...
samples/bad.component.ts:60 | WARN | COMPUTED-SIDE-EFFECT | computed() wywoluje total.set()/update() - computed() ma byc CZYSTA funkcja odczytu ...
samples/bad.component.ts:72 | WARN | MUTATING-UPDATE | .update() mutuje parametr 'list' w miejscu (push) zamiast zwrocic nowy obiekt/tablice ...
```

(pełne, nieskrócone opisy w [`code/README.md`](code/README.md)). Na `good.component.ts`:

```
$ python3 claude-skills/angular-signals-review/scan_signals.py samples/good.component.ts
samples/good.component.ts | brak uwag
```

`run_tests.py` porównuje zbiór reguł, jakie skaner faktycznie zwrócił, z zestawem
oczekiwanym per plik:

```
$ python3 run_tests.py
OK    bad.component.ts     reguly: COMPUTED-SIDE-EFFECT, EFFECT-SELF-WRITE, EFFECT-STATE-SYNC, MUTATING-UPDATE, ONPUSH-MISSING, UNTRACKED-CANDIDATE
OK    good.component.ts    reguly: -

WYNIK: 2/2 przypadkow zgodnych
```

## 4️⃣ 📋 Skill: jak model ma z tego korzystać

[`SKILL.md`](code/claude-skills/angular-signals-review/SKILL.md) ma frontmatter z
`description`, po którym Claude Code miałby sam dobrać skill przy pracy nad plikiem `.ts` z
`effect()`/`computed()`, oraz `allowed-tools` zawężone do `Read`/`Glob`/`Grep` i **jednego**
skryptu. Krok 2 (ocena kontekstowa) uczy m.in. nie ufać `EFFECT-STATE-SYNC` w ciemno — jeśli
`effect()` robi coś więcej niż tylko liczy wartość (np. woła API), skaner i tak go oflaguje,
ale poprawką nie zawsze jest zamiana 1:1 na `computed()`, tylko rozdzielenie na `computed()`
+ osobny, węższy `effect()`.

### 💬 Przykładowe użycie (do skopiowania)

```text
Zrób review pod kątem Signals: @src/app/cart/cart.component.ts
Użyj skilla angular-signals-review.
```

---

## 📎 Co zweryfikowano, a czego nie

| ✅ Uruchomione naprawdę | ⚠️ Niezweryfikowane |
|---|---|
| `run_tests.py` 2/2: `scan_signals.py` na `bad.component.ts` (6 reguł) i `good.component.ts` (cisza) | **Node.js / Angular CLI / `tsc`** — brak w środowisku, pliki `.ts` nie zostały skompilowane ani zlintowane przez prawdziwy toolchain |
| Dwa realne bugi znalezione i naprawione w trakcie pisania (patrz sekcja 3) | Auto-aktywacja skilla po `description`/`allowed-tools` w żywej sesji Claude Code |
| Ręczna inspekcja outputu — wszystkie 6 reguł trafia dokładnie w te linie, których dotyczą | Fałszywe alarmy/przeoczenia regexu na kodzie z destrukturyzacją, aliasami importów (`effect as fx`) albo logiką rozbitą na wiele metod |

Środowisko: Python 3.10.4 (tylko stdlib), bez Node/npm/Angular CLI. Następny krok w
rubryce: skill SQL na prawdziwym planie z `sqlcmd` (jeśli środowisko na to pozwoli) albo
kolejny, głębszy przypadek Angulara/`.NET` do code-review.

---

<div align="center">

[← wróć do wydania #6 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
