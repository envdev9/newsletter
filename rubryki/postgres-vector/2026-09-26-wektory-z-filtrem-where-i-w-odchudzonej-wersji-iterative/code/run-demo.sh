#!/usr/bin/env bash
# run-demo.sh - odpala cały przykład od zera: kontener pgvector/pgvector:pg16, deterministyczne
# wektory (bez modelu i bez internetu poza pobraniem obrazu), filtrowanie + iterative scan,
# partial index, halfvec i binary quantization z rerankiem. Na końcu usuwa własny kontener.
# Czas: kilka minut (generowanie 100 000 wektorów w SQL jest najwolniejszym krokiem).
set -euo pipefail

PG=pgvector-prasowka-s3
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() {
  docker rm -f "$PG" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "== 1/6Kontener pgvector/pgvector:pg16 =="
docker run -d --name "$PG" --shm-size=512m \
  -e POSTGRES_PASSWORD=demo -e POSTGRES_USER=demo -e POSTGRES_DB=demo \
  pgvector/pgvector:pg16 >/dev/null
until docker exec "$PG" psql -U demo -d demo -c 'select 1' >/dev/null 2>&1; do sleep 1; done
sleep 2   # init-owy restart serwera w obrazie postgres
until docker exec "$PG" psql -U demo -d demo -c 'select 1' >/dev/null 2>&1; do sleep 1; done

echo "== 2/6Dane: 100 000 wektorów x 128 wymiarów + 100 zapytań =="
docker exec -i "$PG" psql -U demo -d demo -v ON_ERROR_STOP=1 < "$DIR/sql/01_data.sql"

echo "== 3/6Prawda (Seq Scan) + funkcja bench() =="
docker exec -i "$PG" psql -U demo -d demo -v ON_ERROR_STOP=1 < "$DIR/sql/02_bench_fn.sql"

echo "== 4/6Filtrowanie: post-filtering, iterative scan, B-tree, partial index =="
docker exec -i "$PG" psql -U demo -d demo -v ON_ERROR_STOP=1 < "$DIR/sql/03_filter.sql"

echo "== 5/6 Quantization: halfvec, bit + rerank =="
docker exec -i "$PG" psql -U demo -d demo -v ON_ERROR_STOP=1 < "$DIR/sql/04_quantization.sql"

echo "== 6/6 Binary quantization na 1024 wymiarach =="
docker exec -i "$PG" psql -U demo -d demo -v ON_ERROR_STOP=1 < "$DIR/sql/05_bit_highdim.sql"

echo "== Sprzątanie (trap): kontener usunięty =="
