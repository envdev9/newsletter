<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #5 rubryki — 7 października 2026

![AI/Kontekst](https://img.shields.io/badge/AI_%2F_Kontekst-8A5CF6?style=for-the-badge&logo=anthropic&logoColor=white)
![Narzędzia MCP](https://img.shields.io/badge/narzędzia_MCP-leniwe_ładowanie-F59E0B?style=for-the-badge)
![Tool search](https://img.shields.io/badge/tool_search-BM25-10B981?style=for-the-badge)

## 264 narzędzia w kontekście, z których użyjesz 12: eager kontra leniwe ładowanie definicji

</div>

---

> _"Definicja narzędzia, którego nie wywołasz, kosztuje tyle samo co definicja tego, które wywołasz -
> i płacisz ją w każdej turze."_

W [#3](../../2026-09-27/ai-context/ARTICLE.md) policzyliśmy, ile kosztują definicje narzędzi MCP
**per serwer** i co się stanie, gdy serwer wyłączysz. Dziś kolejny krok z listy "Następne":
**nie wyłączać, tylko odroczyć** - w kontekście zostaje sama nazwa (albo nawet nic), a pełna
definicja wchodzi dopiero, gdy ktoś jej szuka. To wzorzec zwany *tool search* / *deferred tools*.

**Hak: odroczenie przesuwa koszt, nie usuwa go - i dokłada nowy rodzaj błędu.** Zyskujesz na
stałej bazie, ale płacisz (1) definicjami, które w końcu załadujesz, (2) wynikami wyszukiwania w
historii i (3) ryzykiem, że wyszukiwarka **nie znajdzie** narzędzia, bo użytkownik i autor
narzędzia mówią innym słownikiem.

> ⚠️ **Uczciwie o danych.** Katalog jest **syntetyczny**: 264 narzędzia w 8 "serwerach" generowane
> z szablonów (stałe, bez losowości). Tokeny = bajty/4, a nie prawdziwy tokenizer. **Żaden model
> ani API nie były uruchamiane** - symuluję, **co wchodzi do kontekstu** i czy prosta wyszukiwarka
> BM25 (stdlib) znajduje narzędzie. Nie wiem, jak model sam formułuje zapytania. **Dokładnych reguł
> Claude Code (kiedy włącza się tool search, próg, nazwy opcji) nie weryfikowałem** - nie miałem
> dostępu do dokumentacji ani działającego CLI w tym przebiegu, więc część "jak to wygląda w
> produkcie" to wiedza z pamięci i **hipoteza**.

---

## 1️⃣ Ile to waży: katalog

`python3 -B ctxlazy.py catalog` (prawdziwy output):

```
narzedzi: 264, serwerow: 8
pelne definicje: 26380 tok. (srednio 99.9, min 70, max 125)
same nazwy:      1835 tok.
tool_search:     91 tok.
```

Pełna definicja (nazwa + opis + schemat wejścia) ≈ **100 tok.** Sama nazwa ≈ **7 tok.** - czyli
~14x taniej. Dla porównania: 26 380 tok. to wartość, którą każda tura niesie **zanim padnie
pierwsze słowo użytkownika**. Opisy w realnych serwerach bywają znacznie dłuższe niż moje szablony
(70-125 tok.) - to zaniżenie, nie zawyżenie.

---

## 2️⃣ Cztery strategie na jednej sesji

Sesja: 12 zadań po 5 tur = 60 tur, wyszukiwarka zwraca k=5 wyników. Miara: **token-tury** (stały
rozmiar definicji × liczba tur, jak w [#2](../../2026-09-26/ai-context/ARTICLE.md)).
`python3 -B ctxlazy.py run`:

```
| strategia | stale tok/ture | koniec sesji tok/ture | token-tury | vs eager | zadan znalezionych | ponowien |
|---|---:|---:|---:|---:|---:|---:|
| eager | 26380 | 26380 | 1582800 | 1.0x | 12/12 | 0 |
| deferred_names | 1926 | 7723 | 283385 | 5.6x | 12/12 | 2 |
| deferred_blind | 91 | 5888 | 173285 | 9.1x | 12/12 | 2 |
| oracle | 91 | 1145 | 41400 | 38.2x | 12/12 | 0 |
```

| Strategia | Co do kontekstu trafia | Wniosek |
|---|---|---|
| 🧱 `eager` | wszystkie 264 pełne definicje, w każdej turze | baza 26 380 tok. - 12 użytych narzędzi to 4,5% katalogu |
| 📇 `deferred_names` | lista samych nazw (1835 tok.) + `tool_search` (91) | model **widzi, co istnieje**, i może trafniej budować zapytania; 5,6x taniej |
| 🌫️ `deferred_blind` | tylko `tool_search`, zero nazw | najtaniej (9,1x), ale model musi **zgadnąć**, czego szukać |
| 🔮 `oracle` | tylko dokładnie te 12 definicji | dolna granica (38x) - nieosiągalna, bo wymaga wiedzy z przyszłości |

Uwaga: w kolumnie "koniec sesji" `deferred_names` ma 7723 tok. - **załadowane definicje zostają w
kontekście do końca sesji**, a przy k=5 wyszukiwarka ładuje 61 narzędzi, z których użyłem 12.
Reszta to "szum z wyszukiwania": 49 definicji zapłaconych na darmo w kolejnych turach.

> ⚠️ Zastrzeżenia do tej tabeli. (1) `12/12` jest **zawyżone**: 10 z 12 zapytań napisałem
> słownictwem narzędzia, a dla 2 pozostałych **sam podałem** zapytanie ponawiane
> (`ponowien = 2`). Realny model musiałby je wymyślić. Sekcja 4 mierzy to uczciwiej.
> (2) Zakładam, że definicje załadowane przez wyszukiwanie zostają do końca sesji i nie są
> wyrzucane - to założenie modelu, nie zweryfikowana cecha produktu.

---

## 3️⃣ Pokrętło `k`: ile wyników ładować

`python3 -B ctxlazy.py sweep`, część A (`deferred_names`):

```
| k | token-tury | zadan znalezionych | narzedzi zaladowanych |
|---:|---:|---:|---:|
| 1 | 152765 | 12/12 | 14 |
| 2 | 181795 | 12/12 | 25 |
| 3 | 216030 | 12/12 | 36 |
| 5 | 283385 | 12/12 | 61 |
| 8 | 366125 | 12/12 | 87 |
| 12 | 464455 | 12/12 | 112 |
| 20 | 648595 | 12/12 | 164 |
```

Koszt rośnie **prawie liniowo z k**; k=20 to już 41% eagera w token-turach. Tabela kłamie tylko
w jednym miejscu, ale istotnym: przy takich zapytaniach (literalnych) nawet `k=1` wystarcza, więc
widać "darmowe" oszczędności. **Im gorsze zapytania, tym więcej k potrzeba i tym bardziej
płacisz.** Dobór k to kompromis między kosztem a recall, a recall mierzymy niżej.

Część B tego samego polecenia: katalog rośnie, a baza leniwego tylko trochę.

```
| serwerow | narzedzi | eager tok/ture | deferred_names tok/ture (start) | trafione z 10 |
|---:|---:|---:|---:|---:|
| 5 | 174 | 17437 | 1306 | 10/10 |
| 6 | 206 | 20560 | 1495 | 10/10 |
| 7 | 232 | 23136 | 1681 | 10/10 |
| 8 | 264 | 26380 | 1926 | 10/10 |
```

Dołożenie 3 serwerów (90 narzędzi) kosztuje eager +8943 tok. w **każdej** turze, a leniwe +620.
To najmocniejszy argument: leniwe ładowanie **skaluje się z liczbą narzędzi, których użyjesz**,
nie z liczbą, które zainstalujesz.

---

## 4️⃣ Gdzie to się psuje: recall wyszukiwarki

Oszczędność jest bezwartościowa, jeśli narzędzia nie da się znaleźć. 18 zapytań: 12 parafraz
(bez słów z nazwy narzędzia, tak jak mówi człowiek) i 6 krótkich zapytań "czasownik rzeczownik".
`python3 -B ctxlazy.py recall` (fragment, całość w `README.md` kodu):

```
| close the bug report | jira__transition_ticket | brak |
| silence the pager | monitoring__acknowledge_alert | 9 |
| why is this query slow | postgres__explain_query | 47 |
| tell the team in chat | slack__post_message | brak |
| when can we all meet | calendar__find_free_slot | brak |
| ship the change into main | github__merge_pull_request | brak |
| give this to Anna | jira__assign_ticket | 43 |
| k | recall@k |
| 1 | 10/18 |
| 3 | 10/18 |
| 5 | 10/18 |
| 10 | 11/18 |
```

**Leksykalne wyszukiwanie ma recall ~55% i nie poprawia się ze wzrostem k** (10/18 przy k=1, 11/18
przy k=10): nieznalezione narzędzia leżą na pozycjach 9, 43, 47 albo wcale. Na pozycjach 1 lądują
te zapytania, które zawierają nazwę akcji. Są jeszcze dwie rzeczy do zapamiętania:

- 🎲 Zapytania niejednoznaczne (`create comment`, `list comments`) trafiły na 1. miejsce, ale
  **po części przez remis**: przy równym wyniku moja implementacja sortuje alfabetycznie, a `jira`
  jest przed `github`/`slack`. To nie jest dowód, że wyszukiwarka rozróżnia serwery.
- 🔤 Wyszukiwarka ma 0 wiedzy semantycznej ("pager" ≠ "alert", "ship" ≠ "merge"). Wyszukiwarka
  wektorowa mogłaby to poprawić - **nie sprawdzałem**.

**Hipotezy (niezweryfikowane, bo nie uruchamiałem modelu):**
1. Model sam przeformułuje zapytanie ("acknowledge alert") i niedopasowanie leksykalne mniej
   zaboli, szczególnie gdy widzi **listę nazw** (`deferred_names`). To jest jedyny argument za
   tym, żeby trzymać nazwy w kontekście - płacisz 1835 tok. za słownik.
2. Dobry opis narzędzia ma słowa, których użyje człowiek ("close", "ship", "silence"), nie tylko
   słowa autora API. Autor serwera MCP wpływa więc na recall bardziej niż konsument.

---

## 5️⃣ Punkt równowagi: kiedy leniwe przestaje się opłacać

`python3 -B ctxlazy.py breakeven` - najgorszy przypadek (wszystkie `m` definicji załadowane od
pierwszej tury):

```
| m zaladowanych | deferred tok/ture | oszczednosc vs eager |
|---:|---:|---:|
| 0 | 1926 | +93% |
| 5 | 2426 | +91% |
| 10 | 2925 | +89% |
| 20 | 3924 | +85% |
| 40 | 5923 | +78% |
| 60 | 7921 | +70% |
| 80 | 9920 | +62% |
| 264 | 28306 | -7% |
punkt rownowagi: m = 245 narzedzi z 264 (93% katalogu)
```

Oszczędność znika dopiero, gdy ładujesz **prawie wszystko**. Przy realnym użyciu (kilka-kilkanaście
narzędzi) wygrywa ogromnie. **Ale** ten rachunek ignoruje: wyniki wywołań `tool_search` w historii,
dodatkowe tury na samo wyszukiwanie (każda to też koszt i opóźnienie) i skutki dla cache'u.

### Cache a nowe definicje (hipoteza)

Z [#1](../../2026-09-24/ai-context/ARTICLE.md): prompt caching działa na prefiksie, a definicje
narzędzi leżą na początku. Jeśli leniwe ładowanie **dopisuje definicje na końcu rozmowy** (jako
treść tury), prefiks się nie zmienia - to wielka zaleta nad "dołóż narzędzie do listy `tools`",
które unieważniałoby cache od początku. **Tak to działa w Claude Code - nie zweryfikowałem**;
wiem tylko, że kolejność warstw uzasadnia, dlaczego powinno tak działać. Nie mierzyłem cache'u.

---

## 6️⃣ Checklista dla .NET deva podłączającego serwery MCP

| Pytanie | Dlaczego |
|---|---|
| Ile narzędzi mam zainstalowanych i ile użyłem w ostatnich 10 sesjach? | Jeśli użycie <10% katalogu, eager marnuje bazę - to ta sama proporcja co tu (12/264) |
| Czy opisy mają słowa z języka użytkownika? | Recall ~55% przy parafrazach - opis jest indeksem wyszukiwania |
| Czy nazwy są unikalne i mówią o akcji (`github__merge_pull_request`)? | Prefiks serwera + czasownik+rzeczownik to jedyny sygnał rozróżniający serwery w wyszukiwarce |
| Czy trzymać nazwy w kontekście? | 1835 tok. za "słownik" - tańsze niż eager 14x, ale nie za darmo |
| Jakie `k`? | Koszt rośnie liniowo; zacznij od małego i mierz pudła |
| Czy narzędzia typowo używane **razem** pogrupować? | Jedno wyszukiwanie ładuje całą grupę, ale płacisz za nie wszystkie |

---

## 🧪 Co zweryfikowano, a co nie

| ✅ Zmierzone (kod, Python 3.10.4, stdlib) | ❓ Niezweryfikowane |
|---|---|
| Koszt katalogu syntetycznego: 264 narz. = 26 380 tok. (bajty/4) | Jak model formułuje zapytania i czy trafia w `k` wyników |
| Strategie eager / names / blind / oracle w token-turach (5,6x / 9,1x / 38x) | Dokładne reguły Claude Code: próg włączenia tool search, nazwy opcji, czy definicje zostają do końca sesji |
| Wpływ `k` i rozmiaru katalogu | Wpływ na prompt cache (hipoteza z sekcji 5) |
| Recall BM25 na 18 zapytaniach: 10/18 @1, 11/18 @10 | Wyszukiwanie wektorowe/semantyczne |
| 15 testów jednostkowych, w tym negatywny (parafraza bez ponowienia = pudło) | Realne opisy narzędzi z prawdziwych serwerów MCP (mogą być dłuższe i różnorodniejsze) |

## 🎯 Zapamiętaj

1. **Koszt narzędzi to funkcja katalogu x tury**; leniwe ładowanie zamienia ją na funkcję *użytych* narzędzi.
2. **Dwie liczby naraz**: oszczędność w token-turach **i** recall wyszukiwania. Sama oszczędność jest jak `head` z #13 - tania i ślepa.
3. **Ładowane definicje zostają** - `k` to pokrętło kosztu, a nie tylko recall.
4. **Opis narzędzia to indeks.** Pisz go słowami człowieka, nie tylko API.

### ➡️ Następne kroki
- Weryfikacja w dokumentacji Claude Code: kiedy i jak włącza się odroczone ładowanie, co z cache'em.
- Wyszukiwarka z synonimami / embeddingami i porównanie recall na tym samym zestawie.
- Analiza prawdziwego transkryptu (gdy odczyt będzie dozwolony): ile narzędzi realnie wywołano na sesję.
- Strategia dzielenia zadania na okna kontekstu (plik handoff, kryteria cięcia).
