<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #9 rubryki — 14 października 2026

![AI/Kontekst](https://img.shields.io/badge/AI_%2F_Kontekst-8A5CF6?style=for-the-badge&logo=anthropic&logoColor=white)
![Odczyty](https://img.shields.io/badge/powtorzone_odczyty-dedup_vs_cache-EF4444?style=for-the-badge)
![Zmierzone](https://img.shields.io/badge/17_krokow-prawdziwe_pliki_i_testy-10B981?style=for-the-badge)

## Ten sam plik po raz piąty. Dlaczego „wyrzuć stare odczyty z kontekstu” może wyjść drożej niż ich zostawienie

</div>

---

> _"Najtańszy token to ten, którego nie trzeba było przeczytać po raz drugi. Najdroższy — ten, który
> zmienił prefiks i zmusił cache do zapomnienia wszystkiego po sobie."_

Seria o kontekście miała dotąd dwie osie: **ile** wchodzi do okna (kompresja, leniwe narzędzia, handoff, fold)
i **w jakiej kolejności** (warstwy, [cache](../../2026-09-24/ai-context/ARTICLE.md)). Dziś ich zderzenie na
najbardziej prozaicznym przypadku: agent czyta **ten sam plik** wiele razy — po edycji, po testach, „dla
pewności”. Każdy odczyt to pełna kopia. Naturalny odruch: *„stare kopie są zbędne, wytnijmy je”*.

**Hak:** na 17-krokowej sesji, którą skrypt wykonuje na prawdziwych plikach (edycje, testy przez
`subprocess`), wycinanie starych kopii daje **2,44× mniej token-tur** niż nic nie robić — ale po
uwzględnieniu cache kosztuje **tylko 1,11× mniej**. Polityka, która **nie rusza historii**, a przy ponownym
odczycie oddaje stub albo diff, daje token-tury 1,94× mniejsze i koszt ważony cache **2,65× mniejszy**. To
nie jest „lepsza kompresja”; to inna *chwila*, w której podejmujesz decyzję.

> ⚠️ **Uczciwie o danych.** Sesja jest **skryptowana** (`SCRIPT` w `ctxdedup.py`): pliki, edycje i wyniki
> testów są prawdziwe, ale **żaden model nie był uruchamiany** i nie znam rozkładu powtórzeń prawdziwych
> sesji (odczyt `~/.claude/projects` odrzucano). Liczby opisują **kształt kontekstu przy danej polityce**, nie
> zachowanie modelu. Mnożniki cache (0,10 / 1,25) i baza 8000 tok. to **moje założenia** — dlatego jest tabela
> wrażliwości (sekcja 5).

---

## 1️⃣ Eksperyment: 17 kroków, 3 pliki prawdy

Fixture to dwa prawdziwe pliki z poprzedniego wydania: `ctxsearch.py` (31 846 B → **7962 tok.**) i
`test_ctxsearch.py` (5156 B → 1289 tok.), tokeny = bajty/4. Skrypt zadania: „zmień `k` w RRF, sprawdź testy,
posprzątaj”:

| Rodzaj | Ile | Co |
|---|---|---|
| `Read` | 8 | 5× `ctxsearch.py`, 3× `test_ctxsearch.py` (w tym dwa powtórzenia **bez zmiany pliku**) |
| `Edit` | 4 | `k=60→20`, komentarz w `main`, zmiana komunikatu testu, `k=20→60` |
| `Bash` (testy) | 5 | prawdziwe `python3 -B test_ctxsearch.py`, za każdym razem `OK: 40 asercji` |

Edycje robi `str.replace` z wymogiem „wzorzec występuje dokładnie raz” (inaczej wyjątek) na kopii w katalogu
tymczasowym — tak jak robi to narzędzie `Edit`. Stan końcowy: pliki identyczne z początkowymi poza jednym
komentarzem i komunikatem testu.

Pierwsze ciekawe: testy przeszły **także z `k=20`** (wszystkie 5 uruchomień: `OK: 40`, `exit 0`). Zestaw nie
przypina `k`, więc „zielone” nic nie mówi o wartości, którą agent właśnie ustawił. To osobny temat (testy jako
źródło prawdy), ale ma tu skutek: wynik testu w kontekście ma **10 tokenów** — koszt siedzi w odczytach plików,
nie w testach.

---

## 2️⃣ Cztery polityki

| Polityka | Co robi | Mutuje historię? |
|---|---|---|
| `none` | każdy odczyt = pełna treść | nie |
| `retro` | po nowym odczycie/edycji pliku **stare** odczyty tego pliku zamieniane na stub („zastąpiona: nowsza wersja niżej”); stare wyniki testów też | **tak** |
| `append` | narzędzie odczytu pamięta ostatnią wersję **widzianą w kontekście**: bez zmian → stub „bez zmian od tury N”; zmieniony → **unified diff** (gdy < 50% rozmiaru pliku); inaczej pełny plik | nie |
| `append+` | jak `append` + identyczny wynik testów → stub | nie |

Różnica nie jest estetyczna. `retro` podejmuje decyzję **po fakcie** i **zmienia to, co już było wysłane**.
`append` podejmuje ją **przy zapisie**: historia rośnie wyłącznie na końcu.

---

## 3️⃣ Wyniki

`python3 -B ctxdedup.py run` (baza 8000 tok., cache: odczyt 0,10×, zapis 1,25× — **założenia**):

```
| polityka | kontekst koncowy | token-tury | vs none | zapis do cache (tok.) | koszt wazony | vs none | odtworzenie odczytow | stare pelne kopie (tok.) |
|---|---|---|---|---|---|---|---|---|
| none | 51915 | 574604 | 1.00x | 43915 | 107963 | 1.00x | 8/8 | 34390 |
| retro | 17611 | 235431 | 2.44x | 64228 | 97405 | 1.11x | 8/8 | 0 |
| append | 17763 | 295676 | 1.94x | 9763 | 40795 | 2.65x | 8/8 | 9238 |
| append+ | 17769 | 295705 | 1.94x | 9769 | 40805 | 2.65x | 8/8 | 9238 |
```

Trzy rzeczy do wyciągnięcia:

1. 🧊 **`retro` wygrywa na „token-turach”, `append` na pieniądzach.** `retro` kasuje stare kopie, więc
   kontekst jest najmniejszy (17 611 tok.), ale każde kasowanie zmienia treść na pozycji, która była już w
   cache → **wszystko po niej jest zapisywane od nowa**: 64 228 tok. zapisu do cache wobec 9 763 dla `append`.
   `retro` zapisuje do cache **więcej niż `none`** (43 915), choć wysyła mniej.
2. 🧾 **Odczyt pliku po edycji kosztuje 33–106 tokenów zamiast 7 962.** Diff zmiany jednej
   linii w `ctxsearch.py` to 33 tok., dopisanie komentarza 51, a zmiana komunikatu w pliku testowym 106.
   Pełna tabela `python3 -B ctxdedup.py trace` pokazuje to turą po turze.
3. ✅ **Nic nie zginęło**: `verify` odtwarza *każdy* z 8 odczytów wyłącznie z tekstu widocznego w kontekście
   (pełny odczyt + kolejne diffy) i porównuje z dyskiem — 8/8 dla wszystkich polityk, stan końcowy obu plików
   zgodny. (`retro` też, bo testuję kontekst w turze `t`, nie w ostatniej.)

Kolumna „stare pełne kopie”: `append` zostawia w kontekście **jedną nieaktualną pełną kopię każdego pliku**
(9238 tok.) — to pierwszy odczyt, na który wskazują diffy. W `none` jest ich 34 390, w `retro` zero. Czy to
szkodzi (model widzi starą wersję i diff obok)? **Nie mierzyłem** — to pytanie o model.

---

## 4️⃣ Im więcej „dla pewności”, tym większa przewaga

`python3 -B ctxdedup.py sweep` — ta sama sesja + N dodatkowych odczytów `ctxsearch.py` na końcu, bez zmian
pliku (zachowanie „agent czyta jeszcze raz, bo nie jest pewien”):

```
| dodatkowych powtorzen | token-tury none | retro/none | append/none | koszt wazony none | retro/none | append/none |
|---|---|---|---|---|---|---|
| 0 | 574604 | 0.41 | 0.51 | 107963 | 0.90 | 0.38 |
| 5 | 953684 | 0.34 | 0.40 | 191681 | 0.79 | 0.26 |
| 10 | 1531939 | 0.27 | 0.31 | 295317 | 0.70 | 0.20 |
| 20 | 3285974 | 0.18 | 0.20 | 562341 | 0.56 | 0.14 |
```

Koszt `none` rośnie **superliniowo** (5,7× token-tur przy 20 powtórzeniach — każda kopia jest ponownie
wysyłana w każdej kolejnej turze). Oba rozwiązania są prawie płaskie. Przy 20 powtórzeniach `append` kosztuje
14% bazowego, `retro` 56%. Dlaczego `retro` nie spada tak mocno: każdy dodatkowy odczyt stubuje
poprzedni, a to znów zmiana w środku historii.

---

## 5️⃣ Kiedy `retro` jednak wygrywa — wrażliwość na cache

Wynik zależy od mnożnika odczytu z cache. `python3 -B ctxdedup.py cache`:

```
| mnoznik odczytu z cache | zapis | none | retro | append | najtanszy |
|---|---|---|---|---|---|
| 1.00 | 1.00 | 574604 | 235431 | 295676 | retro |
| 0.75 | 1.25 | 452910 | 208687 | 226638 | retro |
| 0.50 | 1.25 | 320238 | 165886 | 155160 | append |
| 0.25 | 1.25 | 187566 | 123086 | 83682 | append |
| 0.10 | 1.25 | 107963 | 97405 | 40795 | append |
| 0.05 | 1.25 | 81428 | 88845 | 26499 | append |
```

- Bez cache (wiersz 1,00) wygrywa `retro`: mniejszy kontekst = mniej do wysłania, a mutacja nic nie psuje.
- Przy tańszym odczycie niż ~0,5–0,75 cena zapisu po mutacji przeważa. Przy 0,05 `retro` jest **gorszy od
  nic-nierobienia** (88 845 vs 81 428).
- Punkt przecięcia leży gdzieś w (0,5; 0,75) — dokładniej nie liczyłem. **Nie wiem, jakie mnożniki
  obowiązują w Twoim planie/modelu** (moje 0,10/1,25 są z pamięci i nie były weryfikowane, dokumentacja
  niedostępna). Reguła: przy realnie tanim odczycie z cache nie ruszaj historii; bez cache
  (albo przy zimnym cache po przerwie) `retro` jest racjonalne.

---

## 6️⃣ Co może pójść źle (i czego nie sprawdzałem)

| Ryzyko | Mechanizm | Status |
|---|---|---|
| 🕳️ **Wiszący stub** | po `/compact` lub handoffie odczyt „jak w turze 1” wskazuje na treść, której już nie ma w oknie | **niezweryfikowane**; reguła: po kompakcji/nowym oknie zeruj `last_seen` (kod: wystarczy nowa symulacja) |
| 🧠 **Czy model czyta diff** | diff to inna reprezentacja; model może zażądać pełnego pliku albo źle złożyć wersję | **niezweryfikowane** — kod sprawdza tylko, że diff *da się* złożyć mechanicznie (8/8, plus 300 losowych edycji) |
| 🔌 **Kto to wdraża** | polityka `append` wymaga warstwy między modelem a dyskiem (własny MCP / hook / wrapper narzędzia). Czy `claude` sam coś takiego robi — nie wiem (CLI niedostępne, dokumentacja odrzucona) | **niezweryfikowane** |
| ✏️ **Edycja na starej wersji** | `Edit` wymaga dokładnego dopasowania `old_string`; model pracujący ze stale widokiem popełni błąd. `append` go ogranicza (diff pokazuje nowy stan), `none` nie | nie mierzone |
| 🎯 **Próg diffu 50%** | wartość umowna; duży refactor → pełny plik | nie stroiłem |

---

## 7️⃣ Checklista

| # | Reguła | Dlaczego |
|---|---|---|
| 1 | **Decyduj przy zapisie, nie po fakcie** | `append` 9 763 tok. zapisu do cache vs `retro` 64 228 |
| 2 | **Odczyt bez zmian zwraca pointer (~14 tok.), nie plik (7 952)** | 2 takie odczyty w sesji = 9 210 tok. mniej w każdej kolejnej turze |
| 3 | **Po edycji: diff względem tego, co model *widział*, nie względem dysku sprzed edycji** | `last_seen` z kontekstu, nie z systemu plików — inaczej diff się nie złoży |
| 4 | **Zweryfikuj mechanicznie, że kontekst odtwarza stan** | `verify` 8/8; koszt weryfikacji ~0 |
| 5 | **Policz politykę dla swojego mnożnika cache** | punkt przecięcia (0,5; 0,75); bez cache wygrywa `retro` |
| 6 | **Po kompakcji zeruj pamięć odczytów** | wiszący stub to cichy błąd |
| 7 | **Nie optymalizuj wyników testów, zanim nie zobaczysz, co jest duże** | 10 tok. vs 7 962 tok. pliku |

---

## 🧪 Co zweryfikowano, a co nie

| ✅ Zmierzone (kod, Python 3.10.4, stdlib) | ❓ Niezweryfikowane |
|---|---|
| 17 kroków na prawdziwych plikach; edycje i testy wykonane naprawdę (`subprocess`) | Zachowanie żadnego modelu (nie uruchamiany) |
| 4 polityki: token-tury, zapis do cache, koszt ważony | Mnożniki cache 0,10/1,25 (z pamięci) i baza 8000 tok. (założenie) |
| Odtwarzalność wszystkich odczytów z kontekstu 8/8; 300 losowych diffów | Rozkład powtórzeń w prawdziwych sesjach (skrypt pisał jeden autor) |
| Wrażliwość na mnożnik odczytu i na liczbę powtórzeń | Czy/jak `claude` sam deduplikuje odczyty; wpływ stuba/diffu na jakość |
| 30 asercji (`test_ctxdedup.py`), w tym test negatywny (zepsuty diff) | Zachowanie po `/compact`; edge-case’y diffu (CRLF, bez końcowego `\n`, binaria) |

## 🎯 Zapamiętaj

1. **Powtórzone odczyty to koszt superliniowy** — każda kopia jedzie w każdej kolejnej turze.
2. **Dedupikacja przy zapisie** (stub/diff) zachowuje prefiks; **retroaktywna** mutuje historię i płaci cache’em.
3. **Wszystko zależy od mnożnika cache** — zmierz u siebie, nie zakładaj.
4. **Weryfikuj odtwarzalność stanu**, nie tylko rozmiar.

### ➡️ Następne kroki
- Ta sama sesja z **prawdziwym transkryptem** (gdy odczyt dozwolony) — jaki jest realny rozkład powtórzeń.
- Zachowanie po kompakcji: unieważnianie `last_seen` i test „wiszącego stuba”.
- Reguły `CLAUDE.md` i „lost in the middle” (nadal otwarte — wymagają modelu).
- Dedupikacja wyników `grep`/`ls` (częściowe pokrycie, nie całe pliki).
