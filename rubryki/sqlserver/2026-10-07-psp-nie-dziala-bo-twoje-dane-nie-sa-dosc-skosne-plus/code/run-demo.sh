#!/usr/bin/env bash
# run-demo.sh - wydanie #14: (1) dlaczego PSP nie ruszal + Query Store hints na zapytaniu z PSP,
#               (2) columnstore: TOMBSTONE i statystyki po REORGANIZE/REBUILD.
# Wymaga: Docker. Lokalny sqlcmd niepotrzebny (uzywamy sqlcmd z kontenera). Calosc trwa ok. 10 minut
# (w tym 5-minutowa obserwacja TOMBSTONE w 17-tombstone-watch.sql).
set -euo pipefail

CONTAINER=prasowka14-sqlserver
PASSWORD='Prasowka_Demo_123!'
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "== start kontenera SQL Server 2022 =="
docker run -d --rm --name "${CONTAINER}" \
  -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=${PASSWORD}" \
  mcr.microsoft.com/mssql/server:2022-latest

echo "== czekam az SQL Server wstanie =="
for i in $(seq 1 40); do
  if docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -Q "SELECT 1" >/dev/null 2>&1; then
    echo "SQL Server gotowy po ${i}x3s"; break
  fi
  sleep 3
done

docker exec "${CONTAINER}" mkdir -p /tmp/code
docker cp "${HERE}/." "${CONTAINER}:/tmp/code/"

# -I = QUOTED_IDENTIFIER ON (wymagane dla XQuery .value()), -W = bez paddingu kolumn
sql() { docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -I -W -b "$@"; }

echo; echo "########## CZESC 1: parameter sensitive plan (PSP) ##########"
for f in 01-setup-psp 02-psp-baseline 03-psp-diagnoza 04-psp-rozklady 05-psp-prog-skosnosci 06-psp-prog-ratio 07-psp-dziala 08-psp-query-store-hints; do
  echo "== ${f} =="; sql -i "/tmp/code/${f}.sql"
done

echo; echo "########## CZESC 2: columnstore - statystyki i TOMBSTONE ##########"
echo "== 10 setup =="; sql -i /tmp/code/10-setup-ncci.sql
echo "== 11 snapshot po buildzie =="; sql -v "ETAP=po buildzie" -i /tmp/code/11-stats-snapshot.sql
echo "== 12 DELETE 300000 =="; sql -i /tmp/code/12-delete.sql
echo "== 11 snapshot po DELETE =="; sql -v "ETAP=po DELETE 300000" -i /tmp/code/11-stats-snapshot.sql
echo "== 13 REORGANIZE =="; sql -i /tmp/code/13-reorganize.sql
echo "== 16 stan po REORGANIZE =="; sql -v "ETAP=po REORGANIZE" -i /tmp/code/16-stats-only.sql
echo "== 17 obserwacja TOMBSTONE (5 min) =="; sql -i /tmp/code/17-tombstone-watch.sql
echo "== 14 REBUILD =="; sql -i /tmp/code/14-rebuild.sql
echo "== 16 stan po REBUILD =="; sql -v "ETAP=po REBUILD" -i /tmp/code/16-stats-only.sql
echo "== 15 maly DELETE (20000, ponizej progu auto-update) =="; sql -i /tmp/code/15-small-delete.sql
echo "== 16 stan po malym DELETE =="; sql -v "ETAP=po malym DELETE" -i /tmp/code/16-stats-only.sql
echo "== 14 REBUILD ponownie =="; sql -i /tmp/code/14-rebuild.sql
echo "== 16 stan po drugim REBUILD =="; sql -v "ETAP=po drugim REBUILD" -i /tmp/code/16-stats-only.sql
echo "== 18 UPDATE STATISTICS FULLSCAN =="; sql -i /tmp/code/18-update-statistics.sql

echo "== sprzatanie =="
sql -i /tmp/code/19-cleanup.sql
docker rm -f "${CONTAINER}"
echo "Gotowe."
