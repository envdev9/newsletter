#!/usr/bin/env bash
# run-demo.sh - odpala calosc od zera w jednorazowym kontenerze Dockera.
# UWAGA: ten skrypt jako calosc NIE zostal uruchomiony przy pisaniu artykulu (poszczegolne pliki .sql - tak,
# recznie przez docker exec). Sesje A/B odpalane sa rownolegle przez '&' + wait.
set -euo pipefail

CONTAINER_NAME="sqlserver-prasowka-d4"
SA_PASSWORD="Prasowka_Demo_123!"
IMAGE="mcr.microsoft.com/mssql/server:2022-latest"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Uruchamiam kontener SQL Server 2022..."
docker run -d --rm --name "$CONTAINER_NAME" -e ACCEPT_EULA=Y -e "MSSQL_SA_PASSWORD=$SA_PASSWORD" "$IMAGE" >/dev/null
docker cp "$SCRIPT_DIR/." "$CONTAINER_NAME:/tmp/code"

sql() { docker exec "$CONTAINER_NAME" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$SA_PASSWORD" -C -b -I -y 120 "$@"; }
sql_nob() { docker exec "$CONTAINER_NAME" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$SA_PASSWORD" -C -I -y 120 "$@"; }  # bez -b: deadlock (1205) lapiemy w TRY/CATCH

echo "==> Czekam na SQL Server..."
for i in $(seq 1 90); do
  if sql -Q "SELECT 1" >/dev/null 2>&1; then echo "    gotowe po ${i}s"; break; fi
  sleep 1
done

echo "=== CZESC 1: deadlock ==="
sql -i /tmp/code/01-setup-deadlock.sql
sql_nob -i /tmp/code/02-deadlock-a.sql &
sleep 1
sql_nob -i /tmp/code/02-deadlock-b.sql
wait
sleep 10   # system_health zapisuje .xel z opoznieniem
sql -i /tmp/code/03-read-deadlock-graph.sql

echo "=== CZESC 2: naprawa (spojna kolejnosc) ==="
sql_nob -i /tmp/code/04-fixed-a.sql &
sleep 1
sql_nob -i /tmp/code/04-fixed-b.sql
wait

echo "=== CZESC 3: blokowanie czytelnika, potem RCSI ==="
sql_nob -i /tmp/code/05-blocking-writer.sql >/dev/null &
sleep 1
sql_nob -i /tmp/code/05-blocking-reader.sql
wait
sql -i /tmp/code/05-rcsi-on.sql
sql_nob -i /tmp/code/05-blocking-writer.sql >/dev/null &
sleep 1
sql_nob -i /tmp/code/05-blocking-reader.sql
wait

echo "=== CZESC 4: columnstore ==="
sql -i /tmp/code/06-facts-setup.sql
sql -i /tmp/code/07-columnstore.sql
sql -i /tmp/code/08-compare.sql
sql -i /tmp/code/08-compare.sql
sql -i /tmp/code/09-segment-elimination.sql

echo "==> Usuwam kontener..."
docker rm -f "$CONTAINER_NAME" >/dev/null
echo "==> Gotowe."
