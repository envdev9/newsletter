#!/usr/bin/env bash
# run-demo.sh — odpala cały przykład od zera w jednorazowym kontenerze Dockera.
#
# Wymaga: Docker. Nie wymaga sqlcmd na hoście (używamy sqlcmd z obrazu).
# Kontener jest efemeryczny (--rm). Cały output ląduje też w output.txt.

set -euo pipefail

CONTAINER_NAME="sqlserver-prasowka-stats"
SA_PASSWORD="Prasowka#2026!"
IMAGE="mcr.microsoft.com/mssql/server:2022-latest"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Uruchamiam kontener SQL Server 2022 ($IMAGE)..."
docker run -d --rm \
    --name "$CONTAINER_NAME" \
    -e "ACCEPT_EULA=Y" \
    -e "MSSQL_SA_PASSWORD=$SA_PASSWORD" \
    "$IMAGE"

SQLCMD=(docker exec -i "$CONTAINER_NAME" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$SA_PASSWORD" -C -b -I -y 40)

echo "==> Czekam, aż SQL Server przyjmie połączenia..."
for i in $(seq 1 90); do
    if docker exec "$CONTAINER_NAME" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$SA_PASSWORD" -C -Q "SELECT 1" >/dev/null 2>&1; then
        echo "    gotowe po ${i}s."
        break
    fi
    sleep 1
done

run_script() {
    local file="$1"
    echo ""
    echo "=== $file ==="
    "${SQLCMD[@]}" -i "/dev/stdin" < "$SCRIPT_DIR/$file"
}

run_script 01-create-table-and-data.sql
run_script 02-statistics.sql
run_script 03-key-lookup.sql
run_script 04-parameter-sniffing.sql
run_script 05-covering-index.sql

echo ""
echo "==> Zatrzymuję i usuwam kontener ($CONTAINER_NAME)..."
docker rm -f "$CONTAINER_NAME" >/dev/null

echo "==> Gotowe."
