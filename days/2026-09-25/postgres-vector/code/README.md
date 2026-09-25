# Kod do wydania #2 - pgvector: hybrid search + strojenie indeksów

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

> ⚠️ **STATUS WERYFIKACJI: kod NIE został uruchomiony.** Uruchomienie `run-demo.sh` (i `chmod +x`)
> odrzuciły uprawnienia środowiska, więc nie ma tu żadnego wklejonego outputu - nic nie zostało
> zmyślone. Zweryfikowano tylko: pobranie obrazu `pgvector/pgvector:pg16` oraz dostęp do PyPI z
> kontenera `python:3.12-slim`. Kod może zawierać błędy, których nie wychwycił żaden przebieg.
> Po pierwszym uruchomieniu wklej output w sekcji poniżej.

## Fragment prasówki, którego dotyczy ten kod

> Odległość kosinusowa i `ts_rank_cd` to różne skale - nie da się ich dodać. **Reciprocal Rank
> Fusion** patrzy tylko na pozycję w każdej liście: `rrf(dok) = Σ 1 / (k + pozycja)`, k = 60.
> Dokument wysoko w obu listach wygrywa; dokument tylko w jednej nadal dostaje punkty.
>
> Strojenie: IVFFlat - `lists` (budowa) i `ivfflat.probes` (zapytanie; `probes = lists` daje wynik
> dokładny). HNSW - `m`, `ef_construction` (budowa) i `hnsw.ef_search` (zapytanie, powinno być >=
> LIMIT). Pomiar: prawda = Seq Scan bez indeksu; dla każdej konfiguracji recall@10 i czas zapytania.

Zastrzeżenie: 24 dokumenty `kb` są ręcznie napisane; korpus benchmarkowy to zdania z szablonów
(prawdziwe embeddingi, sztuczny tekst) - wyniki nie przenoszą się 1:1 na realne dane.

## Struktura

```
code/
├── run-demo.sh          # cała pętla od zera; sprząta kontener i sieć (trap EXIT)
├── requirements.txt     # fastembed (ONNX) + psycopg
├── sql/
│   ├── 01_schema.sql        # kb (z generowanym tsvector), bench, bench_q; vector(384)
│   ├── 02_fts_index.sql     # GIN na tsvector + HNSW na kb (odpalane z embed_load.py)
│   └── 03_hybrid_rrf.sql    # RRF w czystym SQL (dwa CTE + FULL OUTER JOIN)
└── py/
    ├── corpus.py        # 24 dokumenty kb + generator korpusu benchmarkowego
    ├── common.py        # połączenie, model, formatowanie wektora
    ├── embed_load.py    # prawdziwe embeddingi lokalnym modelem -> COPY do Postgresa
    ├── hybrid.py        # wektor vs FTS vs RRF na 5 zapytaniach + EXPLAIN GIN
    └── tuning.py        # recall@10 / czas: Seq Scan, IVFFlat (lists x probes), HNSW (m, efc x ef_search)
```

## Jak uruchomić

Wymagania: Docker i internet (obraz `python:3.12-slim`, pakiety pip, model ~200+ MB).

```bash
cd days/2026-09-25/postgres-vector/code
bash run-demo.sh
# opcjonalnie mniej/więcej danych:  N_DOCS=20000 N_QUERIES=200 bash run-demo.sh
```

Skrypt tworzy własną sieć `pgvector-prasowka-net` i kontener `pgvector-prasowka-hybrid`, po
zakończeniu (także przy błędzie) usuwa oba. Nie dotyka innych kontenerów ani obrazów.

## Output z uruchomienia

_Brak - patrz status weryfikacji na górze. Wklej tu pełny output po pierwszym uruchomieniu._
