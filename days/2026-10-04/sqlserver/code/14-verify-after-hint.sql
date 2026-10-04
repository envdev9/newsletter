-- 14-verify-after-hint.sql - po hincie: kazde wywolanie dostaje WLASNY, optymalny plan - bez zmiany kodu procedury.
USE PrasowkaQueryHints;
GO
CREATE TABLE #trash (EventId bigint, TenantId int, Payload varchar(200));
GO
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
GO
PRINT '--- TenantId=1 (190 000 wierszy) PO hincie - powinien dostac plan zoptymalizowany dla DUZEJ liczby wierszy ---';
TRUNCATE TABLE #trash;
INSERT #trash EXEC dbo.GetEventsByTenant @TenantId = 1;
GO
PRINT '--- TenantId=2 (100 wierszy) PO hincie - powinien dostac WLASNY, INNY plan (Seek) zamiast reuzycia planu z Tenant=1 ---';
TRUNCATE TABLE #trash;
INSERT #trash EXEC dbo.GetEventsByTenant @TenantId = 2;
GO
SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
GO
DROP TABLE #trash;
GO
PRINT '--- Query Store: teraz WIELE planow dla query_id=6 (kazde wywolanie = nowa kompilacja przez RECOMPILE) ---';
SELECT p.plan_id, p.query_id, rs.count_executions, rs.avg_logical_io_reads, rs.last_execution_time
FROM sys.query_store_plan p
JOIN sys.query_store_runtime_stats rs ON rs.plan_id = p.plan_id
WHERE p.query_id = 6
ORDER BY rs.last_execution_time;
GO
