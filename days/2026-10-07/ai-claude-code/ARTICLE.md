<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #14 — 7 października 2026

![AI](https://img.shields.io/badge/AI_%2F_Claude_Code-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![EF Core](https://img.shields.io/badge/EF_Core-10.0.12-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![SQL Server](https://img.shields.io/badge/SQL_Server_2022-CC2927?style=for-the-badge&logo=microsoftsqlserver&logoColor=white)
![Testy](https://img.shields.io/badge/run__tests.py-36%2F36-brightgreen?style=for-the-badge)

## Skill + hook `ef-core-review`: skaner EF Core, który łączy się z planem wykonania

</div>

---

> _"Skaner planu z #13 wie, że `CONVERT_IMPLICIT` jest zły. Ale plan powstaje dopiero po
> uruchomieniu zapytania. Dziś przesuwamy to o krok wcześniej: do chwili, gdy Claude zapisuje
> plik `.cs`."_

W #4, #10 i #13 zbudowaliśmy skill `sql-plan-review`: skaner T-SQL i skaner planów XML
sprawdzony na realnym SQL Server 2022. Zostawał dziura po stronie .NET: nikt nie czyta planu,
dopóki zapytanie nie jest wolne na produkcji. Dziś dokładamy brakujące ogniwo:
**`ef-core-review`** — deterministyczny skaner kodu EF Core (`scan_ef.py`), hook
`PostToolUse`, który odpala go po każdej edycji `.cs`, oraz test end-to-end: ten sam kod
wysłany na prawdziwy SQL Server i plan z cache przepuszczony przez `scan_plan.py` z #13.

---

## 1️⃣ 🎯 Dlaczego to ważne: kod wygląda niewinnie, plan nie

Pięć linii LINQ, zero wyjątków, zielone testy jednostkowe na SQLite w pamięci. A potem:

- `string` w `Where` jedzie do SQL Server jako `nvarchar`, kolumna jest `varchar` — **Index Scan
  zamiast Seek** (w #10: 57×, dziś na EF-ie: 44×),
- `foreach` z `db.Orders.Count(...)` w środku — 1 zapytanie na klientów + N na zamówienia,
- `ToList().Where(...)` — cała tabela do pamięci aplikacji,
- dwa `Include` na kolekcjach — wiersze mnożą się przez siebie.

Żaden z tych problemów nie wywala testów. Wszystkie dają się wykryć **z samego tekstu kodu**
— a to dokładnie ten rodzaj pracy, który ma sens zlecić deterministycznemu skanerowi, a nie
modelowi "na oko". Model zostaje do tego, co skaner robi słabo: ocena kontekstu i przepisanie.

## 2️⃣ 🧩 Co dokładnie jest w pakiecie

| Element | Rola |
|---|---|
| `claude-skills/ef-core-review/scan_ef.py` | skaner tekstowy, 7 reguł, tylko stdlib Pythona |
| `claude-skills/ef-core-review/SKILL.md` | instrukcja: skaner → ocena kontekstowa → format odpowiedzi |
| `claude-skills/ef-core-review/scan_plan.py` | skaner planu z #13 (bez zmian) — potwierdza regułę planem |
| `claude-hooks/ef-post-edit.py` | `PostToolUse`: WARN → exit 2 (wraca do Claude), INFO → `additionalContext` |
| `ef-demo/` | projekt .NET 10 + EF Core 10.0.12: kod "zły" i "dobry" oraz pomiary |

Reguły skanera:

| Reguła | Poziom | Co łapie |
|---|---|---|
| `N-PLUS-1` | WARN | zapytanie do `DbContext` (`Count`, `ToList`, `First...`, `Find`, `Load`) w pętli |
| `SAVECHANGES-IN-LOOP` | WARN | `SaveChanges(Async)` w pętli |
| `TOLIST-BEFORE-FILTER` | WARN | `ToList()`/`ToArray()`/`AsEnumerable()` przed `Where`/`Count`/`Any`... |
| `INCLUDE-NO-SPLIT` | WARN | ≥ 2 × `Include` bez `AsSplitQuery`/`AsSingleQuery` |
| `FUNC-ON-COLUMN` | WARN | `ToLower`/`Trim`/`Substring`/`.Year` na kolumnie w predykacie |
| `NO-ASNOTRACKING` | INFO | odczyt w metodzie, która nic nie zapisuje, bez `AsNoTracking()` |
| `STRING-UNICODE` | INFO | indeksowany `string` bez `IsUnicode(false)` / `varchar` |

## 3️⃣ 🔬 Pomiar: ile kosztuje każdy antywzorzec

Skaner bez dowodu to tylko opinia, więc każdy antywzorzec został zmierzony na prawdziwym
EF Core 10.0.12. Kod `ef-demo` ma dwie wersje każdego zapytania (`BadQueries` / `GoodQueries`).

### `string` → `nvarchar`: SQL widać bez bazy

`ToQueryString()` z providerem SqlServer **nie łączy się z bazą**, więc różnicę widać na
każdej maszynie z SDK. Prawdziwy output:

```
-- BadShopContext (Email: zwykly string):
DECLARE @email nvarchar(100) = N'user42@example.com';
...WHERE [c].[Email] = @email
-- GoodShopContext (Email: IsUnicode(false)):
DECLARE @email varchar(100) = 'user42@example.com';
...WHERE [c].[Email] = @email
-- funkcja na kolumnie (ToLower) w Where:
DECLARE @ToLower nvarchar(100) = N'user42@example.com';
...WHERE LOWER([c].[Email]) = @ToLower
```

Jedyna różnica po stronie C# to `.IsUnicode(false)` w konfiguracji modelu. A po stronie planu?

### To samo na prawdziwym SQL Server 2022

Własny, jednorazowy kontener (port tylko na `127.0.0.1`), tabela `Customers` z kolumną
`Email varchar(100)` + indeks, 50 000 wierszy. Zapytanie wysyła **EF Core** (nie ręczny
`sp_executesql`), a plan i odczyty pobieram z `sys.dm_exec_query_stats` / `dm_exec_query_plan`:

```
-- bad: wynik=1 wiersz, parametr: @email NVarChar(100)
-- good: wynik=1 wiersz, parametr: @email VarChar(100)
-- bad: logical reads (dm_exec_query_stats) = 222 przy 1 wykonaniu
-- good: logical reads (dm_exec_query_stats) = 5 przy 1 wykonaniu
```

**222 vs 5 odczytów logicznych (≈ 44×)** na jednym wyszukaniu po e-mailu. Plany przepuszczone
przez `scan_plan.py` z #13 (prawdziwy output, opisy skrócone, ścieżki do `samples/`):

```
ef_bad.xml  | WARN | SCAN             | NodeId=2 Index Scan na [Customers].[IX_Customers_Email] (tabela ~50000 wierszy, odczyt ~1) ...
ef_bad.xml  | WARN | IMPLICIT-CONVERT | Seek Plan: CONVERT_IMPLICIT(nvarchar(100),[c].[Email],0)=[@email] - niezgodnosc typow ...
ef_bad.xml  | INFO | KEY-LOOKUP       | ...
ef_good.xml | INFO | KEY-LOOKUP       | ...      (i nic więcej)
```

To zamyka pętlę z #10: wtedy parę zapytań uruchamiałem ręcznie przez `sp_executesql`, dziś
**tę parę generuje EF Core** z dwóch wariantów mapowania. Hook łapie przyczynę
(`STRING-UNICODE` w konfiguracji), plan potwierdza skutek (`IMPLICIT-CONVERT` + `SCAN`).

### Pozostałe antywzorce: liczba poleceń

SQLite in-memory (20 klientów, 200 zamówień, 160 tagów), licznik poleceń z interceptora EF
(`DbCommandInterceptor.ReaderExecuting`) i `ChangeTracker.Entries().Count()`:

```
scenariusz                            polecen  sledzonych
N+1 (zle)                                  21           0
N+1 (dobrze: Select + Count)                1           0
ToList() przed Where (zle)                  1           0
Count w SQL (dobrze)                        1           0
Include x2 bez split (zle)                  1           0
Include x2 + AsSplitQuery (dobrze)          3           0
odczyt bez AsNoTracking (zle)               1         200
odczyt z AsNoTracking (dobrze)              1           0
zapytanie z Include x2 zwraca 1600 wierszy; split query: 20 + 200 + 160 = 380
```

Dwa `Include` na kolekcjach dają **1600 wierszy** (20 klientów × 10 zamówień × 8 tagów) zamiast
380 przy split query — kosztem 3 poleceń zamiast 1. To nie jest "zawsze split": dlatego
reguła jest `WARN` do oceny, a SKILL.md każe rozróżniać jedną kolekcję od dwóch.

`SaveChanges` w pętli: SQLite nie batchuje wstawień, więc ten pomiar zrobiłem na SQL Server:

```
-- SaveChanges w petli (20 Tag): 20 polecen do SQL Server
-- jeden SaveChanges (20 Tag):   1 polecen do SQL Server
```

## 4️⃣ 🔍 Co robi skaner (i czego nie robi)

`scan_ef.py` to nie parser C#, tylko ~400 linii Pythona:

1. **Tokenizacja:** komentarze są zerowane, a treść stringów maskowana przy dopasowywaniu
   wywołań. Test: `"db.Orders.ToList().Where(...)"` w stringu i w komentarzu → cisza.
2. **Podział na instrukcje** (do `;`/`{`/`}` poza nawiasami), więc łańcuch LINQ rozbity na
   kilka linii to jedna instrukcja.
3. **Pętle:** ciało `foreach`/`for`/`while`/`do` (z klamrami albo bez). Nagłówek pętli
   wykonuje się raz, więc `foreach (var c in db.Customers.ToList())` nie jest N+1.
4. **Kontekst EF** rozpoznawany po nazwie zmiennej: `db`, `ctx`, `context`, `dbContext`,
   `*Context`, `*Db`.
5. **Konfiguracja modelu:** `HasIndex(...)` (także złożony `new { a.X, a.Y }` i atrybut
   `[Index]`) na właściwości typu `string`, bez `IsUnicode(false)`, `HasColumnType("varchar…")`
   ani `[Unicode(false)]`.
6. Wyciszanie: `// ef-review: ignore REGUŁA` w linii instrukcji albo linię wyżej.

### 🐛 Cztery błędy znalezione przez własne testy

Pierwsza wersja miała 32/36. Cztery porażki były prawdziwymi błędami skanera:

| Błąd | Przyczyna | Poprawka |
|---|---|---|
| string z antywzorcem dawał `TOLIST-BEFORE-FILTER` | maskowałem komentarze, ale nie treść stringów (ta sama lekcja co #6) | osobna wersja kodu bez treści stringów do reguł wywołań |
| `foreach` bez klamer nie dawał `N-PLUS-1` | ciało pętli to ogon **tej samej** instrukcji, a szukałem dopiero kolejnych | sprawdzenie ogona po `)` nagłówka |
| `[Unicode(false)]` na encji nie wyciszał reguły | atrybut jest w innym pliku niż `HasIndex` | konfiguracja `varchar` zbierana z plików sąsiednich |
| indeks złożony `{ Sku, Name }` → 1 znalezisko zamiast 2 | deduplikacja po (linia, reguła) | klucz deduplikacji zawiera nazwę właściwości |

Poprawka trzeciego błędu wywołała **regresję**, którą też wyłapały testy: `BadShopContext` i
`GoodShopContext` mają tę samą właściwość `Email`, więc `IsUnicode(false)` z jednego
"zasłaniało" brak w drugim. Rozwiązanie: konfigurację z plików `DbContext` bierze się tylko z
samego skanowanego pliku, a z pozostałych (encje, `IEntityTypeConfiguration`) — ze wszystkich.
To heurystyka po nazwie, nie po typie — patrz ograniczenia.

## 5️⃣ 🪝 Hook `PostToolUse`: kiedy blokować, a kiedy tylko podpowiedzieć

```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write|Edit|MultiEdit",
      "hooks": [{ "type": "command",
                  "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/ef-post-edit.py\"",
                  "timeout": 30 }]
    }]
  }
}
```

- **WARN** → stderr + `exit 2`. Claude dostaje listę i poprawia kod w tej samej turze.
- **tylko INFO** → `exit 0` i JSON `{"hookSpecificOutput": {"hookEventName": "PostToolUse",
  "additionalContext": "..."}}` — podpowiedź bez blokowania. `NO-ASNOTRACKING` i
  `STRING-UNICODE` są INFO celowo: skaner nie zna typu kolumny w bazie ani tego, czy encje
  są modyfikowane w innej metodzie.
- plik nie jest `.cs`, nie wygląda na EF Core, brak skanera lub awaria skanera → `exit 0`.
  Narzędzie pomocnicze nie ma prawa zablokować pracy.

Prawdziwy output hooka dla `BadQueries.cs` (exit 2; komunikaty skrócone, na końcu dochodzą
jeszcze dwie linie INFO `NO-ASNOTRACKING` z linii 17 i 51; payload JSON na stdin):

```
EF-REVIEW: 5 problem(ow) w BadQueries.cs po ostatniej edycji:
  BadQueries.cs:17 [WARN] FUNC-ON-COLUMN: `.ToLower()` na kolumnie w predykacie ...
  BadQueries.cs:26 [WARN] N-PLUS-1: zapytanie do bazy wewnatrz petli `foreach` (N+1): `var n = db.Orders.Count(o => o.CustomerId == c.Id);` ...
  BadQueries.cs:35 [WARN] TOLIST-BEFORE-FILTER: `.ToList()` przed `.Where()` ...
  BadQueries.cs:41 [WARN] INCLUDE-NO-SPLIT: 2 x Include w jednym zapytaniu bez AsSplitQuery/AsSingleQuery ...
  BadQueries.cs:60 [WARN] SAVECHANGES-IN-LOOP: SaveChanges w petli `foreach` ...
Popraw je albo, jesli to swiadoma decyzja, dodaj komentarz `// ef-review: ignore REGULA` nad instrukcja.
```

## 6️⃣ ✅ Co zweryfikowano, a czego nie

| ✅ Uruchomione naprawdę | ⚠️ Niezweryfikowane / ograniczenia |
|---|---|
| .NET SDK 10.0.400, EF Core 10.0.12 (SqlServer + Sqlite), build **0 warn / 0 err** | **Żywa sesja `claude`**: hook testowany przez pipe JSON na stdin (9 przypadków), nie przez prawdziwe zdarzenie `PostToolUse` |
| SQL z `ToQueryString()` dla `nvarchar` / `varchar` / `LOWER(...)` (bez bazy) | Dokładny kształt `additionalContext` z dokumentacji, nie sprawdzony w żywej sesji; skill nie był auto-aktywowany |
| Własny kontener SQL Server 2022: **222 vs 5** logical reads, plany z cache → `scan_plan.py` daje `IMPLICIT-CONVERT`+`SCAN` vs cisza | To plany **kompilacyjne z cache** (bez `ActualRows`), jedno zapytanie, jedna tabela 50k wierszy; ratio zależy od danych |
| 20 poleceń vs 1 przy `SaveChanges` w pętli (SQL Server) | `FUNC-ON-COLUMN`, `TOLIST-BEFORE-FILTER`, `NO-ASNOTRACKING` zmierzone tylko jako liczba poleceń/encji lub tekst SQL, nie planem |
| `run_tests.py` **36/36**: 5 kod demo, 20 fixtur, 2 plany, 9 hooka | Skaner jest tekstowy: kontekst EF po nazwie zmiennej (`repo.Orders.ToList().Where(...)` **nie** jest wykrywane — to zapisana w teście znana luka), typy `string` i konfiguracja `varchar` dopasowywane po nazwie właściwości, nie po typie encji |
| Sprzątanie: kontener `prasowka-ai-mssql-1007` usunięty, baza `PrasowkaAiEf1007` usunięta, `bin/obj` skasowane | Wiersze w sekcji SQLite: nie wyciągam wniosków o czasie, tylko o liczbie poleceń; `DataReaderDisposing.ReadCount` odrzuciłem jako miarę — liczy końcowy `Read()` i dla split query zwracał 0 dla zapytań zależnych |

Środowisko: Docker, obraz `mcr.microsoft.com/mssql/server:2022-latest` (już lokalnie obecny,
nie pobierałem go), Python 3.10 (stdlib), pakiety NuGet z nuget.org. Nie dotknięto cudzych
kontenerów, obrazów ani baz.

> 💡 **Wniosek:** skaner kodu i skaner planu są komplementarne. Pierwszy jest tani i działa
> przy zapisie pliku, ale zgaduje (kontekst po nazwie, typ kolumny z konfiguracji). Drugi
> jest pewny, ale potrzebuje bazy i uruchomionego zapytania. Skill, który pokazuje oba
> na jednym przykładzie, uczy modelu **czego szukać** i **jak to potwierdzić**.

Następny krok w rubryce: wypróbować hook w żywej sesji `claude` (pierwsze realne zdarzenie
`PostToolUse`), dodać do skilla krok "wygeneruj plan z aplikacji" (interceptor + cache planów)
oraz dopisać reguły dla `Contains` na dużych listach i `string.Contains` → `LIKE '%x%'`.

---

<div align="center">

[← wróć do wydania #14 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
