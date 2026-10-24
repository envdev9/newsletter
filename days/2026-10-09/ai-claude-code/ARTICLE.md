<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #16 — 9 października 2026

![AI](https://img.shields.io/badge/AI_%2F_Claude_Code-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![EF Core](https://img.shields.io/badge/EF_Core-10.0.12-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL_16.14-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Testy](https://img.shields.io/badge/run__tests.py-40%2F40-brightgreen?style=for-the-badge)

## `ef-core-review` v3: ten sam skill, drugi silnik — PostgreSQL, plany z `EXPLAIN` i bramka w CI

</div>

---

> _"Reguła, która w SQL Server krzyczy, w PostgreSQL bywa fałszywym alarmem — a reguła, która
> w PostgreSQL powinna krzyczeć, może w ogóle nie istnieć."_

W #15 obiecałem trzy rzeczy: zmierzyć `Contains` na PostgreSQL, wpiąć skanowanie planów w
testy/CI i dobić spill typu Hash. Dziś: pierwsze zrobione w całości, drugie w wersji
"bramka budżetowa na planach z prawdziwej bazy", trzecie tylko na PostgreSQL (spill typu Hash
w **SQL Server** nadal czeka — patrz sekcja 7). Czwarty dług, żywa sesja `claude`, też nie
został spłacony.

---

## 1️⃣ 🎯 Dlaczego to ważne: skill, który zna jeden silnik, jest gorszy niż brak skilla

Hook z #14/#15 blokuje edycję przy każdym WARN. Gdy wskazałem skanerem projekt na Npgsql
(`pg-plan-demo`), pierwsze uruchomienie dało trzy rzeczy, które były **złe dla tego silnika**:

- `LIKE-LEADING-WILDCARD` straszył odczytami logicznymi "371 vs 5-25" z SQL Server i radził
  "SQL Server czyta całą tabelę" — w projekcie, w którym SQL Servera nie ma;
- `STRING-UNICODE` ostrzegał przed `nvarchar` — w PostgreSQL nie ma `nvarchar`;
- `CONTAINS-LIST` opowiadał o "wiaderkach" parametrów EF dla SQL Server.

Skaner, który w czyimś projekcie pisze nieprawdę, uczy ignorować hook. Dlatego dziś najpierw
**pomiar na PostgreSQL**, potem dopiero zmiany w regułach.

## 2️⃣ 🔬 Pomiar 1: `ids.Contains(...)` w Npgsql

Dane: PostgreSQL 16.14 (Docker, własny kontener), Npgsql EF Core 10.0.0 na EF Core 10.0.12,
tabela `customers` 200 000 wierszy. SQL dla listy `{10, 20, 30}` w trybie domyślnym (nic nie
ustawiałem) i w `Parameter`:

```sql
SELECT c."Id", c."Email"
FROM customers AS c
WHERE c."Id" = ANY (@three)       -- jeden parametr tablicowy
```

W trybie `Constant`: `WHERE c."Id" IN (10, 20, 30)`. Różnica w `pg_stat_statements`
(300 zapytań, listy o rozmiarach 1…300, statystyki zerowane przed każdym trybem):

```
domyslny (nie ustawiony) wpisow w pg_stat_statements:   1   wywolan: 300   czas 300 zapytan: 1010 ms
Parameter                wpisow w pg_stat_statements:   1   wywolan: 300   czas 300 zapytan:  781 ms
Constant                 wpisow w pg_stat_statements: 300   wywolan: 300   czas 300 zapytan: 1181 ms
```

Wniosek, który **różni się** od SQL Server z #15 (tam: 23 wpisy w trybie domyślnym): Npgsql
domyślnie wysyła listę jako **jedną tablicę**, więc jedna postać zapytania niezależnie od
rozmiaru listy. `CONTAINS-LIST` dla Npgsql jest więc szumem — wyciszony. `Constant` nadal
daje 300 różnych tekstów zapytania, więc `CONTAINS-CONSTANT` zostaje WARN. Czasy to pojedyncze
uruchomienia (wcześniejszy przebieg tego samego kodu: 813 / 696 / 1051 ms) — liczy się kolejność,
nie dokładne milisekundy. Lista 5000 elementów: 45 / 54 / 82 ms (wcześniej 28 / 41 / 56) —
wszystko w granicach szumu, **bez wniosku** o przewadze któregoś trybu przy tej wielkości.

## 3️⃣ 🔬 Pomiar 2: `StartsWith`, `Contains` i trzy rodzaje indeksu

Kolumna `Email varchar(100)`, 200 000 wierszy (`user<N>.<12 znaków md5>@<domena>`), baza w
kolacji `en_US.utf8` (domyślnej dla obrazu `postgres:16`). Cztery zapytania z `Queries.cs`,
każde z parametrem, a plan nie z ręki, tylko z **interceptora**, który po wykonaniu zapytania
uruchamia na osobnym połączeniu `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` tego samego polecenia
z tymi samymi parametrami. Trzy zestawy indeksów, każdy po `ANALYZE`:

```
indeks             zapytanie    wierszy   bufory       ms  wezly
btree              eq                 1        4     0.21  Index Scan
btree              startswith         1     1696    34.76  Seq Scan
btree              contains           1     1696    67.07  Seq Scan
btree              endswith       50000     1696   147.18  Seq Scan
btree_pattern_ops  eq                 1        4     0.03  Index Scan
btree_pattern_ops  startswith         1        4     0.03  Index Scan
btree_pattern_ops  contains           1     1696    67.43  Seq Scan
btree_pattern_ops  endswith       50000     1696    70.88  Seq Scan
gin_trgm           eq                 1      461    14.74  Bitmap Heap Scan + Bitmap Index Scan
gin_trgm           startswith         1      255     8.75  Bitmap Heap Scan + Bitmap Index Scan
gin_trgm           contains           1       17     0.16  Bitmap Heap Scan + Bitmap Index Scan
gin_trgm           endswith       50000     2050    69.22  Bitmap Heap Scan + Bitmap Index Scan
```

Cztery lekcje, każda zmierzona:

1. **`StartsWith` na zwykłym btree w kolacji innej niż `C` to Seq Scan** — 1696 buforów
   zamiast 4. W SQL Server `LIKE 'x%'` na indeksie "po prostu działa" (25 odczytów w #15),
   w PostgreSQL potrzebujesz `varchar_pattern_ops`/`text_pattern_ops` albo kolacji `C`.
   Z `varchar_pattern_ops` planer przepisał warunek na zakres
   (`>= 'user77777.22a4' AND < 'user77777.22a5'`) i przeczytał 4 bufory. Nie sprawdzałem,
   czy robi to także w innych kolacjach niż `en_US.utf8`.
2. **Ten indeks nie pomaga `Contains`** (nadal 1696). Pomaga dopiero **GIN z `gin_trgm_ops`**
   (rozszerzenie `pg_trgm`, w obrazie `postgres:16` jest): **17 buforów, 0.16 ms** zamiast
   1696 buforów i ok. 67 ms.
3. **Trigramy nie są darmowe ani uniwersalne.** Ten sam indeks GIN dla `eq` kosztuje 461
   buforów i 14.7 ms, a dla `startswith` — 255 / 8.8 ms, przy 4 / 0.03 ms na btree. W
   tym eksperymencie zmierzyłem tylko czas **zapytań**, nie koszt utrzymania ani rozmiar
   indeksu przy zapisie — nie dam więc liczby "ile to kosztuje przy INSERT".
4. **`EndsWith('@corp.example')` zwraca 25% tabeli** (50 000 z 200 000). Seq Scan jest tu
   rozsądnym wyborem planera; z GIN-em było nawet nie lepiej w buforach (2050 vs 1696),
   choć szybciej w czasie (69 ms vs 147 ms na btree; 71 ms na pattern_ops-Seq Scan). Reguła
   skanera na planie **musi** to wiedzieć, inaczej każde `LIKE '%...'` krzyczałoby tak samo.

> 🪤 **Pułapka procesu (zmierzona):** pierwsza wersja demo budowała warianty indeksów
> *narastająco*. W wierszach `gin_trgm` zapytania `eq` i `startswith` nadal korzystały z
> `ix_email_pattern` z poprzedniego wariantu (4 bufory), więc tabela wyglądała, jakby GIN
> był świetny także dla `eq`. Dopiero dopisanie kolumny z warunkami (`Index Cond`/`Filter`)
> w wydruku i `DROP INDEX` przed GIN-em pokazało prawdę (461 i 255). Druga pomyłka: w
> pierwszym podejściu lista `{10, 20, 30}` była literałem w wyrażeniu LINQ, więc EF od razu
> wstawił ją do SQL jako `IN (10, 20, 30)` w *każdym* trybie — pokazałem to jako "domyślne
> zachowanie Npgsql", dopóki nie zobaczyłem tego w wydruku. Lista musi być zmienną.

## 4️⃣ 🔬 Pomiar 3: spill w PostgreSQL — Hash i Sort na dysk

Tym samym interceptorem: self-join `customers` po `Email` (200 000 × 200 000) i
`ORDER BY Email`, najpierw przy domyślnym `work_mem` (4 MB), potem z `work_mem=64kB` (opcja
połączenia `-c work_mem=64kB`):

```
work_mem domyslny  join: Hash: 4 partii (batches)      342.1 ms | sort: external merge 9496kB na dysku   1028.5 ms
work_mem 64kB      join: Hash: 256 partii (batches)    403.9 ms | sort: external merge 6920kB na dysku    794.6 ms
```

Dwa zaskoczenia, których nie wyjaśniam: już przy **domyślnym** `work_mem` hash join dla
200 000 wierszy szedł w 4 partiach (czyli na dysk; `Temp Written Blocks` = 2352), a z
`work_mem=64kB` zapis tymczasowy był większy (4088 bloków), ale **czas prawie ten sam**
(342 vs 404 ms), natomiast sortowanie z mniejszym `work_mem` wyszło *szybsze* (795 vs 1029 ms)
i z mniejszą deklarowaną przestrzenią na dysku. To pojedyncze uruchomienia z narzutem
`EXPLAIN ANALYZE`; nie umiem z nich powiedzieć nic o wpływie `work_mem` na czas. Pewne jest tylko to,
co jest w planie: skaner widzi `Hash Batches > 1` i `Sort Method: external merge`.

To nie jest ten spill, który obiecywałem (SQL Server, operator Hash Match z ostrzeżeniem
`HashSpillDetails`). Jest to jego odpowiednik na innym silniku — nazywam go tak, żeby nie
udawać, że dług został spłacony.

## 5️⃣ 🧩 Co zmienia się w skillu

### Skaner kodu `scan_ef.py` — dialekt

| Zmiana | Efekt |
|---|---|
| Wykrywanie `UseNpgsql(...)` w skanowanym zestawie | komunikaty PG zamiast SQL Server |
| `EF.Functions.ILike(x.Kol, "%..")` | tak samo jak `Like` → `LIKE-LEADING-WILDCARD` |
| Nowa reguła `PG-STARTSWITH-OPCLASS` (INFO) | `StartsWith` na kolumnie z btree, a w kodzie brak `pattern_ops`/`gin_trgm_ops`/`UseCollation("C")` |
| `STRING-UNICODE`, `CONTAINS-LIST` | wyciszone przy Npgsql |

`PG-STARTSWITH-OPCLASS` to INFO, nie WARN, i tak ma zostać: skaner **nie zna kolacji bazy**
(to ustawienie serwera, nie kodu) i nie czyta migracji SQL. Szuka tylko tekstu
`pattern_ops`/`gin_trgm_ops`/`UseCollation("C")`/`HasOperators` w skanowanych plikach C#.
Jeśli indeks jest założony ręcznie w migracji `.sql`, reguła zaprotestuje niesłusznie — stąd
poziom INFO i komentarz `// ef-review: ignore PG-STARTSWITH-OPCLASS`.

### Skaner planów `scan_pg_plan.py` — nowy

Czyta wynik `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` (nie plan XML SQL Server, więc osobny plik):

| Reguła | Poziom | Warunek |
|---|---|---|
| `SEQ-SCAN` | WARN | Seq Scan przejrzał ≥ 10 000 wierszy, a filtr odrzucił ≥ 90% |
| `HASH-SPILL` | WARN | `Hash Batches > 1` |
| `SORT-SPILL` | WARN | `Sort Method` zawiera `external` |
| `TEMP-IO` | INFO | `Temp Written Blocks > 0` w całym planie |
| `ESTIMATE-SKEW` | INFO | estymata a rzeczywistość ≥ 10× (przy ≥ 1000 wierszy) |
| `BUDGET` | WARN | bufory współdzielone > limit z `budgets.json` |

Progi (10 000, 90%, 10×) są moje, ustalone po obejrzeniu 16 planów — nie wynikają z dokumentacji
PostgreSQL. `ESTIMATE-SKEW` **nie odpaliło na żadnym z 16 realnych planów**, więc jego test
używa planu złożonego ręcznie (opisane w kodzie testu jako fixtura reczna, nie z bazy).

## 6️⃣ 🚦 Plany w CI: bramka budżetowa

To realizacja punktu "skanowanie planów z interceptora w testach integracyjnych/CI". Interceptor
wpinasz w teście integracyjnym (`NextLabel = "nazwa_testu"`), test zapisuje `nazwa_testu.json`, a
krok CI uruchamia skaner z budżetem:

```json
{ "btree_contains": {"max_buffers": 100}, "gin_trgm_contains": {"max_buffers": 100} }
```

```
$ python3 scan_pg_plan.py --budget budgets.json btree_contains.json gin_trgm_contains.json
btree_contains.json | WARN | SEQ-SCAN | Seq Scan na customers: przejrzano 200000 wierszy, filtr zostawil 1 (odrzucono 100.0%); ...
btree_contains.json | WARN | BUDGET | 1696 buforow wspoldzielonych > budzet 100
gin_trgm_contains.json | OK | - | 17 buforow, bez uwag
(exit 1)
```

Budżet w **buforach**, nie w milisekundach, jest świadomy: bufory są deterministyczne dla tych
samych danych i planu, a milisekundy na maszynie CI skaczą (widać to w sekcji 4). To podejście
działa tylko tak długo, jak dane testowe mają rozmiar zbliżony do produkcyjnego — na 100 wierszach
Seq Scan jest tani i budżet niczego nie złapie.
Nie uruchamiałem tego w żadnym realnym pipeline (GitHub Actions/TeamCity); sprawdzony jest
wyłącznie kod wyjścia skanera, wołanego z `run_tests.py`.

## 7️⃣ ✅ Co zweryfikowano, a czego nie

| ✅ Uruchomione naprawdę | ⚠️ Niezweryfikowane / ograniczenia |
|---|---|
| .NET SDK 10.0.400, EF Core 10.0.12, Npgsql EF 10.0.0, build **0 warn / 0 err** | **Żywa sesja `claude`**: CLI jest zainstalowane w środowisku, ale uruchomienie `claude` (nawet `--version`/status logowania) zostało odrzucone przez politykę uprawnień tej sesji, więc **nic nie sprawdzałem**. Hook testowany JSON-em na stdin (2 przypadki w `run_tests.py`), nie zdarzeniem `PostToolUse` |
| PostgreSQL 16.14 w własnym kontenerze: 1 / 1 / 300 wpisów `pg_stat_statements`; bufory 1696 / 4 / 17 | Czasy to pojedyncze uruchomienia (porównanie z poprzednim przebiegiem tego samego kodu: ta sama kolejność, różne ms) |
| `run_tests.py` **40/40**: 13 fixtur dialektu, 3 kod demo, 18 planów/spójności, 4 bramka, 2 hook | Oczekiwania dla 16 planów ustalono po obejrzeniu wyników — to test regresji, nie dowód trafności progów |
| 16 planów `EXPLAIN` zapisanych przez interceptor, przepuszczonych przez `scan_pg_plan.py` | `ESTIMATE-SKEW` tylko na planie ręcznym; reguła nie wywołana na prawdziwej bazie |
| Błędy własne znalezione i naprawione: komunikaty SQL Server w projekcie Npgsql (3 reguły), narastające warianty indeksów, literał zamiast zmiennej listy | Tylko jeden kształt danych (md5 + domena), jedna tabela 200 000 wierszy, jedna kolacja (`en_US.utf8`); wpływ innych kolacji, `citext`, `ILIKE` z GIN **nie mierzony** |
| Sprzątanie: kontener `prasowka-ai-pg-1009` usunięty, baza `prasowka_ai_1009` usunięta, cudze kontenery nietknięte | Spill typu Hash w **SQL Server** (operator Hash Match, `HashSpillDetails`) — niezrobiony; zrobiłem odpowiednik PostgreSQL. Brak SQL Servera w tej sesji |
| | Koszt zapisu/rozmiar indeksu GIN (`INSERT`/`UPDATE`) — niemierzony. Dialekt wykrywany tekstowo dla całego zestawu plików (mieszany projekt SQL Server + Npgsql dostanie komunikaty jednego dialektu) |

Środowisko: Docker, obraz `postgres:16` (już lokalnie, nie pobierałem go), Python 3.10 (stdlib),
pakiety NuGet z nuget.org. Hasło w komendach jest przykładowe i jednorazowe (kontener nasłuchuje
tylko na loopbacku).

> 💡 **Wniosek:** ten sam kod C# (`Email.Contains(term)`) ma w SQL Server i w PostgreSQL ten sam
> *objaw* (pełny skan), ale **różne lekarstwo** (indeks pełnotekstowy vs `gin_trgm_ops`), a ten sam
> *niewinny* kod (`StartsWith`) jest w jednym silniku darmowy, a w drugim wymaga operatora
> indeksu. Skill, który ma być użyteczny dla zespołu, musi znać dialekt — albo uczciwie
> powiedzieć, że go nie zna. A bramka na buforach z planu `EXPLAIN` to najtańszy sposób, żeby
> wykryć regresję zapytania w CI, zanim zobaczy ją użytkownik.

Następny krok w rubryce: uruchomić hook w żywej sesji `claude` (jeśli środowisko pozwoli na
start CLI), zmierzyć spill typu Hash w SQL Server (operator Hash Match), zbadać koszt zapisu
indeksu `gin_trgm_ops` i sprawdzić `ILIKE`/`citext` na PostgreSQL.

---

<div align="center">

[← wróć do wydania #16 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
