<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #23 — 16 października 2026

![PostgreSQL + pgvector](https://img.shields.io/badge/PostgreSQL_16_%2B_pgvector_0.8.6-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Status kodu](https://img.shields.io/badge/kod-uruchomiony_%E2%9C%94-brightgreen?style=for-the-badge)

## Partycjonowanie z indeksem HNSW: wielotenantowy kNN bez post-filtrowania — i `max_scan_tuples`, czyli bezpiecznik skanu iteracyjnego

</div>

---

> _"Mamy 8 tenantów w jednej tabeli wektorów. Filtr `WHERE tenant = 3` obcina nam wyniki do 4–5 zamiast 10."_
> — klasyczny objaw post-filtrowania; poniżej zmierzony na liczbach i rozwiązany strukturą tabeli, nie parametrem

## 🎯 Dlaczego to ważne

W #3 i #9 walczyliśmy z post-filtrowaniem HNSW przez `hnsw.iterative_scan` — czyli „skanuj dalej, aż uzbiera się dość
wierszy". To łata na objaw. Jeśli filtr jest **zawsze** po tej samej kolumnie (tenant, region, język), lepsze jest
rozwiązanie strukturalne: `PARTITION BY LIST (tenant)`. Wtedy:

1. planner **w ogóle nie dotyka** cudzych partycji (pruning), a w partycji tenanta jest mały, własny graf HNSW,
2. ten sam filtr, który na monolicie dawał recall 0,45, daje 0,87–1,00 i **zawsze 10 wierszy**,
3. usunięcie tenanta to `DROP TABLE`, a przebudowa indeksu dotyczy jednej partycji, nie całej tabeli.

Plus drugi element: **`hnsw.max_scan_tuples`** — limit, po którym skan iteracyjny się poddaje. Zmierzyłem, co się dzieje,
gdy go obniżyć.

> 🧪 **Uczciwie o danych.** Syntetyczne, deterministyczne (`setseed(0.42)`): 20 000 wektorów × 64 wymiary (50 klastrów +
> szum), 8 tenantów po 2500 wierszy, 20 wektorów zapytań. PostgreSQL **16.15**, pgvector **0.8.6**, obraz
> `pgvector/pgvector:pg16`. Cały SQL w [`code/`](code/), cały output poniżej jest prawdziwy. Tym razem **bez .NET** — to
> kwestia schematu i planera, więc czysty `psql`.

## 1️⃣ Schemat: partycje listowe, indeks na rodzicu

```sql
CREATE TABLE items_p (
    id int NOT NULL, tenant int NOT NULL, tier int NOT NULL, embedding vector(64) NOT NULL,
    PRIMARY KEY (tenant, id)            -- PK MUSI zawierac klucz partycji
) PARTITION BY LIST (tenant);
CREATE TABLE items_p_t3 PARTITION OF items_p FOR VALUES IN (3);   -- x8

CREATE INDEX ix_p_hnsw ON items_p USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
```

`CREATE INDEX` na rodzicu **nie tworzy jednego wielkiego grafu**: tworzy osobny indeks HNSW w każdej partycji
(`items_p_t0_embedding_idx` … `_t7_`). Rozmiar sumaryczny taki sam jak monolitu (11 MB vs 11 MB), czas budowy
porównywalny (4,4 s vs 6,1 s — pamiętaj, że budowa HNSW jest niedeterministyczna, nie wyciągam z tego wniosków).

## 2️⃣ Co robi planner (`EXPLAIN`)

**A. Filtr po kluczu partycji (stała)** — pozostaje jedna partycja:

```
 Limit
   ->  Index Scan using items_p_t3_embedding_idx on items_p_t3 items_p
         Order By: (embedding <=> $0)
         Filter: (tenant = 3)
```

**B. Bez filtra** — osiem skanów HNSW i `Merge Append` (każda partycja zwraca swoje najbliższe w kolejności, merge bierze
10 najlepszych):

```
   ->  Merge Append
         Sort Key: ((items_p.embedding <=> $0))
         ->  Index Scan using items_p_t0_embedding_idx on items_p_t0 items_p_1
         ->  Index Scan using items_p_t1_embedding_idx on items_p_t1 items_p_2
         ... (8 partycji)
```

**C. Filtr jako parametr** (prepared statement, generic plan) — pruning dopiero **w czasie wykonania**:

```
   ->  Append (actual rows=10 loops=1)
         Subplans Removed: 7
         ->  Index Scan using items_p_t3_embedding_idx on items_p_t3 items_p_1 (actual rows=10 loops=1)
```

To ważne dla .NET: Npgsql z parametrami to właśnie ten przypadek, a `Subplans Removed: 7` jest dowodem, że pruning
działa także tu.

**D. Filtr po kolumnie spoza klucza partycji (`tier = 5`)** — brak pruningu, a planner zamiast HNSW wybrał
`Seq Scan` na każdej partycji + `Sort`, bo partycje są małe (2500 wierszy). Na monolicie to samo zapytanie szło po
HNSW z `Filter: (tier = 5)` na końcu (czyli podatne na post-filtrowanie). Wniosek: **partycjonowanie pomaga tylko dla
filtra po kluczu partycji**.

## 3️⃣ Recall: monolit vs partycje (dokładny kNN jako prawda, 20 zapytań, top 10)

| Zapytanie | monolit | partycje ×8 |
|---|---|---|
| bez filtra, `ef_search=10` | 0,945 | **1,000** |
| bez filtra, `ef_search=40` | 0,990 | **1,000** |
| `tenant = 3`, `ef_search=40`, `iterative_scan=off` | 0,445 (**4,5** wiersza z 10) | 0,870 (10 wierszy) |
| `tenant = 3`, `ef_search=100` | 0,500 (5,0 wiersza) | **1,000** (10 wierszy) |

Dwie rzeczy, które da się z tego wyczytać — i jedna, której nie wolno:

- **Monolit z filtrem zwraca za mało wierszy** (4,5 z 10) — to znany nam problem post-filtrowania; podniesienie
  `ef_search` prawie nie pomaga (0,445 → 0,500).
- **Partycje z filtrem zawsze zwracają 10 wierszy** i recall rośnie z `ef_search`, bo cały graf to dane jednego tenanta.
- Bez filtra partycje wychodzą lepiej, bo każda z 8 partycji dostaje własny budżet `ef_search` (łącznie 8×
  więcej kandydatów) — **to nie jest „za darmo"**: płacisz ośmioma skanami i `Merge Append`. Czasów nie mierzyłem
  w tym wydaniu, więc nie twierdzę, że jest szybciej ani wolniej.
- Czego nie wolno: uogólniać na dane rzeczywiste. Jeden zestaw, jedna budowa grafu, dane syntetyczne.

## 4️⃣ `hnsw.max_scan_tuples` — bezpiecznik skanu iteracyjnego

Gdy partycjonowanie nie wchodzi w grę (filtr po zwykłej kolumnie), zostaje `iterative_scan`. Ma on limit
`hnsw.max_scan_tuples` (domyślnie 20 000 — czyli praktycznie „cała tabela"): po przeskanowaniu tylu krotek skan kończy
się, nawet jeśli nie uzbierał `LIMIT`. Filtr `tier = 5` (5% wierszy, bez indeksu), monolit, `relaxed_order`:

| ustawienie | recall | wierszy / zapytanie |
|---|---|---|
| `iterative_scan = off` | 0,180 | 1,8 |
| `max_scan_tuples = 100` | 0,785 | **8,0** |
| `max_scan_tuples = 500` | 0,935 | 10,0 |
| `max_scan_tuples = 2000` | 0,940 | 10,0 |
| `max_scan_tuples = 20000` (domyślne) | 0,940 | 10,0 |

Co z tego wynika: przy 5% selektywności wystarczało ~500 krotek, a dalsze podnoszenie nic nie dawało. Przy zbyt niskim
limicie (100) dostajesz **mniej wierszy niż `LIMIT`**, bez błędu i ostrzeżenia. To bezpiecznik na zapytania o bardzo
niskiej selektywności (np. 0,01%), które inaczej skanowałyby cały graf — ale trzeba go dobrać świadomie, bo zbyt niski
cicho „ucina" wyniki. Zakres liczb oczywiście zależy od selektywności i danych.

## 5️⃣ Utrzymanie: co jest inne niż na zwykłej tabeli

```
REINDEX INDEX items_p_t3_embedding_idx;          Time: 667 ms     (jedna partycja, 2500 wierszy)
CREATE INDEX CONCURRENTLY ... ON items_p ...;    ERROR: cannot create index on partitioned table "items_p" concurrently
```

Na PostgreSQL 16 **nie da się** zrobić `CREATE INDEX CONCURRENTLY` wprost na tabeli partycjonowanej. Obejście (tak działa
w praktyce): indeks `ON ONLY` na rodzicu (powstaje jako **invalid**), potem `CONCURRENTLY` na każdej partycji i
`ALTER INDEX … ATTACH PARTITION`. Zmierzone:

```
CREATE INDEX ix_p_l2 ON ONLY items_p USING hnsw (...);     -- indisvalid = f
CREATE INDEX CONCURRENTLY items_p_t0_l2 ON items_p_t0 ...; -- ~560 ms
ALTER INDEX ix_p_l2 ATTACH PARTITION items_p_t0_l2;        -- indisvalid = f   (nadal)
... po 7. partycji: f ...
... po 8. (ostatniej) partycji: indisvalid = t
```

Rodzic staje się `valid` dopiero po podpięciu **wszystkich** partycji. Dla nowej partycji
(`CREATE TABLE ... PARTITION OF`) oba indeksy rodzica powstają automatycznie i są od razu `valid`.
`ALTER TABLE ... DETACH PARTITION` + `DROP TABLE` usuwa dane tenanta jednym szybkim poleceniem (ms), zamiast
`DELETE` + `VACUUM` na dużej tabeli.

Wiąże się to z tym, co znamy z #7–#8: przebudowa indeksu HNSW jest ciężka i blokująca, więc **rozbicie na partycje
zmniejsza jednostkę pracy** do jednego tenanta.

## 🪤 Pułapki (wszystkie napotkane naprawdę)

| Pułapka | Objaw / naprawa |
|---|---|
| PK na partycjonowanej tabeli bez klucza partycji | PK musi zawierać `tenant` — stąd `PRIMARY KEY (tenant, id)` (nie `id`) |
| `CREATE INDEX CONCURRENTLY` na rodzicu | `ERROR: cannot create index on partitioned table ... concurrently` → `ON ONLY` + per partycja + `ATTACH` |
| Filtr po kolumnie spoza klucza | brak pruningu; wszystkie partycje; tu planner wybrał Seq Scan |
| Zbyt niskie `max_scan_tuples` | cicho mniej wierszy niż `LIMIT` (8,0 zamiast 10 przy 100) |
| Filtr jako literał vs parametr | literał: pruning przy planowaniu; parametr: dopiero w czasie wykonania (`Subplans Removed`) |
| Liczba partycji | każda partycja = osobny graf i osobny skan; setki partycji bez filtra po kluczu to setki skanów (nie mierzyłem) |

## 🚀 Jak uruchomić

Kroki: [`code/README.md`](code/README.md) (kontener `pgvector-prasowka-d23`, cztery pliki `.sql` przez `psql`).

## 🧾 Status weryfikacji

| Element | Status |
|---|---|
| Schemat partycjonowany, indeks HNSW na rodzicu = indeks per partycja | ✅ uruchomione |
| Plany A–E: pruning stały/parametr, Merge Append, brak pruningu po innej kolumnie | ✅ `EXPLAIN` |
| Recall monolit vs partycje (4 scenariusze), powtórzony dwukrotnie z tym samym wynikiem | ✅ 20 zapytań, jedna budowa grafu |
| `max_scan_tuples` 100/500/2000/20000 | ✅ uruchomione, jeden filtr (5%) |
| `ON ONLY` + `CONCURRENTLY` per partycja + `ATTACH INDEX`, błąd wprost na rodzicu | ✅ uruchomione |
| Czasy zapytań partycje vs monolit, skalowanie przy dziesiątkach/setkach partycji | ❌ nie mierzone |
| Zachowanie `max_scan_tuples` w obrębie partycji, `DETACH CONCURRENTLY` | ❌ niezweryfikowane |
| Partycjonowanie przez EF Core / Npgsql, `HalfVector` w EF Core | ❌ niezweryfikowane |
| Kod z #2 (fastembed, prawdziwe embeddingi) | ❌ nadal niezweryfikowany |

---

<div align="center">

[← wszystkie artykuły: 🧬 PostgreSQL jako baza wektorowa](../README.md) · [spis rubryk](../../../README.md)

</div>
