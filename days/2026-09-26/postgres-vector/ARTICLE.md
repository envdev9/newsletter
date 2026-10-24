<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #3 — 26 września 2026

![PostgreSQL + pgvector](https://img.shields.io/badge/PostgreSQL_%2B_pgvector_0.8.6-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Status kodu](https://img.shields.io/badge/kod-uruchomiony_%E2%9C%94-brightgreen?style=for-the-badge)

## Wektory z filtrem WHERE i w odchudzonej wersji: iterative scan, partial index, halfvec, bit

</div>

---

> _"Indeks HNSW z filtrem `WHERE tenant_id = 7` potrafi zwrócić **zero wierszy** i nie zgłosić żadnego błędu.
> Zapytanie się wykonało. Wynik jest po prostu pusty."_

## 🎯 Dlaczego to ważne

W wydaniach #1 i #2 było `ORDER BY emb <=> q LIMIT k`. Produkcyjne zapytanie prawie nigdy tak nie wygląda -
ma `WHERE tenant_id = @t` (multi-tenancy), `WHERE lang = 'pl'`, uprawnienia. I tu jest pułapka:
**HNSW najpierw znajduje kandydatów, a dopiero potem stosuje filtr.** Drugi temat to koszt: 100 mln wektorów
po 1536 wymiarów w `float32` to setki GB. Pokażemy, co daje `halfvec` i kwantyzacja binarna - **i gdzie
kwantyzacja nas zawiodła w moim teście**.

> 🧪 **Uczciwie o danych.** Nie używam modelu embeddingowego. Wektory są **deterministyczne i syntetyczne**
> (`setseed`): centroidy + jednorodny szum, `tenant_id` losowy i niezależny od podobieństwa. Nie potrzeba internetu
> ani kluczy. Liczby poniżej to **prawdziwy output** z kontenera `pgvector/pgvector:pg16`, **pgvector 0.8.6**,
> PostgreSQL 16.15, 100 000 wierszy x 128 wymiarów, 100 zapytań, jeden rdzeń
> (`max_parallel_workers_per_gather = 0`), pomiar w plpgsql (`clock_timestamp`) na maszynie z Dockerem.
> Bezwzględne czasy zależą od sprzętu; **rozkład danych jest syntetyczny, więc wyniki nie przenoszą się 1:1 na realne
> embeddingi.** Zmierz na swoich.

## 1️⃣ Problem post-filtrowania

HNSW przechodzi po grafie i utrzymuje listę `hnsw.ef_search` najlepszych kandydatów (domyślnie 40). Filtr `WHERE`
Postgres nakłada **na to, co indeks zwrócił**. Jeśli filtr przepuszcza 0,5% wierszy (u nas: 200 tenantów,
średnio 502 wiersze na tenanta), z 40 kandydatów przeżywa średnio 0,2.

Prawdziwy `EXPLAIN ANALYZE` (tenant 7, `ef_search = 40`):

```
 Limit (actual rows=0 loops=1)
   ->  Index Scan using items_hnsw on items (actual rows=0 loops=1)
         Order By: (emb <=> $0)
         Filter: (tenant_id = 7)
         Rows Removed by Filter: 40
```

Zażądaliśmy 10 wierszy, dostaliśmy **0**: 40 kandydatów, wszystkie odrzucone filtrem. Pomiar na 100 zapytaniach
(recall@10 względem dokładnego wyniku z Seq Scan, tylko w obrębie tenanta):

| Wariant | recall@10 | śr. wierszy | śr. czas |
|---|---:|---:|---:|
| Bez filtra, `ef_search=40` (punkt odniesienia) | 0,890 | 10,0 | 0,72 ms |
| **Z filtrem**, `ef_search=40` | **0,019** | **0,2** | 0,65 ms |
| Z filtrem, `ef_search=200` | 0,094 | 0,9 | 1,66 ms |
| Z filtrem, `ef_search=1000` | 0,476 | 4,8 | 4,35 ms |

> 💡 Podnoszenie `ef_search` to droga donikąd: przy 1000 kandydatów nadal średnio tylko 4,8 z 10 wierszy.
> Uwaga dla .NET-owca: to jest ciche złe zachowanie. Żaden wyjątek, `SqlException`-odpowiednik, ani ostrzeżenie -
> `NpgsqlDataReader` po prostu zwróci mniej wierszy niż `LIMIT`.

## 2️⃣ `hnsw.iterative_scan` (pgvector 0.8.0+)

Od 0.8.0 indeks potrafi **kontynuować skanowanie**, dopóki nie uzbiera dość wyników po filtrze. Włączasz jednym
parametrem sesji:

```sql
SET hnsw.iterative_scan = relaxed_order;   -- albo strict_order; domyślnie off
```

| Tryb | recall@10 | śr. wierszy | śr. czas | p95 |
|---|---:|---:|---:|---:|
| `off` | 0,019 | 0,2 | 0,65 ms | 0,81 ms |
| `strict_order` | 0,908 | 10,0 | 9,65 ms | 15,80 ms |
| `relaxed_order` | 0,928 | 10,0 | 8,96 ms | 14,19 ms |
| `relaxed_order`, `hnsw.max_scan_tuples=2000` | 0,841 | 8,8 | 5,07 ms | 8,07 ms |

Co z tego wynika:

- ✅ Recall wraca do poziomu zapytania bez filtra (0,89), a wierszy jest komplet. **Płacisz czasem**: ok. 9 ms zamiast
  0,7 ms, bo indeks przeszedł przez ok. 1250 kandydatów (EXPLAIN: `Rows Removed by Filter: 1246`).
- 🧯 `hnsw.max_scan_tuples` (domyślnie 20000) to bezpiecznik: przy 2000 skan urywa się wcześniej i wraca mniej
  wierszy (8,8 zamiast 10). To kompromis "gorszy wynik" kontra "nieograniczony czas" przy wyjątkowo selektywnym filtrze.
- `relaxed_order` może zwracać wyniki nie w ścisłej kolejności odległości, `strict_order` pilnuje kolejności.
  W tym pomiarze różnica recall (0,908 vs 0,928) jest w granicach szumu na 100 zapytaniach; nie wyciągam z niej wniosków.
  Jeśli potrzebujesz posortowanego wyniku z `relaxed_order`, dokumentacja pgvector radzi opakować zapytanie i
  posortować je wyżej (nie testowałem tego wariantu).

## 3️⃣ Indeks B-tree nie ratuje sytuacji automatycznie

Naiwny odruch: "dodam B-tree na `tenant_id`, planner wybierze dokładny plan (500 wierszy + sort)". Sprawdzone:

```
 Limit (actual rows=0 loops=1)
   ->  Index Scan using items_hnsw on items (actual rows=0 loops=1)
         Order By: (emb <=> $0)
         Filter: (tenant_id = 7)
         Rows Removed by Filter: 40
```

Mimo istniejącego `items_tenant_btree` planner dla tenanta 7 **nadal wybrał HNSW** (zero wierszy), bo dla
`ORDER BY ... LIMIT 10` plan po indeksie wygląda mu na tani. W pełnym pomiarze z B-tree recall wyniósł **0,971**,
a średnia liczba wierszy **9,7 (nie 10)**, przy 0,83 ms. Interpretacja (wnioskuję z tych liczb, nie logowałem
planów per zapytanie): dla ok. 97 z 100 zapytań planner wybrał dokładny plan (recall 1,0), a dla ok. 3
przeskoczył na HNSW i zwrócił zero wierszy. **Plan zależy od wartości parametru** (statystyki tenanta).

> ⚠️ Wniosek: przy małych tenantach dokładny plan jest doskonały (0,83 ms, recall ~1), ale **nie możesz na
> niego liczyć bez kontroli**. Albo włącz `iterative_scan` jako siatkę bezpieczeństwa, albo użyj partial index.

## 4️⃣ Partial index: HNSW tylko dla "gorącego" tenanta

```sql
CREATE INDEX items_hnsw_t7 ON items USING hnsw (emb vector_cosine_ops) WHERE tenant_id = 7;
```

Rozmiar: **408 kB** (globalny: 79 MB). Planner wybiera go, gdy `WHERE` pasuje do predykatu, i **nie ma już post-filtra**:

```
 Limit (actual rows=10 loops=1)
   ->  Index Scan using items_hnsw_t7 on items (actual rows=10 loops=1)
         Order By: (emb <=> $0)
```

Zwróciło 10 wierszy, bez linii `Filter:`. Plusy: pełny recall w obrębie tenanta bez płacenia za skan
setek kandydatów. Minusy: jeden indeks na wartość - sensowne dla kilku dużych klientów, **nie dla 200 tenantów**
(zarządzanie migracjami/DDL). Partycjonowanie deklaratywne (`PARTITION BY LIST (tenant_id)`, indeks HNSW na każdej
partycji) daje ten sam efekt automatycznie - **tego wariantu nie uruchomiłem**, opisuję go z dokumentacji i logiki działania.

| Strategia | Kiedy | Zmierzone tutaj |
|---|---|---|
| Sam HNSW + `WHERE` | filtr mało selektywny (> ok. 10-20% wierszy) | nie mierzyłem; przy 0,5%: recall 0,019 |
| `iterative_scan` | ogólna siatka bezpieczeństwa, filtr zmienny | recall 0,91-0,93, ~9 ms |
| B-tree + dokładny sort | małe grupy (setki wierszy) | 0,83 ms, ale planner nie zawsze go wybiera |
| Partial index | kilku "gorących" tenantów | 408 kB, 10/10 wierszy |
| Partycjonowanie | wielu tenantów, stabilny klucz | nie uruchomiono |

## 5️⃣ Kwantyzacja: `halfvec` i `bit`

pgvector nie zmienia typu kolumny: **indeksujesz wyrażenie**, a zapytanie musi zawierać dokładnie to samo wyrażenie.

```sql
-- float16
CREATE INDEX ON items USING hnsw ((emb::halfvec(128)) halfvec_cosine_ops);
-- 1 bit na wymiar
CREATE INDEX ON items USING hnsw ((binary_quantize(emb)::bit(128)) bit_hamming_ops);
```

Rozmiary i czas budowy (100 000 x 128D, `m=16`, `ef_construction=64`):

| Indeks | Rozmiar | Budowa* | recall@10 | śr. czas zapytania |
|---|---:|---:|---:|---:|
| `vector` (fp32) | 79 MB | 24,7 s | 0,890 | 0,74 ms |
| `halfvec` (fp16) | 54 MB | 89,8 s | 0,895 | 1,36 ms |
| `bit` (bez rerank) | 30 MB | 16,8 s | **0,021** | 0,46 ms |
| `bit` + rerank 100 kandydatów | 30 MB | 16,8 s | 0,172 | 1,70 ms |
| `bit` + rerank 400 kandydatów | 30 MB | 16,8 s | 0,452 | 2,22 ms |

\* Czasy budowy to pojedyncze pomiary; budowa `halfvec` trwała najdłużej, ale nie badałem dlaczego (
kolejność budowy i stan cache mogły mieć wpływ), więc nie wyciągam z tego wniosków.

**`halfvec`: rozmiar indeksu -32%, recall bez zmian (0,895 vs 0,890), ale zapytanie wolniejsze (1,36 vs 0,74 ms)**
w tej konfiguracji: rzutowanie `emb::halfvec` przy każdym porównaniu kosztuje. Jeśli trzymasz w kolumnie od razu
typ `halfvec(N)`, rzutowania nie ma (nie mierzyłem tego wariantu). Zysk jest pewny w miejscu i I/O, nie w czasie CPU.

**`bit`: 2,6x mniejszy indeks (30 MB vs 79 MB), ale na tych danych recall katastrofalny.** Rerank pomaga
(0,02 -> 0,17 -> 0,45) i kosztuje kandydatów. Wzorzec zapytania:

```sql
SELECT id FROM (
  SELECT id, emb FROM items
  ORDER BY binary_quantize(emb)::bit(128) <~> binary_quantize($1)::bit(128)
  LIMIT 100                                      -- kandydaci wg Hamminga (przy hnsw.ef_search >= 100)
) c
ORDER BY emb <=> $1 LIMIT 10;                    -- dokładny rerank na oryginalnych float32
```

Dlaczego tak słabo? Sprawdziłem hipotezę "128 bitów to za mało" na **1024 wymiarach** (20 000 wierszy, 50 zapytań,
[`sql/05_bit_highdim.sql`](code/sql/05_bit_highdim.sql)):

| 1024D, 20 000 wierszy | Rozmiar indeksu | recall@10 | śr. czas |
|---|---:|---:|---:|
| `vector` fp32, `ef_search=40` | 156 MB | 0,932 | 1,43 ms |
| `bit` + rerank 50 | 8,5 MB (18x mniej) | 0,214 | 1,85 ms |
| `bit` + rerank 200 | 8,5 MB | 0,580 | 4,78 ms |

Rozmiar spada spektakularnie, recall dalej jest słaby. Moja interpretacja (**hipoteza, nie zmierzony fakt**):
w moich danych "sąsiedztwo" w obrębie klastra to wyłącznie niezależny, jednorodny szum, a znaki wymiarów niemal
w całości wyznacza centroid klastra, więc kod binarny prawie nie rozróżnia sąsiadów wewnątrz klastra. Prawdziwe embeddingi mają
inną strukturę i binary quantization bywa tam znacznie skuteczniejsze - **tego nie zweryfikowałem**. To test mechaniki
(rerank ratuje recall kosztem kandydatów), a nie dowód, że kwantyzacja binarna "nie działa".

> 📌 Reguła kciuka do zapamiętania: kwantyzację włączasz **dopiero po pomiarze recall na własnych embeddingach**,
> z rerankiem na pełnej precyzji. `halfvec` to zwykle bezpieczny pierwszy krok, `bit` wymaga dowodu.

## 🔷 A .NET?

Planowałem dopisać część z Npgsql + `Pgvector` (NuGet), ale w tym wydaniu **jej nie budowałem ani nie
uruchamiałem** - nie ma tu kodu C#, więc niczego nie zmyślam. W .NET wystarczy pamiętać: `SET hnsw.iterative_scan`
to ustawienie **sesji**, a Npgsql używa puli połączeń - ustaw je w tej samej transakcji (`SET LOCAL`) albo w
`Options`/connection-startup, inaczej nie masz gwarancji, które połączenie je dostanie. (To wnioskowanie z
semantyki puli, nie wynik testu.)

## 🚀 Jak uruchomić

```bash
cd days/2026-09-26/postgres-vector/code
bash run-demo.sh      # Docker + pobranie obrazu; kilka minut; sprząta własny kontener
```

Szczegóły, struktura i pełny output: [`code/README.md`](code/README.md).

## 🧾 Status weryfikacji

| Element | Status |
|---|---|
| SQL 01-05 uruchomione w kontenerze `pgvector/pgvector:pg16` (pgvector 0.8.6) | ✅ |
| Liczby i EXPLAIN w tabelach | ✅ prawdziwy output |
| `run-demo.sh` jako całość jednym poleceniem | ⚠️ pliki SQL uruchomiono kolejno tymi samymi poleceniami `docker exec`, skryptu nie odpalono end-to-end |
| Partycjonowanie deklaratywne, `halfvec` jako typ kolumny, sort przy `relaxed_order` | ❌ nie uruchomiono |
| Npgsql + Pgvector w .NET | ❌ nie zbudowano |
| Prawdziwe embeddingi | ❌ dane syntetyczne |

---

<div align="center">

[← wróć do wydania #3 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
