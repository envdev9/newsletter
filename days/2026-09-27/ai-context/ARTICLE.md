<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #3 rubryki — 27 września 2026

![AI/Kontekst](https://img.shields.io/badge/AI_%2F_Kontekst-8A5CF6?style=for-the-badge&logo=anthropic&logoColor=white)
![Pamięć](https://img.shields.io/badge/CLAUDE.md-stały_koszt-F59E0B?style=for-the-badge)
![MCP](https://img.shields.io/badge/MCP-definicje_narzędzi-10B981?style=for-the-badge)

## Podatek od każdej tury: ile kosztuje `CLAUDE.md` i serwery MCP, zanim napiszesz pierwsze słowo

</div>

---

> _"Wyniki narzędzi płacisz, gdy ich użyjesz. Pamięć i definicje narzędzi płacisz, gdy
> tylko otworzysz sesję - i w każdej następnej turze."_

W [wydaniu #2](../../2026-09-26/ai-context/ARTICLE.md) wprowadziliśmy metrykę **token-tur**:
rozmiar × liczba tur, przez które go dźwigasz. Tam pożeraczami były wyniki `Read` i `Bash`.
Dziś ta sama metryka, ale dla kontekstu, który **nie zależy od zadania**: `CLAUDE.md` i
definicje narzędzi MCP. To jest stała baza (`--base 18000` w analizatorze z #2), o której
mówiliśmy, że "odchudzaj". Dziś mierzymy, co i jak.

**Hak: wyniki narzędzi możesz ograniczyć w trakcie sesji. Stałej bazy - nie. Każda linia w
`CLAUDE.md` i każdy parametr w schemacie narzędzia jest czytany w turze 1, 2, 3... 60.**
Linia, która nikomu nie pomaga, ma więc **najgorszy możliwy współczynnik**: wynik ×
(wszystkie tury).

> ⚠️ **Uczciwie o danych.** Prawdziwych transkryptów znowu nie zmierzyłem: odczyt
> `~/.claude/projects/` został odrzucony przez system uprawnień (i nie próbowałem tego
> obchodzić). Próba pobrania dokumentacji Claude Code, żeby zweryfikować szczegóły
> ładowania pamięci, też została odrzucona. Dlatego:
> - **Zmierzone naprawdę:** rozmiary plików i definicji z mojego **fixture'a** (fikcyjny
>   projekt "Contoso Orders" i **syntetyczne** definicje narzędzi MCP - nie zrzut żadnego
>   prawdziwego serwera), plus działanie kodu (test 13/13).
> - **Mój model, nie obserwacja:** reguły ładowania pamięci (hierarchia, importy, limit
>   skoków) odtworzyłem z pamięci dokumentacji. Sekcja "Co niezweryfikowane" na końcu.
> - Liczby są **ilustracją mechanizmu**. Twój projekt ma inne - dlatego dostajesz narzędzie.

---

## 1️⃣ Pamięć jako stały koszt: co się ładuje i kiedy

Model nie ma pamięci między sesjami, więc "pamięć" projektu to pliki tekstowe, które klient
dokleja do kontekstu. Wg dokumentacji (zapis z pamięci, patrz zastrzeżenie) działa to tak:

| Warstwa | Gdzie | Kiedy wchodzi do kontekstu |
|---|---|---|
| 👤 użytkownik | `~/.claude/CLAUDE.md` | start sesji, każdy projekt |
| 📁 projekt (hierarchia) | `CLAUDE.md` w katalogu roboczym **i katalogach nadrzędnych** | start sesji |
| 🔒 lokalny | `CLAUDE.local.md` (nie do repo) | start sesji |
| 📂 podkatalogi | `CLAUDE.md` niżej w drzewie | **leniwie** - gdy sesja dotknie plików w tym katalogu |
| 🔗 importy | linia z `@ścieżka/do/pliku.md` | **od razu**, razem z plikiem, który importuje |

Trzy konsekwencje, które robią różnicę:

1. **Uruchamiasz `claude` w podkatalogu monorepo? Dostajesz też pamięć z katalogów nad nim.**
   Miejsce startu sesji zmienia stały koszt.
2. **Import (`@plik`) to nie "link", tylko wklejenie.** Wygodne organizacyjnie, ale koszt
   jest identyczny, jakbyś wpisał treść wprost. To najczęstsza pułapka: "wydzieliłem do
   `docs/`, więc odchudziłem" - nie, dopóki jest `@`.
3. **Zwykła wzmianka ścieżki (bez `@`) jest darmowa** - agent przeczyta plik, gdy uzna
   to za potrzebne (`Read` w wybranej turze, a nie w każdej). To odpowiednik
   "wskaźników zamiast zawartości" z łańcuchów subagentów (#2).

---

## 2️⃣ Pomiar: `ctxaudit.py memory`

Fixture: typowy, trochę przerośnięty `CLAUDE.md` projektu .NET + Angular (ogólne zasady,
drzewo katalogów, komendy, dwa importowane dokumenty, wklejony przykład endpointu, przypomnienia),
plik użytkownika i dwie pamięci podkatalogów. Prawdziwy output (sesja startuje w
`src/Orders.Api`):

```
1) Ładowane na starcie sesji (stały koszt, płacony w KAŻDEJ turze)
plik                              źródło         bajtów   ~tok
~/CLAUDE.md                       user              190     47
CLAUDE.md                         hierarchia       2352    588
docs/architecture.md              import@1         1154    288
docs/api-conventions.md           import@1          981    245
src/Orders.Api/CLAUDE.md          hierarchia        291     72
RAZEM                                              4968   1242
= 0.62% okna 200000 tok.; przez 40 tur: 49680 token-tur (zanim padnie pierwsze słowo o zadaniu)
```

Dwie rzeczy od razu widać:

- 🔎 **Import policzony jak zwykły tekst:** 533 z 1242 tokenów (43%) to dwa pliki z `docs/`,
  które ktoś "tylko podlinkował".
- 🔎 **Podkatalog `src/web/CLAUDE.md` (66 tok.) nie wszedł na start** - jest na liście
  "ładowane leniwie", bo sesja jest w `src/Orders.Api`. Reguły Angulara nie kosztują, gdy
  pracujesz w API. To jest **hierarchia użyta jako mechanizm oszczędzania**: reguły lokalne
  trzymaj lokalnie, nie w korzeniu.

### Co przycinać: cztery heurystyki

Skrypt szuka kandydatów regexami - wskazuje, gdzie patrzeć, nie wydaje wyroków:

```
3) Kandydaci do przycięcia (heurystyki regex)
    1 x blok kodu >15 linii (wskaż plik zamiast wklejać) ~249 tok.
    1 x drzewo katalogów (agent zrobi ls)        ~125 tok.
    5 x ogólnik bez sprawdzalnej treści          ~62 tok.
    2 x duplikat linii                           ~19 tok.
  RAZEM do zbadania: ~455 tok. (36% pamięci; linie mogą się nakładać)
```

| Kandydat | Dlaczego to zły lokator stałej bazy | Co zamiast |
|---|---|---|
| 🌳 drzewo katalogów | agent odtworzy je jednym `ls`/`Glob`, a ty aktualizujesz je ręcznie i po miesiącu kłamie | usuń; zostaw tylko rzeczy **nieoczywiste** ("`Migrations/` nie edytować ręcznie") |
| 📋 wklejony kod przykładowy | 249 tok. w każdej turze za coś, co jest w repo | wskaż plik wzorcowy (ścieżka), nie kopiuj |
| 💬 ogólniki ("write clean code", "be careful") | nie da się ich sprawdzić, więc nie zmieniają zachowania; model i tak stara się pisać dobrze | reguła **falsyfikowalna**: "money is `decimal`, never `double`" |
| ♻️ duplikaty | to samo zdanie dwa razy = płacisz podwójnie | jedna reguła, jedno miejsce |

Zasada, którą warto zapamiętać jako test każdej linii: **_"czy agent mógłby się tego
dowiedzieć sam z kodu w jednym wywołaniu narzędzia?"_** Jeśli tak - to nie należy do stałej
bazy, tylko do "na żądanie". W `CLAUDE.md` zostaje to, czego kod **nie powie**: decyzje
("nie commitujemy na main"), pułapki, komendy, których nie da się wywnioskować.

### Po: ten sam projekt po przycięciu

`CLAUDE.after.md` (ten sam katalog; `--root-file` podmienia plik korzenia) - komendy, trzy
twarde reguły, a dokumenty z `docs/` jako **wskaźniki bez `@`**:

```
1) Ładowane na starcie sesji (stały koszt, płacony w KAŻDEJ turze)
plik                              źródło         bajtów   ~tok
~/CLAUDE.md                       user              190     47
CLAUDE.after.md                   hierarchia        735    183
src/Orders.Api/CLAUDE.md          hierarchia        291     72
RAZEM                                              1216    304
= 0.15% okna 200000 tok.; przez 40 tur: 12160 token-tur (zanim padnie pierwsze słowo o zadaniu)
```

| | przed | po | zmiana |
|---|---:|---:|---:|
| tokeny stałej bazy (pamięć) | 1 242 | 304 | **4,1x mniej** |
| token-tury przy 40 turach | 49 680 | 12 160 | −37 520 |

⚠️ **Nie oszukujmy się co do sensu tej liczby.** 1 242 tokenów to 0,6% okna - w skali jednej
sesji to drobiazg. Fixture jest **mały celowo** (mieści się w artykule). Lekcja to
**proporcja i mechanizm**: ok. 75% tokenów tej pamięci dało się przenieść z "zawsze" na "na żądanie" albo usunąć (drzewo, ogólniki, duplikaty), bez utraty reguł, których kod nie zdradza. Prawdziwe
pliki `CLAUDE.md` bywają wielokrotnie większe - **ile ma twój, sprawdź skryptem**, nie zgaduj.
Drugi koszt jest ważniejszy niż rachunek: **im więcej instrukcji, tym słabiej każda z nich
się liczy** (rozmywanie uwagi - obserwacja praktyczna, której tu nie mierzyłem).

Cena przycięcia: informacja "na żądanie" wymaga, żeby agent **wiedział, że ma ją przeczytać**.
Dlatego pointer ma mówić **kiedy** ("layering, kierunek zależności: docs/architecture.md"), a nie
tylko istnieć. Czy agent w praktyce zawsze po nią sięga - **nie testowałem** (brak żywej sesji).

---

## 3️⃣ Hierarchia i importy: kiedy co

| Chcesz... | Użyj | Koszt |
|---|---|---|
| reguła dla całego repo, krótka, zawsze aktualna | `CLAUDE.md` w korzeniu | stały |
| reguła tylko dla `src/web` | `src/web/CLAUDE.md` | leniwy - płacisz tylko pracując tam |
| własne ustawienia, których nie commitujesz | `CLAUDE.local.md` | stały (u ciebie) |
| dokument, który **musi** być zawsze widoczny (rzadko!) | `@docs/x.md` | stały, pełny |
| dokument potrzebny czasem | ścieżka + "kiedy czytać" | 0 do momentu `Read` |
| powtarzalna, długa procedura | skill (opis kilkanaście tok., treść dopiero przy użyciu) | opis stały, treść leniwa |

Ostatni wiersz opieram na **własnej obserwacji z tej sesji**: lista skilli, którą dostałem w
kontekście, to jedna linia opisu na skill - pełne instrukcje ładują się dopiero po wywołaniu.
To ten sam wzorzec "krótki wskaźnik stale, treść leniwie".

**Trzy zasady mistrzowskie:**

1. **Stały koszt = tylko rzeczy, które zmieniają zachowanie w większości sesji.** Reszta
   jest "na żądanie".
2. **Importuj oszczędnie.** `@` jest dla treści, bez której agent jest ślepy od pierwszej
   tury (a takich jest mało).
3. **Sesję zaczynaj w najwęższym katalogu, który wystarcza do zadania** - hierarchia wtedy
   pracuje na ciebie (mniej pamięci z góry, a lokalne reguły i tak wchodzą).

---

## 4️⃣ MCP: koszt definicji narzędzi

Serwer MCP udostępnia narzędzia; klient wkłada do kontekstu ich **definicje** - nazwę, opis
i schemat argumentów (JSON Schema) - żeby model wiedział, że mogą być wywołane. Płacisz za
to **niezależnie od tego, czy narzędzie zostanie użyte**. Stąd zawsze ten sam rachunek:

```
koszt serwera  =  suma(tokeny definicji jego narzędzi)  x  liczba tur
```

Do tego serwer może dołączać własny tekst instrukcji (widziałem to w tej sesji: sekcja
"MCP Server Instructions" w kontekście) - to też stała baza.

Fixture: **trzy syntetyczne serwery** (`tracker` - gadatliwy, `db` i `docs` - zwięzłe;
nazwy zmyślone, generator `gen_mcp_fixture.py`). Prawdziwy output `ctxaudit.py mcp`:

```
Narzędzi łącznie: 13 w 3 serwerach

1) Koszt definicji (nazwa + opis + schemat JSON) per serwer
serwer         narzędzi    ~tok  ~tok/narz.    max  udział
tracker               8    1790         223    274   86.2%
db                    3     177          59     72    8.5%
docs                  2     109          54     58    5.3%
RAZEM                13    2076
= 1.04% okna 200000 tok. i 83040 token-tur przez 40 tur - niezależnie od tego, czy użyjesz choć jednego narzędzia

3) What-if: wyłącz serwer
  bez tracker      ->    286 tok. (oszczędność 71600 token-tur / 40 tur)
  bez db           ->   1899 tok. (oszczędność 7080 token-tur / 40 tur)
  bez docs         ->   1967 tok. (oszczędność 4360 token-tur / 40 tur)
```

Zwróć uwagę na **koszt na narzędzie**: gadatliwy `tracker` to 223 tok./narz., zwięzły `db`
59 - **prawie czterokrotna różnica** (3,8x) przy podobnej funkcjonalności. Skąd: (a) ten sam ~300-znakowy
wstęp w każdym opisie, (b) parametry, po których model i tak zgadnie znaczenie ("page",
"sort"), (c) 11 argumentów w jednym narzędziu. Audyt wskazuje to wprost:

```
4) Zastrzeżenia do definicji (heurystyki)
  tracker/tracker_list_issues: opis 378 znaków (> 300)
  tracker/tracker_list_issues: parametry bez opisu: page, per_page, sort, direction, since, assignee, creator
  tracker/tracker_list_issues: 11 parametrów (> 8)
  ...
  tracker/(kilka narzędzi): 8 opisów zaczyna się tak samo: "Use this tool when you need to work with..."
```

⚠️ **Uwaga o "parametrach bez opisu":** to heurystyka w drugą stronę niż oszczędzanie -
brak opisu bywa tanim wyborem, ale przy niejednoznacznej nazwie model źle wywoła narzędzie,
a **błędne wywołanie kosztuje więcej tur niż 15 tokenów opisu**. Cel to **gęstość
informacji**, nie minimalizm. Z drugiej strony powtarzalny wstęp "Use this tool when..." nie
niesie żadnej informacji - to czysty podatek.

### Jak to zmierzyć u siebie

Wyeksportuj listę narzędzi swojego serwera do JSON w kształcie `{"servers": {nazwa:
{"tools": [{name, description, inputSchema}]}}}` (to kształt odpowiedzi `tools/list`
protokołu MCP - kształt znam ze specyfikacji, nie sprawdzałem go na żywym serwerze) i:
`python3 -B ctxaudit.py mcp twoj.json`. **Tokeny to bajty/4 na zwartym JSON-ie** - klient
serializuje definicje po swojemu, więc to rząd wielkości i **porównanie względne** między
serwerami, nie fakturowany rachunek.

### Nowa oś: definicje ładowane leniwie (obserwacja z tej sesji)

W sesji, w której powstawał ten tekst, część narzędzi (m.in. `WebFetch`, `WebSearch`,
`Monitor`) była na liście **tylko z nazwami** - bez schematów. Dopiero wywołanie
`ToolSearch` z zapytaniem `select:WebFetch` zwróciło pełną definicję i dopiero wtedy dało
się narzędzie wywołać. To ten sam wzorzec, co w sekcji 3 (krótki wskaźnik stale, treść
leniwie), zastosowany do narzędzi. Praktyczny wniosek: **jeśli twój klient to obsługuje, duże,
rzadko używane serwery MCP nie muszą być stałym kosztem.** Jak to włączyć i jakie ma
ograniczenia - **nie sprawdzałem** (w tej sesji był to gotowy mechanizm, nie moja konfiguracja).

### Polityka dla MCP

| Pytanie | Działanie |
|---|---|
| Czy używałem tego serwera w ostatnich sesjach? | nie → wyłącz w projekcie; włącz, gdy potrzeba |
| Czy serwer ma >10 narzędzi, z których używam 2? | `What-if` z audytu: policz oszczędność; rozważ węższy serwer lub filtr narzędzi (jeśli klient to wspiera - niesprawdzone) |
| Czy opisy mają powtarzalny wstęp / puste parametry? | jeśli to twój serwer: skróć; jeśli cudzy: zgłoś lub weź inny |
| Czy narzędzie zwraca całe obiekty? | to osobny koszt (wyniki, wydanie #2) - stała baza go nie pokazuje |

---

## 5️⃣ Podsumowanie: budżet stałej bazy

| Pozycja | Mierzysz | Politykę masz |
|---|---|---|
| system + skille | (poza twoją kontrolą / lista skilli) | mało, zwięzłe opisy skilli |
| `CLAUDE.md` + importy | `ctxaudit.py memory` | test "czy agent sam się dowie?"; `@` tylko gdy konieczne |
| pamięć podkatalogów | to samo (sekcja "leniwie") | reguły lokalne - lokalnie |
| definicje MCP | `ctxaudit.py mcp` | wyłączaj nieużywane; zwięzłe opisy |
| historia i wyniki narzędzi | `analyze_transcript.py` (#2) | grep/head, subagenci, `/compact` |

**Hak na koniec:** stała baza jest jedynym elementem kontekstu, który **można zoptymalizować
raz, a zyskiwać w każdej sesji, już przy pierwszej turze**. Wyniki narzędzi wymagają
dyscypliny w każdej sesji; `CLAUDE.md` wymaga jednego przeglądu na kwartał.

---

## 🚫 Co niezweryfikowane (wprost)

| Twierdzenie | Status |
|---|---|
| Hierarchia (użytkownik / katalogi nadrzędne / podkatalogi leniwie), `CLAUDE.local.md` | z pamięci dokumentacji; **nie sprawdzone na żywym kliencie** (pobranie dokumentacji odrzucone) |
| `@import`: rekursja do 5 skoków, brak rozwijania w blokach kodu i span-ach | j.w. - stała `MAX_HOPS = 5` w skrypcie to **moje założenie** |
| Import wkleja treść (koszt jak tekst wprost) | wynika z opisu mechanizmu; nie widziałem surowego kontekstu |
| Realne rozmiary pamięci/definicji w projektach | **niezmierzone** - fixture i dane syntetyczne |
| Agent sam sięga po plik wskazany pointerem bez `@` | **nie testowane** (brak żywej sesji z modelem) |
| `CLAUDE.md` po `/compact` (z #2) | nadal niezweryfikowane |
| Włączanie leniwego ładowania definicji narzędzi | zaobserwowane jako fakt w tej sesji; konfiguracja **nie sprawdzana** |
| Analiza prawdziwego transkryptu | odczyt `~/.claude/projects` **odrzucony** - nie obchodzone |

---

## 📎 Jak uruchomić kod z tego wydania

[`code/README.md`](code/README.md) - komendy, prawdziwy output, test 13/13. Wymaga tylko
`python3`.

---

<div align="center">

[← wydanie z 27 września (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
