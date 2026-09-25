#!/usr/bin/env bash
# run-demo.sh - odpala cały przykład od zera: Postgres+pgvector w Dockerze, prawdziwy lokalny
# model embeddingowy (fastembed/ONNX, bez kluczy API), hybrid search (RRF) i pomiar
# recall vs czas dla IVFFlat/HNSW. Sprząta: usuwa własny kontener i własną sieć.
#
# Wymaga: Docker + dostęp do internetu (obraz python:3.12-slim, pip, pobranie modelu ~220 MB).
# Zmienne opcjonalne: N_DOCS (domyślnie 8000), N_QUERIES (domyślnie 100).
set -euo pipefail

PG=pgvector-prasowka-hybrid
NET=pgvector-prasowka-net
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() {
  docker rm -f "$PG" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "== 1/5 Sieć i kontener pgvector/pgvector:pg16 =="
docker network create "$NET" >/dev/null
docker run -d --name "$PG" --network "$NET" --shm-size=512m \
  -e POSTGRES_PASSWORD=demo -e POSTGRES_USER=demo -e POSTGRES_DB=demo \
  pgvector/pgvector:pg16 >/dev/null
until docker exec "$PG" pg_isready -U demo -d demo >/dev/null 2>&1; do sleep 1; done
sleep 2   # init-owy restart serwera w obrazie postgres

echo "== 2/5 Schemat =="
docker exec -i "$PG" psql -U demo -d demo -v ON_ERROR_STOP=1 < "$DIR/sql/01_schema.sql"

echo "== 3/5 Jeden kontener Pythona (model pobierany raz): embeddingi -> hybrid -> strojenie =="
docker run --rm --network "$NET" -e PGHOST="$PG" \
  -e N_DOCS="${N_DOCS:-8000}" -e N_QUERIES="${N_QUERIES:-100}" \
  -v "$DIR:/app:ro" -w /app/py python:3.12-slim \
  sh -c "pip install -q --no-cache-dir -r /app/requirements.txt 2>&1 | grep -v -i notice; pip list 2>/dev/null | grep -i -E '^(fastembed|onnxruntime|psycopg) '; echo '== 3/5 Embeddingi (prawdziwy model) + ładowanie =='; python embed_load.py; echo; echo '== 4/5 Hybrid search =='; python hybrid.py; echo; echo '== 5/5 Strojenie indeksów =='; python tuning.py"

echo "== Sprzątanie (trap): kontener i sieć usunięte =="
