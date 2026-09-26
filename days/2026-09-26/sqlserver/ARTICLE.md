<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #3 — 26 września 2026

![SQL Server](https://img.shields.io/badge/SQL_Server-CC2927?style=for-the-badge&logo=microsoftsqlserver&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)
![Zweryfikowane](https://img.shields.io/badge/kod-uruchomiony_na_SQL_Server_2022_CU27-brightgreen?style=for-the-badge)

## Leczenie parameter sniffingu: RECOMPILE, OPTIMIZE FOR, Query Store i filtered index

</div>

---

> _"Wczoraj znaleźliśmy pułapkę. Dziś pokażemy trzy sposoby wyjścia z niej — i
> jeden, który nie wymaga nawet dotykania kodu aplikacji."_

**🎣 Dlaczego to ważne:** w #2 ta sama procedura raz czytała **21**, raz **600 350**
stron. Wiesz już *dlaczego*. Ale w piątek o 16:00 nikt nie pyta "dlaczego" — pyta
"jak to naprawić **teraz**, bez wdrożenia?". Dziś odpowiedź: **Query Store** potrafi
przypiąć dobry plan jednym poleceniem, bez zmiany ani linijki C#. A na deser:
indeks, który zamiast 1 051 stron ma **2**.

Wszystkie liczby pochodzą z **realnego uruchomienia** kodu z [`code/`](code/) na
`mcr.microsoft.com/mssql/server:2022-latest` (SQL Server 2022 RTM-CU27, 16.0.4295.3,
Developer Edition on Linux). Tabela `dbo.Orders` jest ta sama co wczoraj: 500 000
wierszy, klient 1 ("hurtownik") ma 200 000, klient 4242 ma 6.

---

## 1️⃣ Leczenie w kodzie: cztery warianty tej samej procedury

Procedura z #2 (`SELECT COUNT(*), SUM(Amount), MAX(OrderDate) ... WHERE CustomerId = @CustomerId`)
w czterech wersjach. Scenariusz zawsze ten najgorszy: czysty plan cache, **pierwszy
wchodzi rzadki klient (4242), potem hurtownik (1)**.

| Wariant | Co robi z planem | 4242 | Hurtownik (1) |
|---|---|---:|---:|
| bez leczenia | plan pod pierwszą wartość (Seek + Lookup) | 21 | **600 350** 🔥 |
| `OPTION (RECOMPILE)` | nowy plan przy każdym wywołaniu | 21 | 2 486 |
| `OPTIMIZE FOR UNKNOWN` | plan pod "przeciętnego" klienta | 21 | **600 350** 🔥 |
| `OPTIMIZE FOR (@CustomerId = 1)` | plan zawsze pod hurtownika | 2 486 | 2 486 |

(logical reads dla tabeli `Orders`, prawdziwy output z `STATISTICS IO`)

### 🔁 `OPTION (RECOMPILE)` — precyzyjny, ale płacisz za każde wywołanie

Optymalizator widzi **konkretną wartość** i dobiera idealny plan: 21 i 2 486. Cena:
kompilacja przy każdym wywołaniu. Zmierzyliśmy ją: 2 000 wywołań rzadkiego klienta
trwało **574 ms** bez RECOMPILE i **5 414 ms** z nim (w innym przebiegu 199 ms vs
4 538 ms — czasy się wahają, proporcja ~10× nie). To ~2,7 ms samej kompilacji na
wywołanie: OK dla raportu raz na minutę, zabójcze dla endpointu wołanego tysiące razy
na sekundę.

### ❓ `OPTIMIZE FOR UNKNOWN` — pułapka, którą wiele osób bierze za lekarstwo

Brzmi jak "ignoruj sniffing". Faktycznie optymalizator używa **średniej gęstości**,
a nie histogramu. Tu: 500 000 wierszy / ~50 000 klientów ≈ **10 wierszy** (prawdziwy
`EstimateRows = 10.0` w planie). Dla 10 wierszy Seek + Lookup jest idealny, więc
dostajemy... dokładnie ten sam plan co w scenariuszu z pechowym sniffingiem, tylko
teraz **zawsze**. Hurtownik: 600 350 stron, deterministycznie.

> ⚠️ `OPTIMIZE FOR UNKNOWN` daje **przewidywalność**, nie **dobry plan**. Przy
> mocno skośnych danych przewidywalnie zły to wciąż zły.

### 🎯 `OPTIMIZE FOR (@CustomerId = 1)` — świadomy kompromis

Plan zawsze pod hurtownika (skan): najgorszy przypadek jest ograniczony (2 486), ale
rzadki klient płaci 2 486 zamiast 21 (118× więcej). Sensowne, gdy **koszt najgorszego
przypadku** jest ważniejszy niż średnia — np. gdy 600 350 stron kładzie serwer.

> 💡 **Dla .NET-owca:** to jak wybór między `AsNoTracking()` a domyślnym trybem —
> nie ma "najlepszej" opcji, jest kompromis, który musisz świadomie wybrać. Dodatkowo
> SQL Server 2022 ma "Parameter Sensitive Plan optimization" (PSP), ale w naszym
> teście na tej bazie **nie zadziałała** dla tego zapytania (plan nadal jeden,
> 600 350 odczytów) — nie licz na nią jako na lekarstwo; dlaczego akurat nie —
> nie badaliśmy.

---

## 2️⃣ Leczenie bez dotykania kodu: Query Store

**Query Store** to wbudowana "czarna skrzynka" bazy: zapisuje **teksty zapytań,
wszystkie ich plany i statystyki wykonania** w bazie (przetrwa restart, w przeciwieństwie
do plan cache). Włączenie to jedno polecenie:

```sql
ALTER DATABASE PrasowkaQS SET QUERY_STORE = ON
    (OPERATION_MODE = READ_WRITE, QUERY_CAPTURE_MODE = ALL,
     INTERVAL_LENGTH_MINUTES = 1, DATA_FLUSH_INTERVAL_SECONDS = 60);
```

(Na produkcji zwykle zostawia się `QUERY_CAPTURE_MODE = AUTO` i dłuższy interwał —
`ALL` i 1 minuta to ustawienia dla demo, żeby dane pojawiły się szybko.)

Widoki, które musisz znać:

| Widok | Co zawiera |
|---|---|
| `sys.query_store_query` | jeden wiersz na zapytanie (`query_id`), powiązanie z procedurą (`object_id`) |
| `sys.query_store_query_text` | tekst SQL |
| `sys.query_store_plan` | **każdy plan** tego zapytania (`plan_id`), XML planu, `is_forced_plan` |
| `sys.query_store_runtime_stats` | statystyki per plan i per interwał: czas, logical reads, liczba wykonań |

Odtwarzamy pechowy scenariusz z #2: najpierw plan skompilowany pod rzadkiego (i użyty
na hurtowniku 2×), potem "restart" (`CLEAR PROCEDURE_CACHE`) i hurtownik wchodzi
pierwszy (3×). Query Store widzi **jedno zapytanie i dwa plany**:

```
query_id plan_id is_forced_plan Wykonan AvgLogicalReads AvgDurationMs RodzajPlanu
       2       2              0       3          400240         560.1 Seek + Key Lookup
       2       3              0       3            2486          69.2 Clustered Index Scan
```

To jest **regresja planu** pokazana w liczbach: ten sam kod, ten sam `query_id`,
a plan 2 jest średnio **161× droższy w odczytach** i **8× wolniejszy** (560 ms vs
69 ms) w tym obciążeniu. (Średnia 400 240 to ważona: (21 + 2×600 350) / 3.)
Zawodowo szukasz tego w SSMS w raportach "Regressed Queries" / "Top Resource
Consuming Queries" — my patrzymy prosto w widoki (raportów SSMS tu nie uruchamialiśmy).

### 📌 Wymuszenie planu

```sql
EXEC sys.sp_query_store_force_plan @query_id = 2, @plan_id = 3;
```

Od teraz optymalizator przy kompilacji tego zapytania używa planu 3. Test: czyścimy
cache, znowu **rzadki wchodzi pierwszy** (dokładnie ten scenariusz, który wcześniej
dał 600 350):

```
--- po force: rzadki (4242) pierwszy
Table 'Orders'. Scan count 1, logical reads 2486
--- po force: hurtownik (1)
Table 'Orders'. Scan count 1, logical reads 2486
```

**Hurtownik: 2 486 zamiast 600 350** — bez zmiany kodu i bez wdrożenia. Ale
zauważ cenę: rzadki klient płaci teraz 2 486 zamiast 21. Wymuszenie to **wybór
jednego planu dla wszystkich parametrów**, więc działa jak `OPTIMIZE FOR` z wnętrza
Query Store. Dopóki dobrego planu na hurtownika nie ma czym zastąpić, to wciąż
świetne gaszenie pożaru.

Ostrożność z wymuszaniem, o której mówi dokumentacja (tu niezweryfikowane
eksperymentem): jeśli wymuszony plan przestanie być możliwy (np. zniknie indeks),
wymuszenie **zawodzi po cichu** i optymalizator kompiluje nowy plan — dlatego w
`sys.query_store_plan` są kolumny `force_failure_count` i `last_force_failure_reason_desc`
(u nas: 0 i `NONE`). Wymuszenie zdejmujesz `sp_query_store_unforce_plan`.

> 📎 SQL Server 2022 dodał też **Query Store hints** (`sp_query_store_set_hints`) —
> wstrzyknięcie `OPTION (RECOMPILE)` lub `OPTIMIZE FOR` do zapytania *bez zmiany
> kodu*. Nie uruchamialiśmy tego w demo, wspominam jako kierunek do sprawdzenia.

---

## 3️⃣ Filtered index — indeks tylko na tym, co ważne

Klasyk: **kolejka zadań**. Tabela `dbo.Tasks` ma 500 000 wierszy, ale tylko **500** to
zadania oczekujące (`Status = 0`), reszta jest zrobiona. Aplikacja ciągle pyta:
"daj mi 10 najstarszych oczekujących".

```sql
SELECT TOP (10) TaskId, CreatedAt FROM dbo.Tasks WHERE Status = 0 ORDER BY CreatedAt;
```

| Wariant | Logical reads | Rozmiar indeksu (strony) |
|---|---:|---:|
| (a) bez indeksu (skan tabeli, plan równoległy) | **6 846** | — |
| (b) zwykły `(Status, CreatedAt)` | 3 | **1 051** (500 000 wierszy) |
| (c) filtered `(CreatedAt) WHERE Status = 0` | **2** | **2** (500 wierszy) |

```sql
CREATE NONCLUSTERED INDEX IX_Tasks_Pending ON dbo.Tasks (CreatedAt) WHERE Status = 0;
```

Oba indeksy odpowiadają błyskawicznie (3 vs 2 odczyty), ale filtered ma **500 razy
mniej wierszy i ~525× mniej stron**. Miejsce to nie jedyna korzyść: taki indeks
trzeba aktualizować **tylko** przy zmianach wierszy z `Status = 0`; zwykły pilnuje
wszystkich 500 000. (Kosztu zapisu nie mierzyliśmy w demo — to wniosek z definicji
indeksu, nie z benchmarku.) Uwaga: 6 518 w wyniku (b) w surowym outpucie to koszt
*budowy* indeksu (skan tabeli przy `CREATE INDEX` przy włączonym `STATISTICS IO`),
nie zapytania.

### 🪤 Pułapka: parametry

W .NET prawie zawsze wołasz zapytanie z parametrem (`WHERE Status = @s`). Optymalizator
kompiluje plan **bez pewności**, że `@s` będzie zawsze 0 — a filtered index nie zawiera
wierszy `Status = 1`, więc plan z nim byłby błędny dla `@s = 1`. Efekt (prawdziwy):

```
(d) sp_executesql ... WHERE Status = @s             -> logical reads 6846   (indeks pominięty)
(e) to samo + OPTION (RECOMPILE)                    -> logical reads 2      (indeks użyty)
```

Wnioski dla praktyki: dla filtered indexów **wpisz stałą w zapytaniu** (`Status = 0`
jako literał w LINQ/SQL) albo dodaj `OPTION (RECOMPILE)` — i wróciliśmy do tematu
z punktu 1. Sprawdź plan, zanim uznasz, że indeks "działa".

---

## 🧾 Ściąga na dziś

| Pojęcie | Jedno zdanie |
|---|---|
| `OPTION (RECOMPILE)` | nowy, idealny plan co wywołanie; ~10× wolniej na samej kompilacji (u nas) |
| `OPTIMIZE FOR UNKNOWN` | plan pod średnią gęstość (u nas: 10 wierszy) — przewidywalny, niekoniecznie dobry |
| `OPTIMIZE FOR (@p = x)` | plan zawsze pod wybraną wartość; kompromis worst-case |
| Query Store | trwały zapis zapytań, planów i statystyk w bazie (`sys.query_store_*`) |
| Regresja planu | to samo `query_id`, dwa plany, jeden dramatycznie gorszy |
| `sp_query_store_force_plan` | przypina plan bez zmiany kodu aplikacji |
| Filtered index | indeks tylko na podzbiorze wierszy (`WHERE`): mały i tani, ale wrażliwy na parametry |

**Pełny, uruchamialny kod + komendy:** [`code/README.md`](code/README.md).

**Co dalej:** columnstore (analityka na milionach wierszy) oraz blokady i deadlocki —
dziś ich nie ruszaliśmy.

---

## ✅ Status weryfikacji

Kod uruchomiony realnie: kontener `mcr.microsoft.com/mssql/server:2022-latest`
(SQL Server 2022 RTM-CU27, 16.0.4295.3), skrypty `01`–`05` wykonane po kolei przez
`sqlcmd` (`-C -b -I`) z wnętrza kontenera (pliki skopiowane `docker cp`). Wszystkie
liczby powyżej pochodzą z tego uruchomienia. Skrypty `02` i `05` po drobnych
poprawkach (wyciszenie outputu pętli, `TOP (10)`, `DROP INDEX IF EXISTS`) uruchomiono
ponownie w finalnej postaci; `01`, `03` i `04` w finalnej.

Uczciwe uwagi:

1. `run-demo.sh` jako całość **nie został odpalony** — te same kroki wykonano ręcznie.
   `06-cleanup.sql` też nie był uruchamiany (kontener usunięto w całości).
2. Czasy (ms) wahają się między przebiegami; logical reads są deterministyczne.
3. **Niezweryfikowane:** zachowanie wymuszonego planu po zniknięciu indeksu, Query
   Store hints, raporty SSMS, koszt zapisu filtered indexu, przyczyna braku PSP
   optimization w naszym teście.

---

<div align="center">

[← wróć do wydania #3 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
