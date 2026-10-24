#!/usr/bin/env bash
# run-demo.sh — odpala cały przykład od zera w jednorazowym kontenerze Dockera.
#
# Wymaga: Docker. Nie wymaga zainstalowanego sqlcmd na hoście — używamy
# sqlcmd, który jest już wewnątrz obrazu mssql/server (docker exec).
#
# Kontener jest efemeryczny (--rm): po zatrzymaniu znika razem z bazą.

set -euo pipefail

CONTAINER_NAME="sqlserver-prasowka-demo"
SA_PASSWORD="Prasowka#2026!"
IMAGE="mcr.microsoft.com/mssql/server:2022-latest"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Uruchamiam kontener SQL Server 2022 ($IMAGE)..."
docker run -d --rm \
    --name "$CONTAINER_NAME" \
    -e "ACCEPT_EULA=Y" \
    -e "MSSQL_SA_PASSWORD=$SA_PASSWORD" \
    -p 14333:1433 \
    "$IMAGE"

# Ścieżka do sqlcmd wewnątrz obrazu 2022-latest: /opt/mssql-tools18/bin/sqlcmd
# (nowszy tools18 domyślnie wymaga TLS - stąd -C, żeby zaufać
# self-signed certyfikatowi kontenera zamiast ręcznie go importować).
SQLCMD=(docker exec -i "$CONTAINER_NAME" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$SA_PASSWORD" -C -b)

echo "==> Czekam, aż SQL Server przyjmie połączenia..."
for i in $(seq 1 60); do
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
run_script 02-query-no-index.sql
run_script 03-create-index.sql
run_script 04-query-with-index.sql
run_script 05-insert-cost-comparison.sql

echo ""
echo "==> Zatrzymuję i usuwam kontener ($CONTAINER_NAME)..."
docker rm -f "$CONTAINER_NAME" >/dev/null

echo "==> Gotowe."
