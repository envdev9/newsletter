# Kod do wydania #3 - pgvector: filtrowanie + indeks, halfvec, binary quantization

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

> ✅ **Status:** pliki `sql/01`-`05` uruchomione naprawdę w kontenerze `pgvector/pgvector:pg16`
> (pgvector **0.8.6**, PostgreSQL 16.15). Liczby w artykule to prawdziwy output. Skrypt `run-demo.sh` jako całość
> nie był odpalony jednym poleceniem - pliki SQL puszczono kolejno tymi samymi komendami `docker exec`.
> Dane są **deterministyczne i syntetyczne** (bez modelu embeddingowego, bez internetu poza pobraniem obrazu).

## Fragment prasówki, którego dotyczy ten kod

> HNSW najpierw znajduje `hnsw.ef_search` kandydatów, potem stosuje `WHERE`. Przy filtrze przepuszczającym 0,5%
> wierszy zapytanie z `LIMIT 10` zwróciło średnio 0,2 wiersza (recall 0,019). `SET hnsw.iterative_scan =
> relaxed_order` (pgvector 0.8.0+) przywraca komplet wyników (recall 0,93) za cenę ok. 9 ms zamiast 0,7 ms.
> Alternatywy: partial index (408 kB dla jednego tenanta), partycjonowanie. Kwantyzacja: `halfvec` -32% rozmiaru
> indeksu bez straty recall; `bit` -62% (128D) / -95% (1024D), ale na danych syntetycznych recall słaby nawet z rerankiem.

## Struktura

```
code/
├── run-demo.sh               # cała pętla od zera; usuwa własny kontener (trap EXIT)
└── sql/
    ├── 01_data.sql           # 100 000 x 128D + 100 zapytań (setseed), tenant_id losowy
    ├── 02_bench_fn.sql       # prawda (Seq Scan) + funkcja bench(): recall@10, średni czas, p95
    ├── 03_filter.sql         # HNSW, post-filtering, ef_search, iterative_scan, B-tree, partial index
    ├── 04_quantization.sql   # halfvec, bit + rerank: rozmiar, recall, EXPLAIN
    └── 05_bit_highdim.sql    # bit + rerank na 1024D (20 000 wierszy)
```

Pliki mają zależności: `02` wymaga `01`, `03` wymaga `02`, `04` wymaga indeksu `items_hnsw` z `03`.

## Jak uruchomić

Wymagania: Docker (pobranie obrazu `pgvector/pgvector:pg16`).

```bash
cd days/2026-09-26/postgres-vector/code
bash run-demo.sh
```

Kontener nazywa się `pgvector-prasowka-s3` i jest usuwany na końcu (także przy błędzie). Nie dotyka innych
kontenerów ani obrazów.

## Output z uruchomienia (skrót, prawdziwy)

```
wersja_pgvector: 0.8.6      wierszy: 100000   tenantow: 200   sr_wierszy_na_tenanta: 502.3   tabela: 56 MB

HNSW m=16 ef_construction=64: 24,7 s, 79 MB
bez filtra, ef_search=40:                       recall 0.890  wierszy 10.0  0.72 ms
z filtrem, ef_search=40, iterative off:         recall 0.019  wierszy  0.2  0.65 ms
z filtrem, ef_search=200:                       recall 0.094  wierszy  0.9  1.66 ms
z filtrem, ef_search=1000:                      recall 0.476  wierszy  4.8  4.35 ms
iterative strict_order:                         recall 0.908  wierszy 10.0  9.65 ms (p95 15.80)
iterative relaxed_order:                        recall 0.928  wierszy 10.0  8.96 ms (p95 14.19)
relaxed, max_scan_tuples=2000:                  recall 0.841  wierszy  8.8  5.07 ms
B-tree na tenant_id + bench:                    recall 0.971  wierszy  9.7  0.83 ms
partial index tenant 7: 408 kB (planner: Index Scan using items_hnsw_t7, bez Filter)

rozmiary indeksów: fp32 79 MB | halfvec 54 MB (budowa 89,8 s) | bit 30 MB (budowa 16,8 s)
halfvec: recall 0.895, 1.36 ms | bit bez rerank: 0.021 | bit+rerank 40/100/400: 0.083 / 0.172 / 0.452

1024D, 20 000 wierszy: tabela 1024 kB (TOAST) | hnsw fp32 156 MB | hnsw bit 8496 kB
fp32 recall 0.932 (1.43 ms) | bit+rerank 50: 0.214 (1.85 ms) | bit+rerank 200: 0.580 (4.78 ms)
```

Czasy zależą od sprzętu i mają charakter orientacyjny (jeden rdzeń, jeden przebieg pomiarowy na zapytanie).
