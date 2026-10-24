<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #15 — 8 października 2026

![AI](https://img.shields.io/badge/AI_%2F_Claude_Code-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![EF Core](https://img.shields.io/badge/EF_Core-10.0.12-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![SQL Server](https://img.shields.io/badge/SQL_Server_2022-CC2927?style=for-the-badge&logo=microsoftsqlserver&logoColor=white)
![Testy](https://img.shields.io/badge/run__tests.py-65%2F65-brightgreen?style=for-the-badge)

## `ef-core-review` v2: LIKE '%x%', `Contains` na listach — i plan zapytania prosto z aplikacji

</div>

---

> _"Skaner z #14 umiał ostrzec, że `ToLower()` zabija indeks. Nie umiał ostrzec, że
> `Email.Contains(term)` robi to samo — bo to wygląda jak niewinny `string.Contains`."_

W #14 zostawiłem sobie cztery długi: reguły dla `Contains` na listach i dla `LIKE '%x%'`,
dopasowanie po typie zamiast po nazwie zmiennej i krok "wygeneruj plan z aplikacji". Dziś
spłacam trzy z czterech (czwarty — żywa sesja `claude` — nadal czeka, patrz sekcja 6).
Każda nowa reguła ma pomiar na prawdziwym SQL Server 2022, a nie tylko "bo tak się mówi".

---

## 1️⃣ 🎯 Dlaczego to ważne: dwa niewinne wyrażenia LINQ, które nie pasują do indeksu

```csharp
db.Customers.Where(c => c.Email.Contains(term))     // wygląda jak string.Contains w pamięci
db.Customers.Where(c => ids.Contains(c.Id))         // wygląda jak sprawdzenie członkostwa
```

Pierwsze to w SQL `LIKE '%…%'` — wiodący wildcard, więc indeks po `Email` nie służy jako
Seek. Drugie to `IN (…)`, którego **kształt zależy od rozmiaru listy**: inny rozmiar to inny
tekst SQL, a więc potencjalnie inny wpis w plan cache. Oba przechodzą testy jednostkowe na
SQLite, oba są w 100% poprawne funkcjonalnie, oba wychodzą dopiero jako wolne zapytanie albo
rozrośnięty plan cache na produkcji.

## 2️⃣ 🔬 Pomiar 1: `LIKE '%x%'` na indeksowanej kolumnie

Tabela `Customers`, `Email varchar(100)` + indeks, 50 000 wierszy, własny kontener SQL Server
2022. Cztery zapytania z `Queries.cs`, **z parametrem** (jak w prawdziwej aplikacji), odczyty
z `sys.dm_exec_query_stats` po wyczyszczeniu cache planów:

```
zapytanie     wierszy  logical reads   WHERE w SQL
eq                  1              5   WHERE [c].[Email] = @email
startswith         11             25   WHERE [c].[Email] LIKE @prefix_startswith ESCAPE '\'
contains            1            371   WHERE [c].[Email] LIKE @term_contains ESCAPE '\'
endswith           50            371   WHERE [c].[Email] LIKE @suffix_endswith ESCAPE '\'
```

`Contains` i `EndsWith` czytają **371 stron zamiast 5–25**. `StartsWith` jest sargowalne — to
nadal zakres w indeksie. I jedna uczciwa uwaga: w roboczym przebiegu, w którym fraza szła
literałem (nie parametrem), `Contains` dało 222 odczyty (Index Scan po indeksie), a `EndsWith`
320. Wartość "371" to wynik planu wybranego dla parametru na tych danych, nie stała natury.
Stała jest zasada: z wiodącym wildcardem nie ma Seek.

### Plan prosto z aplikacji: `PlanCaptureInterceptor`

Dotąd plany do `scan_plan.py` brałem ręcznie. Teraz robi to `DbCommandInterceptor` (około 60
linii): po wykonaniu zapytania sięga do `sys.dm_exec_query_plan`, szukając tekstu polecenia EF,
i zapisuje plan jako `.xml`. Dev ustawia `interceptor.NextLabel = "contains"` przed zapytaniem —
jedno zapytanie, jeden plik. Wyniki dla czterech zapytań, przepuszczone przez `scan_plan.py`
(opisy skrócone):

```
like_eq.xml         | INFO | KEY-LOOKUP | NodeId=3 Clustered Index Seek na [Customers].[PK__...] (~1 wierszy) ...
like_startswith.xml | INFO | KEY-LOOKUP | NodeId=6 Clustered Index Seek na [Customers].[PK__...] (~1 wierszy) ...
like_contains.xml   | WARN | SCAN       | NodeId=0 Clustered Index Scan na [Customers].[PK__...] (tabela ~50000 wierszy, odczyt ~4500) ...
like_endswith.xml   | WARN | SCAN       | NodeId=0 Clustered Index Scan na [Customers].[PK__...] (tabela ~50000 wierszy, odczyt ~4500) ...
```

Skaner planu z #13 nie wymagał żadnej zmiany: dostał plan, którego nikt nie wklejał ręcznie.

> 🪤 **Pułapka (zmierzona):** pierwsze dwie wersje interceptora używały `SET SHOWPLAN_XML ON`.
> Wariant 1 (to samo polecenie z parametrami, jako RPC): 0 zapisanych plików, nie badałem
> dlaczego. Wariant 2 (zwykły batch `EXEC sp_executesql N'…', N'@p varchar(100)', @p = '…'`):
> plik powstał, ale zawierał jeden `StmtSimple` z `StatementType="EXECUTE PROC"` i **zero
> operatorów `RelOp`** — plan zapytania wewnątrz `sp_executesql` nie wchodzi do planu
> szacowanego, więc skaner nie miał czego czytać. Stąd odczyt z cache planów po wykonaniu: to
> plan, który silnik naprawdę skompilował dla wartości parametru z tego wywołania. Koszt:
> wymaga `VIEW SERVER STATE`, plan jest kompilacyjny (bez `ActualRows`).

## 3️⃣ 🔬 Pomiar 2: `ids.Contains(...)` — co EF Core 10 robi z listą

Najpierw bez bazy, bo `ToQueryString()` z providerem SqlServer nie łączy się z serwerem.
Liczba parametrów (`DECLARE`) w SQL dla list o rozmiarach 1, 2, 5, 6, 9, 17, 100, … 2200:

```
tryb domyslny               1->1 2->2 5->5 6->10 9->10 17->20 100->100 500->500 1000->1000 2000->2000 2100->1 2200->1
tryb Parameter (OPENJSON)   1->1 2->1 5->1 6->1 9->1 17->1 100->1 500->1 1000->1 2000->1 2100->1 2200->1
tryb Constant               1->0 2->0 5->0 6->0 9->0 17->0 100->0 500->0 1000->0 2000->0 2100->0 2200->0
```

Domyślnie EF 10 wysyła **jeden parametr na element**, a rozmiar listy dopełnia do "wiaderka"
(5→5, 6→10, 9→10, 17→20, a 100→100 — tak wynika z zmierzonej liczby parametrów; samego algorytmu
wiaderek nie czytałem w kodzie EF), co ogranicza liczbę różnych kształtów SQL. Od 2100 elementów (limit parametrów SQL Server) sam przechodzi na jeden parametr JSON.
Tryb `Parameter` to zawsze jeden parametr z `OPENJSON`:

```sql
DECLARE @ids nvarchar(4000) = N'[10,20,30]';
SELECT ... WHERE [c].[Id] IN (SELECT [i].[value] FROM OPENJSON(@ids) WITH ([value] int '$') AS [i])
```

Co to daje w plan cache? 300 zapytań, każde z listą innego rozmiaru (1…300), cache planów
czyszczony przed każdym trybem (prawdziwy SQL Server, jedno uruchomienie):

```
domyslny                   wpisow w plan cache:   23   czas 300 zapytan: 2526 ms
Parameter (OPENJSON)       wpisow w plan cache:    1   czas 300 zapytan: 1060 ms
Constant                   wpisow w plan cache:  301   czas 300 zapytan: 5262 ms
EF.Constant(ids) w kodzie  wpisow w plan cache:  301   czas 300 zapytan: 4498 ms
```

I jedna lista 5000 elementów w każdym trybie:

```
domyslny               SQL: 1 DECLARE, 24112 znakow; wynik=5000, 82 ms
Parameter (OPENJSON)   SQL: 1 DECLARE, 24092 znakow; wynik=5000, 29 ms
Constant               SQL: 0 DECLARE, 28976 znakow; wynik=5000, 955 ms
```

Wnioski, w kolejności od najpewniejszego:

1. **`Constant` to zawsze zły pomysł dla list o zmiennej zawartości**: 301 planów zamiast 1 i
   ~30× wolniej dla 5000 elementów. `EF.Constant(ids)` ma identyczny efekt dla jednego zapytania
   (301 wpisów) — stąd reguła `CONTAINS-CONSTANT` jako **WARN**.
2. **Domyślny tryb jest rozsądny** (23 wpisy zamiast 300), więc zwykłe `ids.Contains(c.Id)`
   dostaje tylko **INFO** (`CONTAINS-LIST`): pytanie o rozmiar i zmienność listy, nie nakaz.
3. **Tryb `Parameter` wygrywa przy listach o zmiennej długości** (1 plan), ale to ustawienie
   całej aplikacji — nie wybieraj go "na oko", zmierz własne zapytania.

> 🪤 **Druga pułapka (zmierzona):** porównując tryby w jednym procesie dostałem trzy identyczne
> wiersze. Dopiero osobne uruchomienie tylko z trybem `Constant` pokazało `IN (10, 20, 30)`.
> Najprostsze wyjaśnienie, które pasuje do obserwacji (nie czytałem kodu EF): skompilowane
> zapytanie siedzi w cache współdzielonym przez konteksty o tym samym dostawcy usług, więc
> **pierwszy użyty tryb wygrywa w całym procesie**. Surowy output z pierwszej wersji demo
> (dostawca usług z cache, domyślnie):
>
> ```
> tryb domyslny               rozmiar listy -> liczba DECLARE: 1->1 2->2 3->3 4->4 5->5 6->10 7->10 8->10 9->10 17->20 100->100
> tryb Parameter (OPENJSON)   rozmiar listy -> liczba DECLARE: 1->1 2->2 3->3 4->4 5->5 6->10 7->10 8->10 9->10 17->20 100->100
> tryb Constant               rozmiar listy -> liczba DECLARE: 1->1 2->2 3->3 4->4 5->5 6->10 7->10 8->10 9->10 17->20 100->100
> ```
>
> Po wyłączeniu cache dostawcy wiersze się różnią (patrz wyżej). Dlatego `Opts()` w demo wywołuje `EnableServiceProviderCaching(false)`. W aplikacji tryb
> ustawia się raz, więc to dotyczy tylko porównań — i testów jednostkowych, które zmieniają tryb.
> Drobiazg nazewniczy, na który wpadł kompilator: enum nazywa się `ParameterTranslationMode`,
> ale metoda opcji — `UseParameterizedCollectionMode`.

## 4️⃣ 🧩 Co dokłada skaner v2

| Reguła | Poziom | Co łapie |
|---|---|---|
| `LIKE-LEADING-WILDCARD` | WARN | `x.Kol.Contains(..)` / `EndsWith(..)` / `EF.Functions.Like(x.Kol, "%..")` na kolumnie **string z indeksem** |
| `CONTAINS-CONSTANT` | WARN | `EF.Constant(lista)` albo `ParameterTranslationMode.Constant` |
| `CONTAINS-LIST` | INFO | `lista.Contains(x.Kol)` — jeden parametr/element do 2100, potem JSON |

Dwie decyzje, które wynikają z pomiarów, a nie z intuicji:

- **`LIKE-LEADING-WILDCARD` tylko dla kolumn z indeksem.** `Note.Contains(t)` na kolumnie bez
  indeksu i tak skanuje — ostrzeżenie byłoby szumem, a hook blokuje przy WARN. Wymaga to wiedzy
  o modelu, więc skaner zbiera indeksy z `HasIndex` / `[Index]`.
- **Nawigacje nie są kolumnami.** `c.Orders.Contains(x)` to kolekcja, nie `LIKE`; reguła
  odpala tylko wtedy, gdy właściwość jest typu `string` w danej encji (nawigacja `Orders` nie jest).

### Dopasowanie po typie, nie po nazwie zmiennej

Luka z #14: `repo.Orders.ToList().Where(...)` przechodziło bez uwag, bo `repo` nie jest `db`.
Teraz skaner buduje mały model z całego skanowanego zestawu plików: mapę `DbSet<T> Nazwa → T`,
wlasciwości `string` per encja, indeksy per encja (z najbliższego `Entity<T>` albo klasy po
`[Index]`). Zmienna jest "kontekstem EF", gdy ma zadeklarowany typ (`Repo repo`,
`private readonly ShopCtx _store`), którego nazwa kończy się na `Context`/`Repository`/`Repo`/
`UnitOfWork`/`Uow`/`Db`/`Store` (albo dziedziczy po `DbContext`), a członek jest właściwością
`DbSet`. Efekt w testach:

| Fixtura | Wynik |
|---|---|
| `Repo repo` + `repo.Orders.ToList().Where(..)` | `TOLIST-BEFORE-FILTER` (dawna "znana luka") |
| pole `ShopCtx _store` | `TOLIST-BEFORE-FILTER` |
| `Repo repo` w `foreach` z `FirstOrDefault` | `N-PLUS-1` |
| `Thing thing` (typ bez nazwy kontekstowej) | cisza |
| parametr `Cust c` → `c.Orders.Count()` w pętli | cisza (nawigacja, nie DbSet) |
| `var c` z `foreach` po `db.Customers` | cisza |
| `Email.Contains` na `Cust` (indeks) vs na `Ord` (ta sama nazwa `Email`, brak indeksu) | WARN vs cisza |

Ostatni wiersz to sedno "po typie": w #14 ta sama nazwa właściwości na dwóch encjach była
nierozróżnialna.

## 5️⃣ 🐛 Błędy znalezione własnymi testami

Pierwsze pełne uruchomienie: **62/65**. Trzy porażki:

| Błąd | Przyczyna | Poprawka |
|---|---|---|
| dwa testy `STRING-UNICODE` — cisza zamiast znaleziska | **błąd harnessu**, nie skanera: po refaktoryzacji `scan_text` skanował tylko pierwszy plik z pary encja+kontekst | skanowanie wszystkich plików, gdy nie ma `a.cs` |
| `Email.Contains` na encji `Ord` ostrzegało, choć indeks jest tylko na `Cust` | **realny błąd skanera**: `HasIndex` w łańcuchu `b.Entity<Cust>().HasIndex(..)` leży w tej samej instrukcji co `Entity<Cust>`, a ja porównywałem pozycję `Entity` z *początkiem* instrukcji — typ encji wychodził pusty i indeks lądował w worku "bez typu" | porównanie z *końcem* instrukcji |

Drugi błąd to dobry przykład, dlaczego test "ta sama nazwa właściwości na dwóch encjach"
musiał powstać: bez niego skaner działałby po cichu jak w #14 (po nazwie) i nikt by nie
zauważył, że "dopasowanie po typie" jest martwym kodem.

## 6️⃣ ✅ Co zweryfikowano, a czego nie

| ✅ Uruchomione naprawdę | ⚠️ Niezweryfikowane / ograniczenia |
|---|---|
| .NET SDK 10.0.400, EF Core 10.0.12, build **0 warn / 0 err** | **Żywa sesja `claude`**: hook testowany plikiem/pipe JSON na stdin (11 przypadków), nie prawdziwym zdarzeniem `PostToolUse`; skill nie był auto-aktywowany; `claude` CLI nie uruchamiałem |
| Własny kontener SQL Server 2022: odczyty **5 / 25 / 371 / 371** (eq / StartsWith / Contains / EndsWith) | Czasy (2.5 s / 1.1 s / 5.3 s; 82 / 29 / 955 ms) to pojedyncze uruchomienia; wcześniejsze przebiegi tego samego kodu: 2.4–2.9 s, 1.0–1.2 s, 5.2–5.4 s. Wiarygodny jest rząd wielkości; wpisy w cache i odczyty są deterministyczne |
| Plan cache dla 300 rozmiarów listy: **23 / 1 / 301 / 301** | Nie badałem, co jest "301." wpisem w trybie `Constant` (300 zapytań + 1) |
| `scan_plan.py` bez zmian logiki na planach z interceptora: SCAN tylko dla Contains/EndsWith | Plany kompilacyjne z cache (bez `ActualRows`), jedno zapytanie, jedna tabela 50 000 wierszy |
| `run_tests.py` **65/65**: regresja #14, kod ef-plan-demo, 19+21 fixtur, 4 plany + spójność kod↔plan, 11 hooka | Skaner jest tekstowy: typ zmiennej to deklaracja `Typ nazwa` w tym samym pliku; nie obsługuje `var`, primary constructors, dziedziczenia ani konfiguracji `IEntityTypeConfiguration` w innym katalogu; `STRING-UNICODE` nadal po nazwie właściwości |
| Spójność: metody oznaczone `LIKE-LEADING-WILDCARD` w kodzie = zapytania, których **plan** ma SCAN | Tylko SQL Server; PostgreSQL/SQLite tłumaczą `Contains` na listach inaczej i nie były mierzone |
| Sprzątanie: kontener `prasowka-ai-mssql-1008` usunięty, baza `PrasowkaAiPlan1008` usunięta, `bin/obj` skasowane | Zmienne środowiskowe w poleceniach były odrzucane — connection string idzie argumentem `--sqlserver` |

Środowisko: Docker, obraz `mcr.microsoft.com/mssql/server:2022-latest` (już lokalnie, nie
pobierałem go), Python 3.10 (stdlib), pakiety NuGet z nuget.org. Nie dotknięto cudzych
kontenerów, obrazów ani baz.

> 💡 **Wniosek:** reguła, która ostrzega bez pomiaru, jest opinią. Reguła, która ma obok
> plan z prawdziwego silnika i liczbę odczytów, jest argumentem — a model w skillu dostaje
> oba i może powiedzieć deweloperowi nie tylko *co* zmienić, ale *ile to kosztuje*. Najciekawszy
> wniosek dnia jest jednak negatywny: `ids.Contains(...)` w domyślnym trybie EF 10 jest
> rozsądne (23 wpisy zamiast 300) i reguła dla niego to tylko INFO. Skaner, który wszystko
> oznacza na czerwono, uczy ignorować hook.

Następny krok w rubryce: wypróbować hook w żywej sesji `claude` (pierwsze realne zdarzenie
`PostToolUse`), dołożyć do skilla krok "uruchom `PlanCaptureInterceptor` w testach
integracyjnych i skanuj plany w CI" oraz zmierzyć `Contains` na PostgreSQL (nie wiem, jak dokładnie Npgsql
tłumaczy listy — to do sprawdzenia, nie założenia).

---

<div align="center">

[← wróć do wydania #15 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
