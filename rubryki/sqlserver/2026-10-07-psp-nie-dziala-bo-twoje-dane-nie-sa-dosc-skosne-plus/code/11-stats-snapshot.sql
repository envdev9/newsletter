-- 11-stats-snapshot.sql
-- Zrzut stanu dbo.Orders: statystyki (rows, modification_counter, last_updated), rowgroupy columnstore,
-- potem zapytanie kontrolne (moze wywolac auto-update statystyk) i stan statystyk + estymata po nim.
-- Uzycie: sqlcmd -v ETAP="po DELETE" -i 11-stats-snapshot.sql
SET NOCOUNT ON;
USE NcciClean;
GO
PRINT '##### ETAP: $(ETAP)';
PRINT '--- statystyki PRZED zapytaniem kontrolnym';
SELECT s.name AS statystyka, sp.rows AS rows_w_stat, sp.rows_sampled, sp.modification_counter AS zmian,
       CONVERT(varchar(19), sp.last_updated, 120) AS ostatnia_aktualizacja
FROM sys.stats s CROSS APPLY sys.dm_db_stats_properties(s.object_id, s.stats_id) sp
WHERE s.object_id = OBJECT_ID('dbo.Orders') ORDER BY s.stats_id;
PRINT '--- rowgroupy columnstore';
SELECT row_group_id AS rg, state_desc AS stan, total_rows, deleted_rows
FROM sys.dm_db_column_store_row_group_physical_stats WHERE object_id = OBJECT_ID('dbo.Orders') ORDER BY row_group_id;
GO
-- zapytanie kontrolne: ile jest zamowien ze Status = 3
DECLARE @n int;
SELECT @n = COUNT(*) FROM dbo.Orders WHERE Status = 3 /*kontrola*/;
SELECT @n AS count_faktyczny;
GO
PRINT '--- statystyki PO zapytaniu kontrolnym';
SELECT s.name AS statystyka, sp.rows AS rows_w_stat, sp.rows_sampled, sp.modification_counter AS zmian,
       CONVERT(varchar(19), sp.last_updated, 120) AS ostatnia_aktualizacja
FROM sys.stats s CROSS APPLY sys.dm_db_stats_properties(s.object_id, s.stats_id) sp
WHERE s.object_id = OBJECT_ID('dbo.Orders') AND sp.rows IS NOT NULL ORDER BY s.stats_id;
-- Estymata optymalizatora z planu ostatniego wykonania (faktyczna liczba = count_faktyczny powyzej).
-- ActualRows z batch-mode scan pomijamy celowo: nie zweryfikowalismy, czy liczy wiersze przed czy po bitmapie usuniec.
DECLARE @h varbinary(64);
SELECT TOP (1) @h = qs.plan_handle FROM sys.dm_exec_query_stats qs CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) t
WHERE t.text LIKE N'%/*kontrola*/%' AND t.text NOT LIKE N'%dm_exec%' ORDER BY qs.last_execution_time DESC;
;WITH XMLNAMESPACES (DEFAULT 'http://schemas.microsoft.com/sqlserver/2004/07/showplan')
SELECT r.n.value('@PhysicalOp', 'varchar(60)') AS operator,
       r.n.value('@EstimateRows', 'float') AS estymata_wierszy
FROM sys.dm_exec_query_plan_stats(@h) p CROSS APPLY p.query_plan.nodes('//RelOp') r(n)
WHERE r.n.value('@PhysicalOp', 'varchar(60)') LIKE '%Scan%' OR r.n.value('@PhysicalOp', 'varchar(60)') LIKE '%Seek%';
GO
