#!/usr/bin/env bash
# Uruchamia caly demo od zera: kontener pgvector -> dotnet run -> sprzatanie kontenera.
# Wymagania: Docker, .NET SDK 10. Kontener: pgvector-prasowka-d4, port hosta 54329.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NAME=pgvector-prasowka-d4

trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT

docker run -d --name "$NAME" -e POSTGRES_PASSWORD=demo -e POSTGRES_DB=demo \
  -p 54329:5432 pgvector/pgvector:pg16 >/dev/null

echo "Czekam na PostgreSQL..."
until docker exec "$NAME" pg_isready -U postgres -d demo >/dev/null 2>&1; do sleep 1; done
sleep 2   # obraz robi restart po initdb

dotnet run --project "$HERE/PgVectorDotnet.csproj"
