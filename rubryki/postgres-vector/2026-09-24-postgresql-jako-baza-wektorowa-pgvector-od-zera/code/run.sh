#!/usr/bin/env bash
# Odpala cały przykład od zera: kontener Postgresa z pgvector, schemat,
# dane, oba typy indeksu, zapytania podobieństwa i demo błędu wymiarów.
# Na końcu ZATRZYMUJE I USUWA kontener - nic nie zostaje w tle.
set -euo pipefail

CONTAINER=pgvector-demo
PORT=5544
SQL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/sql" && pwd)"

echo "== 1/4 Start kontenera pgvector/pgvector:pg16 =="
docker run -d --name "$CONTAINER" \
  -e POSTGRES_PASSWORD=demo -e POSTGRES_USER=demo -e POSTGRES_DB=demo \
  -p "${PORT}:5432" \
  pgvector/pgvector:pg16 >/dev/null

echo "== 2/4 Czekam aż Postgres zaakceptuje połączenia =="
until docker exec "$CONTAINER" pg_isready -U demo >/dev/null 2>&1; do
  sleep 1
done

echo "== 3/4 Uruchamiam skrypty SQL po kolei =="
for f in 01_schema.sql 02_data.sql 03_index_ivfflat.sql 04_index_hnsw.sql 05_queries.sql; do
  echo "--- $f ---"
  docker exec -i "$CONTAINER" psql -U demo -d demo -v ON_ERROR_STOP=1 < "$SQL_DIR/$f"
done

echo "--- 06_bledy.sql (SPODZIEWANY błąd - demo ograniczenia typu vector(4)) ---"
docker exec -i "$CONTAINER" psql -U demo -d demo < "$SQL_DIR/06_bledy.sql" || true

echo "== 4/4 Sprzątanie: zatrzymanie i usunięcie kontenera =="
docker rm -f "$CONTAINER" >/dev/null
echo "Gotowe. Kontener $CONTAINER usunięty, nic nie zostało w tle."
