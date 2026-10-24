#!/usr/bin/env bash
# run-demo.sh - calosc wydania #16 w jednym skrypcie. Uruchom z katalogu code/.
set -euo pipefail

KONTENER=prasowka16-sqlserver
docker run -d --rm --name "$KONTENER" \
  -e ACCEPT_EULA=Y -e 'MSSQL_SA_PASSWORD=Prasowka_Demo_123!' \
  mcr.microsoft.com/mssql/server:2022-latest

docker exec "$KONTENER" mkdir -p /tmp/code
docker cp . "$KONTENER:/tmp/code/"

SQLCMD="docker exec $KONTENER /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P Prasowka_Demo_123! -C -I -W -b"

# poczekaj az serwer wstanie
for i in $(seq 1 60); do
  if $SQLCMD -Q "SELECT 1" >/dev/null 2>&1; then break; fi
  sleep 2
done

# --- CZESC 1: PSP z wieloma predykatami + hinty wariantu ---
for f in 01-setup 02-psp-multi 03-warianty 04-ktory-predykat 05-skosnosc-i-cena 06-hint-wariant-vs-rodzic; do
  echo "##### $f"
  $SQLCMD -i "/tmp/code/$f.sql"
done

# --- CZESC 2: nieaktualne statystyki (AUTO_UPDATE_STATISTICS OFF) ---
$SQLCMD -i /tmp/code/07-stale-setup.sql
$SQLCMD -v ETAP=nieaktualne -i /tmp/code/08-stale-pomiar.sql
$SQLCMD -i /tmp/code/09-update-stats.sql
$SQLCMD -v ETAP=swieze -i /tmp/code/08-stale-pomiar.sql

$SQLCMD -i /tmp/code/10-cleanup.sql
docker rm -f -v "$KONTENER"
