#!/usr/bin/env bash
# run-demo.sh - cala demonstracja od zera: nonclustered columnstore na OLTP + SERIALIZABLE vs sp_getapplock.
# Wymaga: Docker. Nie wymaga lokalnego sqlcmd - uzywamy sqlcmd z kontenera przez `docker exec`.
set -euo pipefail

CONTAINER=sqlserver-prasowka-sqlserver7
PASSWORD='Prasowka_Demo_123!'
PORT=14339

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

echo
echo "########## CZESC 1: nonclustered columnstore na tabeli OLTP ##########"
echo "== 01: tabela OLTP + 1 200 000 wierszy historycznych =="
docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -b -i /tmp/code/01-setup-oltp.sql

echo "== 02: CREATE NONCLUSTERED COLUMNSTORE INDEX + stan rowgroupow =="
docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -b -i /tmp/code/02-create-ncci.sql

echo "== 03: punktowy odczyt OLTP vs agregacja analityczna (NCCI vs wymuszony rowstore) =="
docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -b -i /tmp/code/03-oltp-vs-analytics.sql

echo "== 04: male, czeste INSERT-y (trickle) -> delta store =="
docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -b -i /tmp/code/04-trickle-insert.sql

echo "== 05: zapytanie widzi dane z compressed rowgroups I z delta store =="
docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -b -i /tmp/code/05-query-with-delta.sql

echo "== 06: REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON) =="
docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -b -i /tmp/code/06-reorganize.sql

echo
echo "########## CZESC 2: SERIALIZABLE vs sp_getapplock (generator numerow faktur) ##########"
echo "== 07: swieza baza PrasowkaSerial =="
docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -b -i /tmp/code/07-setup-serial.sql

echo "== 08: wyscig pod READ COMMITTED (domyslny) - spodziewany DUPLIKAT numeru faktury =="
docker exec -d "${CONTAINER}" sh -c "/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P '${PASSWORD}' -C -i /tmp/code/08-race-readcommitted-a.sql > /tmp/a.out 2>&1"
docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -i /tmp/code/08-race-readcommitted-b.sql
echo "-- sesja A: --"; docker exec "${CONTAINER}" cat /tmp/a.out
echo "-- stan tabeli (spodziewany duplikat InvoiceNo) --"
docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -Q "USE PrasowkaSerial; SELECT * FROM dbo.Invoices ORDER BY InvoiceId;"

echo "== reset przed kolejnym scenariuszem =="
docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -b -i /tmp/code/07-setup-serial.sql

echo "== 09: ten sam wyscig pod SERIALIZABLE - spodziewany deadlock 1205, ale BEZ duplikatu =="
docker exec -d "${CONTAINER}" sh -c "/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P '${PASSWORD}' -C -i /tmp/code/09-race-serializable-a.sql > /tmp/a2.out 2>&1"
docker exec -d "${CONTAINER}" sh -c "/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P '${PASSWORD}' -C -i /tmp/code/09-inspect-locks.sql > /tmp/locks.out 2>&1"
docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -i /tmp/code/09-race-serializable-b.sql
echo "-- sesja A: --"; docker exec "${CONTAINER}" cat /tmp/a2.out
echo "-- key-range locki w trakcie wyscigu: --"; docker exec "${CONTAINER}" cat /tmp/locks.out
echo "-- stan tabeli (bez duplikatu) --"
docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -Q "USE PrasowkaSerial; SELECT * FROM dbo.Invoices ORDER BY InvoiceId;"

echo "== reset przed kolejnym scenariuszem =="
docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -b -i /tmp/code/07-setup-serial.sql

echo "== 10: sp_getapplock (READ COMMITTED wystarczy) - czyste zablokowanie B, bez bledow =="
docker exec -d "${CONTAINER}" sh -c "/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P '${PASSWORD}' -C -i /tmp/code/10-applock-a.sql > /tmp/a3.out 2>&1"
docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -i /tmp/code/10-applock-b.sql
echo "-- sesja A: --"; docker exec "${CONTAINER}" cat /tmp/a3.out
echo "-- stan tabeli (bez duplikatu, bez bledow) --"
docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -Q "USE PrasowkaSerial; SELECT * FROM dbo.Invoices ORDER BY InvoiceId;"

echo
echo "== 11: sprzatanie baz (opcjonalne, i tak usuwamy caly kontener) =="
docker exec "${CONTAINER}" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${PASSWORD}" -C -b -i /tmp/code/11-cleanup.sql

echo "== usuwam kontener =="
docker rm -f "${CONTAINER}"

echo "Gotowe."
