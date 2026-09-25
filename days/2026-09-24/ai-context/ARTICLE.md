<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #1 — 24 września 2026

![AI/Claude Code](https://img.shields.io/badge/AI_%2F_Claude_Code-D97757?style=for-the-badge&logo=anthropic&logoColor=white)

## Okno kontekstu: z czego się składa, w jakiej kolejności i jak nim gospodarować

</div>

---

> _"Kontekst to nie 'pamięć' modelu - to CAŁA wiedza, jaką model ma o świecie w danym
> momencie. Model między turami niczego nie pamięta; to, co nie jest w oknie kontekstu,
> dla niego po prostu nie istnieje."_

To wydanie ma jeden cel: żebyś po jego przeczytaniu **przestał zgadywać**, co trafia do
kontekstu Claude Code i w jakiej kolejności, i zaczął to świadomie kontrolować. Nie
ciekawostka - realne umiejętności: jak czytać skład kontekstu, jak dzielić robotę na
subagentów, żeby nie zaśmiecać głównej rozmowy, i co dokładnie podawać modelowi "do
ręki". Wszystkie liczby w tym wydaniu pochodzą z realnie uruchomionego skryptu, nie z
szacunków na oko.

---

## 1️⃣ Z czego składa się okno kontekstu i w jakiej kolejności się ładuje

Przy każdym zapytaniu do modelu, Claude Code buduje kontekst w ustalonej kolejności
warstw. Od najbardziej stabilnej (rzadko się zmienia) do najbardziej ulotnej (zmienia
się co turę):

1. **System prompt** - definicja tego, czym jest Claude Code, jak ma się zachowywać,
   plus **pełne schematy JSON wszystkich dostępnych narzędzi** (nazwa, opis, parametry).
   To jest zaskakująco duża część kontekstu, o której się zapomina - każde narzędzie,
   każdy MCP server, każdy zarejestrowany subagent dopisuje swój opis tutaj, **zanim**
   jakikolwiek user w ogóle coś napisze.
2. **Pamięć projektu / `CLAUDE.md`** - instrukcje repo (konwencje, "nie rób X") plus,
   jeśli klient to wspiera, pamięć użytkownika między sesjami. Ładowane raz, wcześnie,
   bo rzadko się zmienia w trakcie jednej rozmowy.
3. **Historia rozmowy** - naprzemiennie wiadomości usera i asystenta, w ścisłej
   kolejności chronologicznej. Wywołania narzędzi (`tool_use`) i ich wyniki
   (`tool_result`) siedzą **dokładnie tam, gdzie faktycznie wystąpiły** w rozmowie - plik
   wczytany przez `Read` w 3. turze zostaje w kontekście jako `tool_result` w miejscu 3.
   tury, nie na końcu. To ważne: model "widzi" plik w kontekście historycznym tego
   momentu, kiedy go wczytał, nie jako osobną, świeżą sekcję.
4. **Dynamicznie wstrzykiwane przypomnienia** (`system-reminder`) - harness potrafi
   dopisać coś do kontekstu **w trakcie** rozmowy, nie tylko na starcie: zmieniona lista
   narzędzi, zaktualizowana pamięć, ostrzeżenie o czymś. To nie jest część "historii" w
   sensie tego, co ktokolwiek napisał - to harness rozmawiający sam ze sobą przez kanał
   widoczny modelowi.
5. **Bieżąca tura** - to, co user właśnie napisał, plus wszystko, co model już zdążył
   zrobić w tej turze (wcześniejsze wywołania narzędzi tej samej tury).

**To nie jest teoria - to dosłownie to, co widać w tej rozmowie.** Ta sesja, w której
powstaje ten artykuł, ma w swoim kontekście realny `<system-reminder>` z zawartością
`MEMORY.md` (pamięć projektowa), osobny `<system-reminder>` z listą "deferred tools"
(narzędzia, których schemat jeszcze się nie załadował - patrz niżej), listę dostępnych
typów subagentów i instrukcje serwerów MCP. Wszystko to zostało wstrzyknięte **przed**
treścią zlecenia, dokładnie w kolejności: system → narzędzia/MCP → przypomnienia →
zlecenie. Jeśli chcesz zobaczyć tę strukturę u siebie z pierwszej ręki - poproś Claude
Code, żeby pokazał ci treść najnowszego pliku `.jsonl` z `~/.claude/projects/<projekt>/`
(patrz sekcja 2).

### Dlaczego kolejność ma znaczenie ekonomicznie, nie tylko poznawczo

Claude Code korzysta z **cache'owania promptów** (prompt caching) - stabilny prefiks
kontekstu (system prompt + narzędzia + pamięć projektu) może zostać zapisany w cache'u
providera i przy kolejnym zapytaniu **nie trzeba go przetwarzać od nowa**, tylko
odczytać z cache'u (znacznie taniej i szybciej niż pełne przetworzenie). To działa tylko
wtedy, gdy prefiks kontekstu jest **identyczny** między zapytaniami - stąd stała
kolejność: rzeczy stabilne (system, narzędzia, pamięć) na początku, rzeczy zmienne
(historia, bieżąca tura) na końcu. Gdybyś co turę przestawiał kolejność albo wstrzykiwał
coś zmiennego na początek, unieważniałbyś cache przy każdym zapytaniu - drożej i wolniej,
nie tylko "bałaganiarsko".

---

## 2️⃣ Jak analizować zużycie kontekstu

### Transkrypt sesji na dysku

Każda sesja Claude Code zapisuje pełny transkrypt jako plik `.jsonl` pod
`~/.claude/projects/<zakodowana-ścieżka-projektu>/<session-id>.jsonl` - jedna linia = jeden
zapis zdarzenia (wiadomość, wywołanie narzędzia, wynik). Transkrypty **subagentów** leżą
osobno, w podkatalogu `<session-id>/subagents/*.jsonl` tej samej sesji - co samo w sobie
jest namacalnym dowodem na to, o czym mówimy w rubryce ⚙️
[AI - agentic loop](../ai-agentic-loop/ARTICLE.md): subagent ma **fizycznie osobny**
zapis kontekstu, nie dopisuje się do głównego pliku.

Każdy zapis typu `assistant` niesie pole `usage` z rozbiciem tokenów zapytania:

- `input_tokens` - tokeny wejściowe, które **nie** trafiły w cache (płacisz pełną cenę),
- `cache_creation_input_tokens` - tokeny, które właśnie zapisano do cache'u,
- `cache_read_input_tokens` - tokeny odczytane z cache'u (znacznie tańsze),
- `output_tokens` - to, co model wygenerował.

Zgrubna analiza jednej sesji bez żadnych dodatkowych narzędzi:

```bash
wc -l ~/.claude/projects/*/twoja-sesja.jsonl     # ile "zdarzeń" w sesji
wc -c ~/.claude/projects/*/twoja-sesja.jsonl     # surowy rozmiar pliku w bajtach
grep -c '"type":"tool_use"' twoja-sesja.jsonl    # ile wywołań narzędzi
grep -c '"type":"tool_result"' twoja-sesja.jsonl # ile wyników wróciło do kontekstu
```

To, w połączeniu z sumowaniem pól `usage.*` (np. przez `python3 -c` albo `jq`, jeśli
masz), daje pełny obraz: ile z tego, co "kosztuje", to w ogóle nowy content, a ile to
tanie odczyty z cache'u. Jeśli twój klient CLI ma wbudowaną komendę pokazującą rozkład
zużycia kontekstu (część wersji Claude Code CLI ją ma) - to jest szybsza ścieżka do tego
samego wniosku; traktuj to jako punkt startowy, bo dokładna nazwa/format komendy zmienia
się między wersjami, więc nie polegaj tu na pamięci - sprawdź `/help` w swoim kliencie.

### Zgrubna heurystyka bez transkryptu

Zanim jeszcze cokolwiek wczytasz modelowi, warto wiedzieć w przybliżeniu, ile to "zje".
Reguła kciuka dla angielskiego/kodu: **~4 znaki ≈ 1 token** (dla tekstu w innych
alfabetach, np. mocno nacechowanego polskimi znakami, ten współczynnik bywa gorszy - nie
traktuj tego jako dokładnej wartości, tylko jako rząd wielkości). Konkretny, uruchomiony
przykład tej heurystyki - patrz sekcja 4 i [`code/`](code/).

---

## 3️⃣ Kiedy delegować do subagenta, a kiedy nie

Subagent dostaje **świeży, pusty kontekst** - widzi tylko to, co wpiszesz w jego prompt
zlecenia, nic z historii głównej rozmowy. Robi swoją robotę własną, zagnieżdżoną pętlą
tool-use (patrz rubryka ⚙️), i **zwraca do głównego kontekstu tylko finalny raport
tekstowy** - wszystkie pośrednie kroki (nieudane próby, eksploracja, ślepe uliczki)
zostają w jego własnym, osobnym transkrypcie i nigdy nie obciążają głównej rozmowy.

### Warto delegować, gdy:

- **Eksploracja jest hałaśliwa, a wniosek mały.** "Znajdź, gdzie w repo obsługiwane jest
  wysyłanie e-maili" może kosztować dwadzieścia `Grep`/`Read` po drodze - w głównym
  kontekście zostałyby wszystkie próby, w subagentowym zostaje jedna odpowiedź: "logika
  jest w `EmailService.cs:42`".
- **Zadanie jest niezależne od reszty rozmowy.** Nie wymaga dopytywania usera w trakcie,
  nie potrzebuje subtelnego kontekstu z wcześniejszych 50 wiadomości.
- **Wynik pośredni jest z natury duży, ale finalny jest mały.** Analiza logów builda,
  przegląd wielu plików pod kątem jednej rzeczy, przeszukanie dokumentacji.
- **Chcesz uruchomić coś równolegle w tle** i wrócić do tego później, nie blokując
  głównej rozmowy.

### NIE warto delegować, gdy:

- **Zadanie jest już małe/tanie.** Odpalenie subagenta ma swój koszt startowy (musi
  dostać w prompcie cały potrzebny kontekst od zera, bo nic nie "dziedziczy"
  automatycznie z rozmowy) - dla jednowierszowej poprawki to czysta strata.
  „Nie deleguj, jeśli cel jest już znany” — jeśli wiesz dokładnie, który plik i którą
  linię zmienić, subagent tylko dokłada rundę komunikacji, a niczego nie odkrywa.
- **Zadanie wymaga iteracyjnego uzgadniania z userem w trakcie.** Subagent nie może
  zapytać usera o zdanie w połowie roboty - dostaje zlecenie i wraca z gotowym wynikiem,
  koniec.
- **Zadanie mocno zależy od niuansu już ustalonego w rozmowie.** Jeśli musiałbyś w
  prompt zlecenia przepisać pół dotychczasowej dyskusji, żeby subagent w ogóle zrozumiał
  zadanie - koszt "wytłumaczenia" może przewyższyć zysk z izolacji.
- **Potrzebujesz wglądu na bieżąco, krok po kroku**, a nie tylko końcowego raportu -
  subagent w trybie tła nie strumieniuje pośrednich kroków do głównej rozmowy.

---

## 4️⃣ Co dawać modelowi "do ręki", a czego unikać

Zasada ogólna: **kontekst to zasób, nie śmietnik**. Każdy znak, który tam wjeżdża,
zostaje tam do końca rozmowy (albo do kompaktowania) i model musi go "przeczytać" przy
każdej kolejnej turze.

**Dawaj:**
- Dokładne ścieżki plików + zakresy linii (`Read` z `offset`/`limit`), zamiast całego
  pliku, gdy interesuje cię jeden fragment.
- `grep -n` z odrobiną kontekstu (`-A`/`-B`/`-C`) zamiast pełnego pliku, gdy szukasz
  konkretnego wzorca.
- `head -n`/`tail -n` na dużych plikach/logach, gdy potrzebny jest tylko fragment - **ale
  uważaj**, bo jeśli sygnał jest głęboko w pliku, `head` go w ogóle nie zobaczy (patrz
  demo w sekcji 5 - to nie jest oczywiste na pierwszy rzut oka).
- Skondensowane, ustrukturyzowane dane (np. `git diff --stat` zamiast pełnego diffa, gdy
  interesuje cię tylko które pliki się zmieniły) zamiast surowych zrzutów.
- Sam kod wyjścia / status ("build succeeded", "3 testy nie przeszły: A, B, C") zamiast
  całego stdout, gdy liczy się tylko wynik.

**Unikaj:**
- Pełnego `cat` dużego pliku/logu, kiedy potrzebny jest tylko fragment - zobacz w sekcji
  5, o ile rzędów wielkości to przepłacasz.
- Surowych logów CI/buildów w całości - zwykle 99% to szum ("Restoring packages...",
  "Test X PASSED"), a sygnał to kilka linii.
- Wyjścia z flagą `--debug`/`--verbose`, jeśli nie debugujesz akurat tego narzędzia.
- Dużych binariów/obrazów, które nie są bezpośrednio potrzebne do zadania.
- Nieprzefiltrowanego drzewa katalogów (`find .` / `ls -R` na całym repo) zamiast
  konkretnego `find` z filtrem albo `Glob` z sensownym wzorcem.

---

## 5️⃣ Działający przykład: ile realnie kosztuje `cat` vs `grep`/`head`

W [`code/`](code/) jest samodzielny, uruchamialny przykład: generator syntetycznego logu
builda CI (4000+ linii szumu + 3 linie prawdziwego sygnału ukryte w środku pliku) plus
skrypt szacujący przybliżoną liczbę tokenów tekstu podanego na `stdin`.

Realny, uruchomiony wynik (pełne komendy w [`code/README.md`](code/README.md)):

| Metoda | Linii | Znaków | ~Tokenów |
|---|---:|---:|---:|
| `cat build.log` (cały plik) | 4003 | 206 086 | ~51 522 |
| `head -n 50 build.log` | 50 | 2 570 | ~642 (**i zero sygnału** - błędy są głębiej) |
| `grep -E 'error \|FAILED' build.log` | 3 | 333 | ~83 |

**`grep` zużył 619× mniej kontekstu niż `cat` całego pliku - i to `grep`, nie `head`,
faktycznie znalazł sygnał.** To jest cała lekcja tej sekcji w jednej liczbie: intuicyjny
odruch "wezmę pierwsze N linii, żeby nie przesadzić" bywa gorszy niż wzięcie całego
pliku, bo nie trafia w to, co ważne - **filtrowanie pod kątem treści** (`grep`), nie
**pozycji** (`head`), jest właściwym narzędziem do ograniczania kontekstu bez utraty
sygnału.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — dokładne komendy i pełny, prawdziwy output.

---

<div align="center">

[← wróć do wydania #1 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
