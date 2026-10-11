<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #18 — 11 października 2026

![AI/Agentic loop](https://img.shields.io/badge/AI_%2F_Agentic_loop-5A67D8?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10.4-3776AB?style=for-the-badge&logo=python&logoColor=white)
![git](https://img.shields.io/badge/git-2.34.1-F05032?style=for-the-badge&logo=git&logoColor=white)
![Testy](https://img.shields.io/badge/testy_lokalne-22%2F22-brightgreen?style=for-the-badge)
![Claude CLI](https://img.shields.io/badge/claude%20CLI-niezweryfikowane-lightgrey?style=for-the-badge)

## Gdy hash drzewa liczy git, a archiwum dziennika składa się z powrotem w jedną oś czasu

</div>

---

> _"Skrót, który sam wymyśliłeś, trzeba utrzymywać. Skrót, który policzył git, wszyscy już rozumieją
> — łącznie z jego dziurami."_

W #17 zostały trzy rzeczy na liście „następne". Dwie da się uczciwie zrobić dziś: (1) **`git write-tree`
jako hash drzewa** zamiast własnego `os.walk` + SHA-256 oraz (2) **złożenie segmentów archiwum w jedną
oś zdarzeń**. Trzecia — `permissionMode` w frontmatterze agenta i hooki headless — wciąż czeka:
`claude --version` jest w tym środowisku odrzucane przez uprawnienia (próbowałem dziś jeszcze raz,
odrzucone), więc o tych polach nie piszę nic z pamięci. Kod: [`code/`](code/).

> ⚠️ **Uczciwie na starcie:** rolę modelu gra **deterministyczna funkcja Pythona** (`policy(historia)`).
> To nie jest LLM ani Claude Code. Realne i uruchomione są: **nadzorca** z #14–#17, **prawdziwy `git`
> 2.34.1** (osobny `GIT_DIR`, prawdziwe `add -A`/`write-tree`), prawdziwe pliki i pliki dziennika na
> dysku. „Testy" w świecie testowym to funkcja sprawdzająca, czy w `Foo.cs` jest słowo `fixed`, nie
> `dotnet test`. Python 3.10.4, `python3 -B code/run_tests.py` → **22 testy OK**.

---

## 1️⃣ 🌲 Hash drzewa z gita — co dostajemy za darmo, a za co płacimy

### Mechanizm

`git write-tree` zamienia **indeks** na obiekt drzewa i drukuje jego SHA-1. Drzewo to rekurencyjna lista
`(tryb, nazwa, hash)`; hash bloba zależy wyłącznie od bajtów pliku. Z tego wynika wszystko, co nas
interesuje: **`mtime` nie istnieje w modelu** (jak w naszym `tree_hash`), ale **tryb pliku — istnieje**.

`GitTreeObserver` składa to tak:

1. `git init --bare` w katalogu tymczasowym (`GIT_DIR`) — **nie dotykamy repo użytkownika**, jego indeksu
   ani bazy obiektów;
2. `GIT_WORK_TREE=<root>` — katalog roboczy agenta;
3. `info/exclude` tego tymczasowego `GIT_DIR` dostaje `bin/ obj/ node_modules/ __pycache__/` (odpowiednik
   stałej listy `ignore`); `.gitignore` z drzewa jest respektowany przez samego gita;
4. `git add -A -- .` + `git write-tree`; opcje `core.autocrlf=false`, `GIT_CONFIG_GLOBAL=/dev/null`,
   `GIT_CONFIG_NOSYSTEM=1` — wynik ma zależeć od treści, nie od ustawień konta, na którym biegnie agent.

Obiekt `GitTreeObserver` jest `callable() -> str`, więc wpina się w `Supervisor(observer=...)` bez żadnej
zmiany w nadzorcy. Test `test_matches_real_git_for_same_content` sprawdza, że hash jest **identyczny**
z tym, który dostaniemy w zwykłym repo przez `git init && git add -A && git write-tree`.

### Co się zmienia, a co nie — realny output

```
== 1. co jest zmiana: tree_hash (python, stala lista ignore) vs git write-tree
  git tree (pierwsze 12 znakow): 6e77d8635ec7  dlugosc hasha: python 64 / git 40 hex
  zapis do obj/                        python: taki sam  git: taki sam
  zmiana mtime                         python: taki sam  git: taki sam
  pusty katalog                        python: taki sam  git: taki sam
  chmod +x (bez zmiany tresci)         python: taki sam  git: ZMIENIONY
  chmod z powrotem 644                 python: taki sam  git: taki sam
  nowy plik build.log                  python: ZMIENIONY git: ZMIENIONY
  dopisano .gitignore z build.log, potem kolejna zmiana logu:
    trwaly indeks (plik juz sledzony)  : git ZMIENIONY   <- pulapka
    python tree_hash                   : ZMIENIONY
    swiezy indeks za kazdym razem      : git taki sam
```

| Zachowanie | Własny `tree_hash` (#17) | `git write-tree` |
|---|---|---|
| `mtime`, pusty katalog, `obj/`, `bin/` | ignoruje | ignoruje |
| `chmod +x` bez zmiany treści | **nie widzi** | **widzi** (tryb jest w drzewie) |
| `.gitignore` projektu | nie zna | respektuje |
| zagnieżdżone repo (submoduł, vendor) | hashuje zawartość plików | **ślepy punkt** (patrz niżej) |
| rozmiar hasha | 64 hex (SHA-256) | 40 hex (SHA-1) |

> 💡 **Haczyk 1 — `.gitignore` nie wyrzuca plików już śledzonych.** Nasz obserwator ma **trwały
> indeks** (inaczej każde wywołanie hashowałoby od zera). Plik `build.log`, który raz trafił do indeksu,
> a dopiero potem do `.gitignore`, **dalej wchodzi do hasha** — dokładnie jak w zwykłym repo (`git rm
> --cached` jest potrzebne). Test `test_gitignore_vs_persistent_index` to dokumentuje; w trybie
> „świeży indeks za każdym razem" ten sam plik jest ignorowany. Rada: reguły ignorowania ustawiać
> **przed pierwszym wywołaniem**, albo płacić świeżym indeksem.

> 💡 **Haczyk 2 — zagnieżdżone repo to ślepy punkt.** Git zapisuje taki katalog jako *gitlink* (hash
> jego commita), nie treść plików:
>
> ```
> == 2. pulapka: zagniezdzone repo (submodul/vendored clone) w drzewie
>   zmiana pliku w zagniezdzonym repo (niezacommitowana): git taki sam, python ZMIENIONY
> ```
>
> Agent, który edytuje kod w `vendor/lib` (własne `.git`), nie zmieni hasha — a `TREE_STALL` strzeli
> mimo pracy. Własny `os.walk` tego nie ma, ale też nie respektuje `.gitignore`. To jest decyzja
> projektowa, nie „lepsza/gorsza" opcja: wybierasz, **czyje reguły** definiują „zmianę".

### Czy to w ogóle szybsze? Pomiar

Hipoteza z #17 brzmiała „na dużym repo własny hash będzie wolny, git pewnie szybszy". Zmierzyłem
(mediana z 5 wywołań, jedna maszyna, syntetyczne pliki ~1,2 KB, ms):

| Liczba plików | `tree_hash` (Python) | git, świeży indeks | git, trwały: 1. wywołanie | git, trwały: nic się nie zmieniło | git, trwały: zmiana 1 pliku |
|---|---|---|---|---|---|
| 200 | 30,0 | 36,9 | 142,9 | 18,2 | 20,4 |
| 5000 | 421,0 | 321,8 | 1624,8 | 44,9 | 53,6 |

Wnioski, w kolejności ważności:

1. **Trwały indeks wygrywa tylko na dużym drzewie i tylko po rozgrzaniu.** Git porównuje `stat`
   (czas/rozmiar/inode) z indeksem i czyta bajty tylko zmienionych plików — to inny mechanizm niż
   „czytaj wszystko" w Pythonie, więc koszt zależy od liczby *zmian*, nie plików. 5000 plików: 45–54 ms
   zamiast 421 ms (≈8–9×).
2. **Pierwsze wywołanie jest drogie** (1,6 s przy 5000 plikach), bo `add` hashuje i **zapisuje** każdy blob.
   Przy 200 plikach własny hash jest po prostu szybszy (30 vs 143/37 ms) — narzut procesu `git`
   dominuje.
3. **Świeży indeks co wywołanie** to kompromis: 322 ms przy 5000 plikach, bez pułapki z `.gitignore`.
4. **Koszt miejsca**: `add -A` zapisuje bloby zmienionych plików w `GIT_DIR` (511 KiB po całym
   pomiarze). Dane syntetyczne są bardzo powtarzalne, więc kompresja jest nierealnie dobra (511 KiB
   wobec ~5,9 MiB treści) — nie traktuj tego jako oszacowania; ważne, że **baza rośnie z każdą unikalną
   wersją pliku**, dlatego `close()` jest obowiązkowe (`with GitTreeObserver(...)`).

Szum pomiarowy jest realny: „nic się nie zmieniło" dla 200 plików wyszło w dwóch kolejnych
uruchomieniach `demo.py` jako 44,1 i 18,2 ms. Liczby są **rzędem wielkości**, nie benchmarkiem.

### Ten sam nadzorca, ten sam wynik

```
== 3. nadzorca z GitTreeObserver jako observer (te same scenariusze co w #17)
  kreci sie na tym samym kodzie      python: NO_PROGRESS krokow=5   testow=3 koszt=89
  kreci sie na tym samym kodzie      git   : NO_PROGRESS krokow=5   testow=3 koszt=89
  oscylacja v1 <-> v2                python: NO_PROGRESS krokow=10  testow=5 koszt=215
  oscylacja v1 <-> v2                git   : NO_PROGRESS krokow=10  testow=5 koszt=215
  progres (3 proby)                  python: DONE        krokow=7   testow=4 koszt=115
  progres (3 proby)                  git   : DONE        krokow=7   testow=4 koszt=115
  rozeznanie: 8 odczytow + naprawa   python: DONE        krokow=10  testow=1 koszt=990
  rozeznanie: 8 odczytow + naprawa   git   : DONE        krokow=10  testow=1 koszt=990
```

Detektor `TREE_STALL` nie zależy od tego, **skąd** pochodzi hash — liczy tylko, ile razy weryfikacja
padła na tym samym ciągu znaków. Dlatego podmiana implementacji nie zmienia żadnego scenariusza z #17.
To jest właściwy test abstrakcji: interfejs `() -> str` jest wystarczająco wąski.

> 💡 **Dlaczego to ważne:** gdy agent pracuje w prawdziwym repo .NET, to `.gitignore` już mówi, co jest
> artefaktem (`bin/`, `obj/`, `.vs/`, `TestResults/`). Ręcznie utrzymywana lista `ignore` w nadzorcy
> rozjeżdża się z nim po pierwszym nowym narzędziu w pipeline (np. folder wyników coverage). Hash z gita
> bierze definicję „co się liczy" od zespołu, a nie od autora pętli.

---

## 2️⃣ 🧵 Archiwum dziennika: z kilku plików z powrotem w jedną oś

### Problem

Po `archive=True` (z #17) mamy `journal.jsonl` (żywy) i kilka `journal.jsonl.archive-NNNNN`. Każdy
plik zaczyna się rekordem `snapshot` (stan *po* poprzednim segmencie), potem są surowe zdarzenia. Pytanie
audytowe — „co dokładnie wydarzyło się w kroku 3 i dlaczego nie powtórzyliśmy go po restarcie" — wymaga
**jednej osi**, nie sześciu plików. A naiwne „skleję pliki" jest błędne z dwóch powodów, o których
poniżej.

### Algorytm `timeline.merge`

```
dla segmentu w [archive-00008, archive-00013, ..., zywy_plik]:
  dla rekordu w segmencie:
    jesli snapshot:
        sprawdz: snapshot.summary.total == liczba krokow zlozonych dotad   # inaczej TimelineGap
        pomin (to widok pochodny, nie zdarzenie)
    inaczej:
        pomin, jesli klucz zdarzenia juz byl                               # duplikaty
        dopisz do osi
```

Klucz zdarzenia: `(t, step)` dla `intent`/`result`, `(t, step, outcome)` dla `resolve`,
`(t, status, reason, vt)` dla `end`. Po złożeniu **`verify`** robi coś, co daje wartość całej
konstrukcji: składa `fold(oś)` i porównuje z `fold(żywy plik)` — podsumowanie (`total`, `cost`,
odciski, `tree_fail`), `pending`, `last_end`, `vt` i okno kroków. Niezgodność = `TimelineMismatch`.

```
== 5. os zdarzen z archiwow: 30 krokow, compact_every=8, keep=3, archive=True
  pliki: ['journal.jsonl', 'journal.jsonl.archive-00008', 'journal.jsonl.archive-00013', 'journal.jsonl.archive-00018', 'journal.jsonl.archive-00023', 'journal.jsonl.archive-00028']
  zywy plik: 6 rekordow (['snapshot', 'intent', 'result']...)
  os: 61 zdarzen z 6 segmentow, snapshotow pominietych: 5, duplikatow: 0
  os == dziennik BEZ kompaktowania (rekord po rekordzie): True (61 rekordow)
  explain_step(3): narzedzie=read_file, klucz=0fad94a0079cc060, wynik ok=True, resolve=None
```

Najmocniejszy dowód: ten sam bieg uruchomiony **bez** kompaktowania daje dziennik, który jest
**rekord po rekordzie identyczny** (`tl.events == full_ref`) ze złożoną osią. Czyli kompaktowanie z
archiwum jest **bezstratne dla audytu** — pod warunkiem, że wszystkie segmenty są na miejscu.

### Luka jest wykrywana, nie zgadywana

Liczba kroków w `snapshot.summary.total` działa jak numer sekwencyjny w protokole:

```
== 6. luka: usuniecie segmentu archiwum
  bez journal.jsonl.archive-00008: TimelineGap: journal.jsonl.archive-00013: snapshot oczekuje 8 krokow wczesniej, a w osi jest 0
  bez journal.jsonl.archive-00013: TimelineGap: journal.jsonl.archive-00018: snapshot oczekuje 13 krokow wczesniej, a w osi jest 8
```

Bez tej kontroli audytor dostałby oś z „dziurą" i **nie wiedziałby o tym** — a to jest dokładnie ten
błąd, który wychodzi po miesiącu, gdy ktoś posprzątał stare pliki.

### Znalezisko: twarde dowiązanie archiwum **rośnie** po crashu

Tego nie przewidziałem w #17, a wyszło przy próbie złożenia osi. `compact` robi `os.link(journal,
archive)` **przed** `os.replace(tmp, journal)`. Jeśli proces ginie *między* tymi dwoma wywołaniami,
`journal.jsonl` i `archive-00008` to **ten sam inode**. Wznowienie dopisuje do `journal.jsonl` — czyli
**też do archiwum**:

```
== 7. crash MIEDZY twardym dowiazaniem a os.replace (hook 'compact_archived')
  po crashu: archive-00008 i journal.jsonl to ten sam plik (inode): True, rekordow w archiwum: 16
  po wznowieniu: ['journal.jsonl', 'journal.jsonl.archive-00008', 'journal.jsonl.archive-00009', 'journal.jsonl.archive-00014', 'journal.jsonl.archive-00019', 'journal.jsonl.archive-00024', 'journal.jsonl.archive-00029']
  rekordow w archive-00008 po wznowieniu: 18 (w momencie kompaktowania bylo 16)
  naiwne sklejenie segmentow: 79 zdarzen; os po deduplikacji: 61 (duplikatow: 18), rownowaznosc z zywym plikiem OK
  kroki w osi: 30
```

Archiwum, które miało być zamrożone, ma 18 rekordów zamiast 16, a kolejny segment (`archive-00009`)
zawiera te same zdarzenia drugi raz. Naiwne sklejenie daje **79** „zdarzeń" zamiast 61 — audyt
twierdziłby, że efekty wykonały się wielokrotnie. Deduplikacja po kluczu zdarzenia przywraca 61 i
`verify` przechodzi (test `test_crash_between_link_and_replace_duplicates_are_dropped` porównuje też
z dziennikiem referencyjnym rekord po rekordzie).

> 💡 **Dlaczego to ważne:** to klasyczna lekcja o *aliasingu*. Twarde dowiązanie jest tanie, bo nie
> kopiuje bajtów — i dlatego **nie jest migawką**, tylko drugą nazwą żywego pliku. Zamrożone archiwum
> wymaga albo kopii (`shutil.copy2` + `fsync`, droższe), albo `rename` starego pliku (wtedy trzeba
> umieć wznowić przy braku `journal.jsonl`). Wybrałem **nie zmieniać `compact`**, tylko uczynić składanie
> odpornym na duplikaty; to świadomy kompromis: oś jest poprawna, ale pojedyncze archiwum po crashu
> nie jest „czystym" segmentem.

---

## 3️⃣ 🧪 Co jest, a czego nie ma

**Zweryfikowane (realne uruchomienia, Python 3.10.4, git 2.34.1):**
- 22 testy `unittest` (`Ran 22 tests`, `OK`) oraz `demo.py` — wszystkie liczby powyżej pochodzą z
  uruchomień (jedyna edycja: brak diakrytyków w komunikatach, tak jak w kodzie).
- Hash z `GitTreeObserver` jest identyczny z `git write-tree` w zwykłym repo; nie rusza indeksu
  repo użytkownika (test sprawdza `git status --porcelain` i brak `.git/index`).
- `chmod +x` zmienia hash gita, nie zmienia hasha Pythona; `.gitignore` + trwały indeks; ślepy punkt
  zagnieżdżonego repo.
- Te same wyniki nadzorcy dla 4 scenariuszy z #17 przy hashu z gita.
- Złożona oś jest rekord po rekordzie równa dziennikowi bez kompaktowania; luka → `TimelineGap`;
  rozbieżność → `TimelineMismatch`; duplikaty po crashu usuwane.

**Niezweryfikowane / uproszczone — wprost:**
- **Żywa sesja Claude Code, `claude -p`, `permissionMode` w frontmatterze agenta, hooki headless** —
  `claude --version` odrzucone przez uprawnienia (kolejny raz). Nie opisuję tych pól z pamięci.
- Rolę modelu gra funkcja; „testy" to sprawdzenie słowa w pliku. Nic tu nie mówi o tym, jak często
  prawdziwy LLM się zapętla.
- **Pomiar wydajności** to syntetyczne pliki, jedna maszyna, 5 powtórzeń; nie testowałem dysku sieciowego,
  Windows, repo z tysiącami małych plików typu `node_modules` ani
  dużych binariów.
- Nie sprawdzałem `git write-tree` z `core.fsmonitor`/`untrackedCache` (mogłyby przyspieszyć lub
  zmienić zachowanie), ani SHA-256 jako formatu obiektów w gicie.
- `autocrlf` jest wyłączone na sztywno; hash na Windows z CRLF w repo użytkownika nie był testowany.
- Dowiązanie twarde i `os.replace` testowane tylko na Linuksie (system plików lokalny).
- Składanie osi nie obsługuje wielu równoległych pisarzy; `merge` czyta całość do pamięci (dla
  tysięcy kroków to bywa za dużo — strumieniowe składanie nie jest zaimplementowane).
- Sprzątanie `/tmp/prasowka-loop4-*` robi kod (`rmtree`, `close()`); potwierdzenie listingiem `/tmp`
  zostało odrzucone przez uprawnienia.

**Następne kroki:** streszczenie jako „pamięć" po kompaktowaniu (to, co `History` oddaje modelowi),
strumieniowe składanie osi, `permissionMode` i hooki headless — po weryfikacji CLI.
