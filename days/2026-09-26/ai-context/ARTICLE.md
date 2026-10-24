<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #2 rubryki — 26 września 2026

![AI/Kontekst](https://img.shields.io/badge/AI_%2F_Kontekst-8A5CF6?style=for-the-badge&logo=anthropic&logoColor=white)

## Kompaktowanie, łańcuchy subagentów i budżet kontekstu: jak przeżyć sesję na 60 tur

</div>

---

> _"Wynik narzędzia nie kosztuje tyle, ile waży. Kosztuje tyle, ile waży, razy liczba
> tur, przez które go dźwigasz."_

W [wydaniu #1](../../2026-09-24/ai-context/ARTICLE.md) ustaliliśmy, **co** wchodzi do
okna kontekstu i dlaczego kolejność warstw ma znaczenie. Dziś kolejny krok: co robić, gdy
sesja robi się długa. Trzy tematy: `/compact` (co przeżywa, co ginie), łańcuchy subagentów
i budżetowanie. Pod spodem jest narzędzie, które można uruchomić od razu - i jedna
uczciwa uwaga na starcie:

> ⚠️ **Dane są syntetyczne.** Chciałem zmierzyć prawdziwy transkrypt z
> `~/.claude/projects/`, ale odczyt tego katalogu w środowisku, w którym powstawało to
> wydanie, został odrzucony przez system uprawnień - i nie próbowałem tego obchodzić.
> Wszystkie liczby poniżej pochodzą więc z **syntetycznego** transkryptu (deterministyczny
> generator, seed=7), którego rozkład rozmiarów wyników sam dobrałem (ciężki ogon).
> **Realne i sprawdzone jest:** arytmetyka, kod i jego zachowanie (uruchomiony, plus test
> 6/6). **Nieudowodnione:** że twoja sesja ma dokładnie takie proporcje. Analizator
> działa na każdym pliku `.jsonl` o opisanym kształcie - odpal go u siebie, tylko
> na własnych danych.

---

## 1️⃣ Metryka, której brakowało: „token-tury"

Model nie ma pamięci między turami (wydanie #1). Każda tura **ponownie czyta cały
dotychczasowy kontekst**. Skoro tak, plik, który wczytałeś w turze 3 i który waży 14 000
tokenów, jest czytany w turze 4, 5, 6... aż do końca sesji albo do kompaktowania.

Stąd prosty model kosztu, którego używa analizator:

```
koszt wyniku  =  ~tokeny wyniku  x  liczba tur po nim
koszt sesji   =  suma po turach z (rozmiar kontekstu w tej turze)     # "token-tury"
```

Cache promptów (wydanie #1) obniża **cenę** takiego odczytu, ale go nie zeruje - a poza
kosztem jest jeszcze okno: gdy suma dobija do limitu, sesja się kończy albo trzeba
kompaktować. **Hak: pojedyncze wielkie `Read` z 3. tury sesji jest droższe niż dziesięć
małych z końcowych tur, nawet jeśli ważą tyle samo.** Wczesne, duże wyniki to najdroższy
kontekst, jaki masz.

---

## 2️⃣ Kto pożera kontekst: wynik z realnego uruchomienia

Syntetyczna sesja: 60 tur, 5 narzędzi (`Read`, `Grep`, `Bash`, `Edit`, `Task`), wyniki
narzędzi to 98,5% bajtów całego transkryptu (rozkład zadany przeze mnie, ale sam fakt, że
w sesjach agentowych dominują wyniki narzędzi, a nie rozmowa, to ta sama obserwacja, co
w wydaniu #1). Prawdziwy output `analyze_transcript.py`:

| narzędzie | wywołań | ~tokenów | udział | największy wynik (~tok.) |
|---|---:|---:|---:|---:|
| `Bash` | 16 | 72 315 | 51,4% | 13 840 |
| `Read` | 14 | 61 896 | 44,0% | 14 137 |
| `Grep` | 14 | 5 036 | 3,6% | 1 110 |
| `Task` (subagent) | 6 | 1 121 | 0,8% | 257 |
| `Edit` | 10 | 225 | 0,2% | 41 |

Ranking „pożeraczy" wg token-tur zmienia obraz: **5 wyników z 60 (8%) odpowiada za 67,3%
całego dźwigania.** Największy to `Read` na ~14 100 tokenów, który przeżył 58 tur (819 946
token-tur). Zwróć uwagę na dwa fakty: `Task` - czyli subagent - ma w tabeli **najmniejszy
średni wynik**, bo do głównego kontekstu wraca sam raport; i `Edit` prawie nic nie waży.
Kosztowne są **czytanie i uruchamianie**, nie pisanie.

---

## 3️⃣ Kompaktowanie (`/compact`): co przeżywa, co ginie

Kompaktowanie zastępuje długą historię krótkim streszczeniem. To zamiana **stratna** -
streszczenie jest napisane przez model i nie zawiera wszystkiego. Co wiemy pewnie, a co
nie:

| Element | Los po kompaktowaniu | Pewność |
|---|---|---|
| Stały prefiks (system prompt, schematy narzędzi) | zostaje - nie jest częścią „historii" | wynika z architektury z wydania #1 |
| Treść pliku `Read` sprzed 40 tur | ginie w dosłownej postaci; zostaje ewentualnie wzmianka w streszczeniu | wynika z definicji streszczenia |
| Decyzje, ograniczenia z rozmowy | przeżyją **tylko jeśli streszczenie je uchwyci** | mechanizm pewny, jakość zależy od streszczenia |
| Twoja instrukcja z 5. wiadomości („nie ruszaj `Legacy/`") | może zginąć - dlatego trwałe reguły należą do `CLAUDE.md` | rada wynikająca z powyższego |
| `CLAUDE.md` po kompaktowaniu | wg mojej wiedzy jest wczytywany z dysku od nowa - **nie sprawdziłem tego w żywej sesji** | niezweryfikowane |

### Jak sterować

1. **Kompaktuj sam, na granicy zadań, a nie czekaj na automat.** Automatyczny compact
   odpala się, gdy okno jest prawie pełne - czyli w najgorszym możliwym momencie, w
   środku zadania, gdy streszczenie ma najtrudniej wybrać, co ważne.
2. **Dawaj instrukcję do streszczenia.** `/compact` przyjmuje dodatkowy tekst, np.
   `/compact zachowaj: listę zmienionych plików, nieprzechodzące testy, decyzję o
   wyborze Dapper zamiast EF`. Składnię znam z dokumentacji klienta, ale w tym wydaniu
   **nie odpaliłem jej w żywej sesji** (CLI nie było dostępne) - sprawdź `/help`.
3. **Zapisz stan na dysk zanim skompaktujesz** - to robi hook `PreCompact` +
   `SessionStart` z rubryki ⚙️
   [agentic loop](../ai-agentic-loop/ARTICLE.md). Plik `TASKS.md` przeżyje każde
   streszczenie, bo nie jest w oknie.
4. **Gdy zadanie jest skończone i kolejne niepowiązane - `/clear`**, nie `/compact`.
   Streszczenie nieaktualnej pracy to kontekst, za który płacisz i który wprowadza
   szum.

**Hak:** kompaktowanie to nie „zwolnienie miejsca", tylko **decyzja, co zapomnisz**.
Lepiej podjąć ją świadomie.

### Ile daje kompaktowanie - liczby

Analizator symuluje automatyczny compact po przekroczeniu 80% okna (tu: okno 100 000
tok., streszczenie 4 000 tok.). Wynik z uruchomienia, na tej samej sesji:

| wariant | szczyt kontekstu (~tok.) | token-tury | compactów |
|---|---:|---:|---:|
| bez zmian | 160 718 (**nie mieści się w oknie 100k**) | 5 405 134 | 0 |
| auto-compact przy 80% | 82 050 | 2 506 436 | 2 |
| delegacja wyników > 3000 tok. | 38 357 | 1 538 332 | 0 |
| delegacja + auto-compact | 38 357 | 1 538 332 | 0 |

Uwaga na ograniczenia symulacji: streszczenie ma **stały** rozmiar i model nie „gubi"
niczego - a w rzeczywistości gubi. Symulacja pokazuje koszt, nie jakość. Wiersz
„bez zmian" przekracza okno, więc jest hipotetyczny (prawdziwa sesja zostałaby wcześniej
skompaktowana lub przerwana).

---

## 4️⃣ Łańcuchy subagentów: kompaktowanie, którego nie musisz robić

Wiersz „delegacja" pokazuje, dlaczego subagenci są lepsi niż kompaktowanie: **nie tracisz
niczego, bo nic nie wpuściłeś**. Wielki wynik (14 000 tok.) powstaje w kontekście
subagenta, a do głównej rozmowy wraca raport na ~150 tokenów. Efekt w symulacji:
szczyt 4,2x niższy (160 718 -> 38 357), token-tury 3,5x niższe (5,41 mln -> 1,54 mln).

Uwaga na uczciwość: **delegacja nie jest darmowa.** Subagent zużywa własne tokeny
(policzone gdzie indziej niż w głównym transkrypcie), a symulacja zakłada idealny raport
150 tok. Wygrywasz kontekst główny i jego jakość, niekoniecznie łączny rachunek.

### Jak zbudować łańcuch dużego zadania

Przykład: „zmigruj 40 kontrolerów z ręcznej walidacji na FluentValidation". W jednym
kontekście to katastrofa (40 plików x 3-10 tys. tok. dźwiganych do końca). Łańcuch:

```
[główny agent: orkiestrator]  -- trzyma tylko: plan, wskaźniki do plików, statusy
   |
   |-- etap 1  subagent "inwentaryzacja": przeszukaj repo, zapisz  work/01-inventory.md
   |             zwróć: "40 kontrolerów, lista w work/01-inventory.md" (1 linia)
   |-- etap 2  subagent x N (równolegle, niezależne pliki): migruje po 1 kontrolerze,
   |             zwróć: "OrdersController: OK, testy zielone" albo "BŁĄD: <1 zdanie>"
   |-- etap 3  subagent "weryfikacja": build + testy, zapisz  work/03-verify.md,
   |             zwróć tylko liczby (przeszło/nie przeszło)
```

Zasady, które robią różnicę:

1. **Przekazuj wskaźniki, nie zawartość.** Między etapami przekazuj ścieżkę do pliku na
   dysku (`work/01-inventory.md`), a nie jego treść. Orkiestrator trzyma wskaźnik za
   kilka tokenów; następny etap sam sobie plik wczyta.
2. **Kontrakt na wyjściu.** W prompcie zlecenia napisz **jaki rozmiar i format** ma raport
   („maksymalnie 5 linii; pierwsza linia: OK albo BŁĄD"). Bez tego subagent zwróci esej i
   cała korzyść znika - to jest wąskie gardło łańcucha.
3. **Zlecenie samowystarczalne.** Subagent nie widzi twojej rozmowy (wydanie #1) - podaj
   cel, ścieżki, kryterium ukończenia.
4. **Równolegle tylko rzeczy niezależne** (różne pliki). Zależne etapy - sekwencyjnie.
5. **Weryfikacja jest osobnym etapem** z obiektywnym kryterium (exit code testów), nie
   deklaracją subagenta „zrobione".

Nie zweryfikowałem w tym wydaniu żywego uruchomienia łańcucha subagentów (CLI
niedostępne) - powyższe to projekt oparty na mechanizmie z wydania #1 i na mierzalnym
efekcie delegacji z symulacji.

---

## 5️⃣ Budżetowanie kontekstu w długiej sesji

Praktyczna checklista - traktuj okno jak budżet z pozycjami:

| Pozycja | Rozsądna polityka |
|---|---|
| Stała baza (system, narzędzia, `CLAUDE.md`) | Płacisz w każdej turze. Odchudzaj `CLAUDE.md` i wyłączaj nieużywane serwery MCP. |
| Wyniki > ~3 000 tok. | Zapytaj: czy ja to muszę widzieć? Jeśli nie - `grep`/`head`/`offset+limit` (wydanie #1) albo subagent. |
| Wczesne duże wczytania | Najdroższe (sekcja 1). Zanim wczytasz plik na 14 tys. tok., ustal, po co. |
| Próg reakcji | Nie czekaj na automat: ustaw własny nawyk, np. przy ~60% okna dokończ zadanie i kompaktuj/czyść. |
| Granica zadania | `/clear` lub `/compact` z instrukcją + stan w pliku na dysku. |

Jak sprawdzić, na czym stoisz: przy własnych transkryptach użyj
`analyze_transcript.py` (kolumna „token-tur" wskazuje, które konkretne wyniki
wyeliminować), a w kliencie sprawdź `/help` pod kątem komendy pokazującej rozkład
kontekstu (jej nazwy i formatu **nie weryfikowałem** - zmienia się między wersjami).

---

## 📎 Jak uruchomić kod z tego wydania

[`code/README.md`](code/README.md) - trzy komendy, pełny prawdziwy output. Wymaga tylko
`python3`.

---

<div align="center">

[← wydanie z 26 września (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
