<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #2 — 25 września 2026

![SQL Server](https://img.shields.io/badge/SQL_Server-CC2927?style=for-the-badge&logo=microsoftsqlserver&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)
![Zweryfikowane](https://img.shields.io/badge/kod-uruchomiony_na_SQL_Server_2022_CU27-brightgreen?style=for-the-badge)

## Ten sam plan, 241 razy drożej: statystyki, Key Lookup i parameter sniffing

</div>

---

> _"Optymalizator nie patrzy w Twoje dane. Patrzy w ich streszczenie — histogram na
> 200 kroków — i w plan, który skompilował ostatnim razem."_

**🎣 Dlaczego to ważne:** wczoraj indeks ratował zapytanie. Dziś zobaczysz, jak ten
sam indeks, ta sama procedura i te same dane potrafią raz dać **21 odczytów stron**, a
raz **600 350** — tylko dlatego, że ktoś wywołał ją w innej kolejności po restarcie
aplikacji. Jeśli w Twoim .NET-owym API "czasem wolno, a nie wiadomo czemu" — to
najczęstszy podejrzany.

Wszystkie liczby poniżej pochodzą z **realnego uruchomienia** kodu z [`code/`](code/) na
kontenerze `mcr.microsoft.com/mssql/server:2022-latest` (SQL Server 2022 RTM-CU27,
16.0.4295.3, Developer Edition on Linux). Nic nie jest zmyślone ani "typowe".

---

## 1️⃣ Statystyki — skąd optymalizator wie, ile wierszy zwróci zapytanie

Zanim SQL Server wykona zapytanie, musi **zgadnąć**, ile wierszy odfiltruje `WHERE`.
Od tego zależy wszystko: Seek czy Scan, Nested Loops czy Hash Match, ile pamięci
zarezerwować. Zgaduje na podstawie **statystyk** — obiektu tworzonego razem z
indeksem (albo automatycznie dla kolumn użytych w filtrach).

Statystyka to głównie **histogram**: maksymalnie 200 "kroków" opisujących rozkład
wartości kolumny. Nasza tabela `dbo.Orders` (500 000 wierszy) jest **celowo skośna**:
klient nr 1 to "hurtownik" z 200 000 zamówień (40% tabeli), pozostałe 300 000 wierszy
rozrzucone po ok. 50 000 zwykłych klientów (klient 4242 ma ich 6).

```
DBCC SHOW_STATISTICS ('dbo.Orders', 'IX_Orders_CustomerId') WITH HISTOGRAM;

RANGE_HI_KEY RANGE_ROWS     EQ_ROWS        DISTINCT_RANGE_ROWS  AVG_RANGE_ROWS
------------ -------------- -------------- -------------------- --------------
           1            0.0       200000.0                    0            1.0
        5436        32604.0            7.0                 5434            6.0
       13355        47508.0            7.0                 7918            6.0
       ...
       50000       109926.0            6.0                18321            6.0
(8 rows affected)
```

Jak to czytać:

| Kolumna | Znaczenie | Przykład z powyżej |
|---|---|---|
| `RANGE_HI_KEY` | górna granica kroku | `1` — pierwszy krok to dokładnie klient 1 |
| `EQ_ROWS` | ile wierszy ma **dokładnie** tę wartość | klient 1 → **200 000** (histogram wie o hurtowniku) |
| `AVG_RANGE_ROWS` | średnio wierszy na wartość *pomiędzy* krokami | wartość leżąca między krokami → **6** |

Uwaga: histogram ma tu tylko **8 kroków**, choć dozwolone jest 200 — SQL Server
zebrał w krok "resztę" wartości, które mają podobną liczebność. Klient 4242 nie ma
własnego kroku; wpada w przedział o `AVG_RANGE_ROWS = 6`. Efekt w planie
(`SET STATISTICS PROFILE ON`, kolumny `Rows` = rzeczywiste vs `EstimateRows` = szacunek):

| Zapytanie | EstimateRows | Rows (rzeczywiste) |
|---|---:|---:|
| `CustomerId = 1` | 200 000 | 200 000 |
| `CustomerId = 4242` | 6 | 6 |

Trafienie co do wiersza — bo statystyki są świeże (`modification_counter = 0`,
`rows_sampled = 500000`). Gdy dane się zmieniają, a statystyki nie nadążają,
szacunki się rozjeżdżają i zaczynają się kłopoty z planem. SQL Server aktualizuje je
automatycznie po przekroczeniu progu zmian, ale próg rośnie z rozmiarem tabeli —
przy dużych tabelach "automat" bywa spóźniony.

> 💡 **Dla .NET-owca:** to działa jak `IQueryable` bez wykonania: optymalizator
> planuje na podstawie *metadanych*, nie sprawdzając danych. Zły szacunek = zły plan,
> nawet przy idealnym indeksie.

---

## 2️⃣ Key Lookup — cena za kolumny, których indeks nie ma

Wczoraj skończyliśmy na "Index Seek + Key Lookup". Dziś rozbieramy ten drugi
składnik. Indeks `IX_Orders_CustomerId` zawiera tylko `CustomerId` (+ klucz
klastrowany `OrderId`). Zapytanie chce jeszcze `OrderDate`, `Amount`, `Status`, więc
**dla każdego trafionego wiersza** SQL Server robi osobny skok do tabeli głównej —
**Key Lookup**. Jeden lookup to kilka odczytów stron (zejście po B-drzewie
klastrowanym).

Trzy uruchomienia tego samego `SELECT OrderDate, Amount, Status ... WHERE CustomerId = ...`:

| Wariant | Plan (z `STATISTICS PROFILE`) | Logical reads (`Orders`) |
|---|---|---:|
| (a) klient 4242 (6 wierszy) | Index Seek → Nested Loops → **Clustered Index Seek (Key Lookup)** ×6 | **21** |
| (b) klient 1 (200 000 wierszy), wybór optymalizatora | **Clustered Index Scan** całej tabeli | **2 486** |
| (c) klient 1, wymuszony `WITH (INDEX (IX_Orders_CustomerId))` | Index Seek + **200 000 × Key Lookup** (plan równoległy) | **612 884** |

Wniosek: optymalizator dzięki histogramowi **wie**, że dla hurtownika 200 000
lookupów to katastrofa (wariant c kosztuje **246× więcej** niż skan, wariant b), więc
sam wybiera skan. Dla rzadkiego klienta lookup jest idealny (21 stron vs 2 486).
Dobry plan zależy od **wartości parametru**. A teraz — co jeśli plan zostanie
skompilowany dla jednej wartości, a użyty dla drugiej?

Fragment realnego planu wariantu (a) — Key Lookup w akcji (`Executes = 6`: lookup
wykonany 6 razy, raz na wiersz):

```
Rows Executes StmtText
   6        1 |--Nested Loops(Inner Join, OUTER REFERENCES:([Orders].[OrderId]))
   6        1      |--Index Seek(OBJECT:([Orders].[IX_Orders_CustomerId]), SEEK:([CustomerId]=(4242)) ...
   6        6      |--Clustered Index Seek(OBJECT:([Orders].[PK__Orders__...]) ... LOOKUP ORDERED FORWARD)
```

---

## 3️⃣ Parameter sniffing i plan cache

SQL Server kompiluje plan zapytania **raz** i trzyma w **plan cache**; kolejne
wywołania tej samej procedury/zapytania parametryzowanego (tak jak z EF Core czy
Dappera) **reużywają** gotowy plan — kompilacja jest droga. Przy pierwszej
kompilacji optymalizator "podgląda" (*sniffs*) aktualną wartość parametru i
dopasowuje plan do niej. To **parameter sniffing** — normalnie pożyteczny, ale
zdradliwy przy skośnym rozkładzie danych.

Procedura z demo (zwraca podsumowanie klienta, więc konsola nie tonie w 200 000 wierszy):

```sql
CREATE PROCEDURE dbo.usp_CustomerSummary @CustomerId INT AS
    SELECT COUNT(*) AS Orders, SUM(Amount) AS TotalAmount, MAX(OrderDate) AS LastOrder
    FROM dbo.Orders WHERE CustomerId = @CustomerId;
```

### 🅰️ Pierwszy wchodzi klient rzadki, potem hurtownik

```
--- A1: klient 4242 (rzadki) -> kompilacja pod Seek+Lookup
Table 'Orders'. Scan count 1, logical reads 21
--- A2: klient 1 (hurtownik) -> REUZYCIE planu z cache
Table 'Orders'. Scan count 1, logical reads 600350
```

Plan skompilowany pod `4242` (potwierdza to `ParameterCompiledValue = (4242)`
odczytany z XML-a planu w cache) został użyty dla hurtownika: **600 350 odczytów
zamiast 2 486 — 241 razy więcej**. `sys.dm_exec_procedure_stats` widzi jeden plan i
`execution_count = 2`. Zapytanie zwróciło poprawny wynik, tylko drogo.

### 🅱️ Odwrotna kolejność: pierwszy hurtownik, potem klient rzadki

```
--- B1: klient 1 (hurtownik) -> kompilacja pod skan tabeli
Table 'Orders'. Scan count 1, logical reads 2486
--- B2: klient 4242 (rzadki) -> REUZYCIE skanu calej tabeli
Table 'Orders'. Scan count 1, logical reads 2486
```

Teraz rzadki klient płaci za skan całej tabeli: **2 486 zamiast 21 — 118×**.

| Scenariusz | Plan z cache | Klient 4242 | Klient 1 |
|---|---|---:|---:|
| A: kompilacja dla 4242 | Seek + Key Lookup | 21 | **600 350** 🔥 |
| B: kompilacja dla 1 | Clustered Index Scan | **2 486** 🔥 | 2 486 |
| `OPTION (RECOMPILE)` | własny plan za każdym razem | 21 | 2 486 |

To ten sam kod, te same dane, ten sam indeks — różni je wyłącznie **kto pierwszy
wywołał procedurę po wyczyszczeniu cache** (restart usługi, wdrożenie, `ALTER
INDEX`, aktualizacja statystyk...). Stąd objaw "działało, a od rana zamula".

### Leczenie 1: `OPTION (RECOMPILE)`

Dopisujesz `OPTION (RECOMPILE)` do zapytania — plan liczony przy każdym wywołaniu, z
konkretną wartością parametru. Wynik z demo: hurtownik 2 486, rzadki 21 — oba
optymalne. Cena: koszt kompilacji przy **każdym** wywołaniu (dla zapytań wołanych
tysiące razy na sekundę to za drogo). Inne narzędzia: `OPTIMIZE FOR (@p = ...)`,
`OPTIMIZE FOR UNKNOWN`, Query Store hints — tu ich nie demonstrujemy.

---

## 4️⃣ Leczenie 2 (lepsze): covering index z `INCLUDE`

Zamiast walczyć z planem, usuwamy przyczynę: **Key Lookup**. Covering index zawiera
w liściach wszystkie kolumny potrzebne zapytaniu:

```sql
CREATE NONCLUSTERED INDEX IX_Orders_CustomerId_Cov
    ON dbo.Orders (CustomerId)
    INCLUDE (OrderDate, Amount);
```

`INCLUDE` dokłada kolumny do liści indeksu, **nie** do klucza (nie wpływają na
sortowanie i nie zajmują miejsca w węzłach pośrednich). Zapytanie zostaje
"pokryte" — cały wynik czytamy z indeksu, bez skoku do tabeli. Realny plan dla 4242:

```
Rows Executes StmtText
   6        1 |--Index Seek(OBJECT:([Orders].[IX_Orders_CustomerId_Cov]), SEEK:([CustomerId]=(4242)) ORDERED FORWARD)
```

— **koniec z Nested Loops i Key Lookup**. Wyniki (te same zapytania co wyżej):

| Zapytanie | Wąski indeks | Covering index |
|---|---:|---:|
| klient 4242 | 21 | **3** |
| klient 1 (optymalny plan) | 2 486 | **648** |
| procedura, hurtownik pierwszy → rzadki | 2 486 → 2 486 | **648 → 4** |
| procedura, rzadki pierwszy → hurtownik | 21 → **600 350** | **3 → 648** |

Efekt uboczny, który nas cieszy najbardziej: **parameter sniffing przestał boleć**.
Niezależnie od tego, kto skompiluje plan pierwszy, oba warianty robią Index Seek po
tym samym indeksie i czytają proporcjonalnie do liczby wierszy — nie ma już
"pułapki planu". Wąski indeks zniknął (zastąpiliśmy go, nie dublowaliśmy).

### ⚖️ Cena covering indexu

| Struktura | Rozmiar (strony 8 KB) |
|---|---:|
| tabela (klucz klastrowany) | 2 476 |
| `IX_Orders_CustomerId` (wąski) | 866 |
| `IX_Orders_CustomerId_Cov` (INCLUDE OrderDate, Amount) | 1 609 |

Covering index to **duplikat części danych**: prawie dwa razy większy od wąskiego,
a każdy `INSERT`/`UPDATE` zmieniający `Amount`/`OrderDate` musi go też zaktualizować
(o kosztach zapisu pisaliśmy wczoraj). Zasada: pokrywaj **najgorętsze** zapytania,
nie wszystkie; nie wrzucaj do `INCLUDE` połowy tabeli.

---

## 🧾 Ściąga na dziś

| Pojęcie | Jedno zdanie |
|---|---|
| Statystyki / histogram | streszczenie rozkładu wartości, z którego optymalizator szacuje liczbę wierszy |
| Key Lookup | dokładanie brakujących kolumn z tabeli głównej, po jednym wierszu naraz |
| Covering index (`INCLUDE`) | indeks z kolumnami zapytania w liściach — zero lookupów |
| Plan cache | skompilowane plany trzymane do reużycia |
| Parameter sniffing | plan skompilowany pod pierwszą wartość parametru służy wszystkim kolejnym |

**Pełny, uruchamialny kod + komendy:** [`code/README.md`](code/README.md).

---

## ✅ Status weryfikacji

Kod uruchomiony realnie: kontener `mcr.microsoft.com/mssql/server:2022-latest`
(SQL Server 2022 RTM-CU27, 16.0.4295.3), skrypty `01`–`05` wykonane po kolei przez
`sqlcmd` z wnętrza kontenera (`-C -b -I`), wszystkie liczby `logical reads` i
fragmenty planów powyżej pochodzą z tego uruchomienia. Ta sama wersja skryptów
`03`–`05` została uruchomiona w finalnej postaci; `01` i `02` bez zmian.

Dwie uczciwe uwagi: (1) skrypt `run-demo.sh` jako całość **nie został odpalony**
(środowisko zablokowało jego uruchomienie) — zamiast tego te same polecenia
`docker run` / `docker exec ... sqlcmd -i` wykonano ręcznie krok po kroku, dokładnie
tak, jak są w skrypcie; (2) dane są deterministyczne (bez `NEWID()`), więc liczby
powinny być powtarzalne, ale drobne różnice (np. 648 vs 650 stron) mogą wystąpić
między wersjami SQL Servera.

---

<div align="center">

[← wróć do wydania #2 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
