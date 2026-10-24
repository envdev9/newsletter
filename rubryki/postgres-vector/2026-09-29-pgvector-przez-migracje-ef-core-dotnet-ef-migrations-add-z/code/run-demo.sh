#!/usr/bin/env bash
# Wydanie #7 - pgvector + EF Core migrations (HNSW).
# Kontener -> dotnet ef database update (od zera) -> dotnet run -> sprzatanie.
set -euo pipefail

CONTAINER=pgvector-prasowka-d7
PORT=54340
export PG_CONN="Host=localhost;Port=${PORT};Username=postgres;Password=demo;Database=demo;Command Timeout=120;Timeout=30"

cleanup() {
  echo "--- Sprzatanie: docker rm -f ${CONTAINER} ---"
  docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cd "$(dirname "$0")"

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

echo "=== 3. dotnet ef database update - od PUSTEJ bazy (extension + tabela + indeks HNSW) ==="
dotnet tool run dotnet-ef database update

echo "=== 4. dotnet run - ladowanie danych i zapytania przez EF Core ==="
dotnet run

echo "=== Gotowe ==="
