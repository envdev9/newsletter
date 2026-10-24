#!/usr/bin/env bash
# run-demo.sh - cala demonstracja od zera: UPDATE/DELETE na NCCI + Query Store hints (sp_query_store_set_hints).
# Wymaga: Docker. Nie wymaga lokalnego sqlcmd - uzywamy sqlcmd z kontenera przez `docker exec`.
set -euo pipefail

CONTAINER=sqlserver-prasowka-sqlserver8
PASSWORD='Prasowka_Demo_123!'
PORT=14344

echo "== start kontenera SQL Server 2022 =="
docker run -d --rm --name "${CONTAINER}" \
  -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=${PASSWORD}" \
  -p ${PORT}:1433 mcr.microsoft.com/mssql/server:2022-latest

echo "== czekam az SQL Server wstanie =="
for i in $(seq 1 30); do
  if docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -Q "SELECT 1" >/dev/null 2>&1; then
    echo "SQL Server gotowy po ${i}x2s"
    break
  fi
  sleep 2
done

echo "== kopiuje skrypty do kontenera =="
docker exec "${CONTAINER}" mkdir -p /tmp/code
docker cp . "${CONTAINER}:/tmp/code/"

SQLCMD="docker exec ${CONTAINER} /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P ${PASSWORD} -C -b"

echo
echo "########## CZESC 1: UPDATE/DELETE na tabeli z nonclustered columnstore (NCCI) ##########"
echo "== 01: tabela OLTP + 1 200 000 wierszy historycznych =="
${SQLCMD} -i /tmp/code/01-setup-ncci.sql

echo "== 02: CREATE NONCLUSTERED COLUMNSTORE INDEX + stan rowgroupow =="
${SQLCMD} -i /tmp/code/02-create-ncci.sql

echo "== 03: baseline - koszt agregacji PRZED jakimkolwiek DELETE/UPDATE =="
${SQLCMD} -i /tmp/code/03-analytics-baseline.sql

echo "== 04: DELETE 300 000 wierszy (Status=3) - sprawdzamy deleted_rows w sys.column_store_row_groups =="
${SQLCMD} -i /tmp/code/04-delete-large-chunk.sql

echo "== 05: ten sam raport PO DELETE - czy reads/ghost rows sie zmienily =="
${SQLCMD} -i /tmp/code/05-analytics-after-delete.sql

echo "== 06: UPDATE 15 000 wierszy - dowod ze to DELETE+INSERT (nowy delta store OPEN) =="
${SQLCMD} -i /tmp/code/06-update-rows.sql

echo "== 07: ALTER INDEX REORGANIZE - czy to odzyskuje miejsce? =="
${SQLCMD} -i /tmp/code/07-reorganize.sql

echo "== 08: raport PO REORGANIZE =="
${SQLCMD} -i /tmp/code/08-analytics-after-reorganize.sql

echo "== 09: ALTER INDEX REBUILD - pelny reclaim =="
${SQLCMD} -i /tmp/code/09-rebuild.sql

echo "== 10: raport PO REBUILD =="
${SQLCMD} -i /tmp/code/10-analytics-after-rebuild.sql

echo
echo "########## CZESC 2: Query Store hints (sp_query_store_set_hints) jako alternatywa OPTION(RECOMPILE) ##########"
echo "== 11: baza PrasowkaQueryHints, tabela skosna (parameter sniffing), Query Store ON =="
${SQLCMD} -i /tmp/code/11-setup-queryhints.sql

echo "== 12: zatruwamy plan cache - pierwsze wywolanie 'halasliwym' tenantem =="
${SQLCMD} -i /tmp/code/12-prime-bad-plan.sql

echo "== 13: sp_query_store_set_hints - wstrzykujemy OPTION(RECOMPILE), BEZ zmiany kodu procedury =="
${SQLCMD} -i /tmp/code/13-apply-query-store-hint.sql

echo "== 14: weryfikacja - kazde wywolanie dostaje teraz WLASNY, optymalny plan =="
${SQLCMD} -i /tmp/code/14-verify-after-hint.sql

echo
echo "== 15: sprzatanie baz (opcjonalne, i tak usuwamy caly kontener) =="
${SQLCMD} -i /tmp/code/15-cleanup.sql

echo "== usuwam kontener =="
docker rm -f "${CONTAINER}"

echo "Gotowe."
