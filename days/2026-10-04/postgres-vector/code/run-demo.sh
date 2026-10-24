#!/usr/bin/env bash
# Wydanie #8 - CREATE INDEX CONCURRENTLY w migracji EF Core dla indeksu HNSW (pgvector).
#
# Caly przebieg: kontener -> 3 migracje EF (plain -> plain -> CONCURRENTLY) -> pomiar
# blokady zapisow (plain CREATE INDEX) vs braku blokady (CREATE INDEX CONCURRENTLY) ->
# reprodukcja "invalid" indeksu po przerwanym budowaniu CONCURRENTLY -> naprawa REINDEX
# CONCURRENTLY -> sprzatanie.
set -euo pipefail

CONTAINER=pgvector-prasowka-d8
PORT=54341
export PG_CONN="Host=localhost;Port=${PORT};Username=postgres;Password=demo;Database=demo;Command Timeout=120;Timeout=30"

cleanup() {
  echo "--- Sprzatanie: docker rm -f ${CONTAINER} ---"
  docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cd "$(dirname "$0")"

psql_c() {
  # $1 = SQL
  docker exec "${CONTAINER}" psql -U postgres -d demo -v ON_ERROR_STOP=1 -c "$1"
}

echo "=== 1. Kontener pgvector/pgvector:pg16 na porcie ${PORT} ==="
docker run -d --name "${CONTAINER}" \
  -e POSTGRES_PASSWORD=demo -e POSTGRES_DB=demo \
  -p "${PORT}:5432" pgvector/pgvector:pg16 >/dev/null

echo "Czekam az Postgres przyjmuje polaczenia..."
until docker exec "${CONTAINER}" pg_isready -U postgres >/dev/null 2>&1; do
  sleep 1
done

echo "=== 2. Przywracanie lokalnego narzedzia dotnet-ef (z dotnet-tools.json) ==="
dotnet tool restore

echo "=== 3. Migracja 1/3: InitialCreate (plain CREATE INDEX, m=16/ef_construction=64) ==="
dotnet tool run dotnet-ef database update InitialCreate

echo "=== 4. Ladowanie 20000 wierszy (binary COPY) ==="
dotnet run -- load

echo "=== 5. Rejestracja procedury writer_probe (osobne, autocommitujace INSERTy) ==="
docker cp writer-probe.sql "${CONTAINER}:/tmp/writer-probe.sql"
docker exec "${CONTAINER}" psql -U postgres -d demo -f /tmp/writer-probe.sql

echo "=== 6. Migracja 2/3: BumpParamsBlocking (plain DROP+CREATE INDEX, BLOKUJACY) ==="
echo "    rownolegle: 60 INSERT-ow co 0.3s w tle, zeby zlapac blokade zapisow"
docker exec "${CONTAINER}" psql -U postgres -d demo -c "CALL writer_probe(900000, 60, 0.3);" \
  > writer-blocking.log 2>&1 &
WRITER_PID=$!

echo "MIGRATION_START: $(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"
time dotnet tool run dotnet-ef database update BumpParamsBlocking
echo "MIGRATION_END: $(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"
wait "${WRITER_PID}" || true

echo "Fragment writer-blocking.log (szukaj odstepu > 0.3s miedzy insertami - to jest blokada):"
tail -20 writer-blocking.log

psql_c "DELETE FROM items WHERE \"Category\"='writer-probe';"

echo "=== 7. Migracja 3/3: BumpParamsConcurrently (CREATE INDEX CONCURRENTLY, NIEBLOKUJACY) ==="
echo "    rownolegle: 70 INSERT-ow co 0.3s w tle"
docker exec "${CONTAINER}" psql -U postgres -d demo -c "CALL writer_probe(910000, 70, 0.3);" \
  > writer-concurrently.log 2>&1 &
WRITER_PID=$!

echo "MIGRATION_START: $(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"
time dotnet tool run dotnet-ef database update BumpParamsConcurrently
echo "MIGRATION_END: $(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"
wait "${WRITER_PID}" || true

echo "Fragment writer-concurrently.log (powinno byc ZERO odstepow > 0.3s):"
tail -20 writer-concurrently.log

psql_c "DELETE FROM items WHERE \"Category\"='writer-probe';"

echo "=== 8. Reprodukcja 'invalid' indeksu: przerwana CREATE INDEX CONCURRENTLY ==="
psql_c "DROP INDEX IF EXISTS ix_items_embedding_hnsw_v2;"
docker exec "${CONTAINER}" psql -U postgres -d demo -c \
  "CREATE INDEX CONCURRENTLY ix_items_embedding_hnsw_v2 ON items USING hnsw (\"Embedding\" vector_cosine_ops) WITH (ef_construction=400, m=48);" \
  > invalid-index-repro.log 2>&1 &
BUILD_PID=$!

sleep 1
PID=$(docker exec "${CONTAINER}" psql -U postgres -d demo -t -c \
  "SELECT pid FROM pg_stat_activity WHERE query LIKE 'CREATE INDEX%' LIMIT 1;" | tr -d '[:space:]')
if [[ -n "${PID}" ]]; then
  echo "Zabijam backend ${PID} w polowie budowania indeksu..."
  psql_c "SELECT pg_terminate_backend(${PID});"
else
  echo "UWAGA: budowa indeksu skonczyla sie zanim zdolalem zlapac PID - tabela za mala/za szybko."
fi
wait "${BUILD_PID}" || true

echo "Stan indeksu po przerwaniu (oczekiwane: indisvalid=f):"
psql_c "SELECT relname, indisvalid, indisready, indislive FROM pg_index idx JOIN pg_class c ON c.oid=idx.indexrelid WHERE relname='ix_items_embedding_hnsw_v2';"

echo "Naprawa przez REINDEX INDEX CONCURRENTLY (bez DROP+CREATE):"
psql_c "REINDEX INDEX CONCURRENTLY ix_items_embedding_hnsw_v2;"
psql_c "SELECT relname, indisvalid FROM pg_index idx JOIN pg_class c ON c.oid=idx.indexrelid WHERE relname='ix_items_embedding_hnsw_v2';"
psql_c "DROP INDEX ix_items_embedding_hnsw_v2;"

echo "=== 9. Finalna kontrola (indeks z migracji 3, dane, kNN przez EF) ==="
dotnet run -- load
dotnet run

echo "=== Gotowe ==="
