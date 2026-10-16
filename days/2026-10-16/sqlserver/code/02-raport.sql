-- 02-raport.sql (dolaczany przez :r z 01-lab.sql)
-- Per plan w cache: ile razy uzyty, grant, spille do tempdb, czas ostatniego wykonania oraz estymata wierszy w Index Scan/Seek na dbo.Orders.
USE StatLab;
GO
;WITH XMLNAMESPACES (DEFAULT 'http://schemas.microsoft.com/sqlserver/2004/07/showplan')
SELECT qs.execution_count AS wykonan, qs.last_grant_kb AS grant_kb, qs.last_used_grant_kb AS uzyty_grant_kb,
       qs.last_spills AS spille_stron, qs.last_elapsed_time / 1000 AS czas_ms, qs.last_dop AS dop,
       CAST(p.query_plan AS xml).value('(//RelOp[@PhysicalOp="Clustered Index Scan"]/@EstimateRows)[1]', 'varchar(30)') AS estymata_wierszy
FROM sys.dm_exec_query_stats qs
CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) t
CROSS APPLY sys.dm_exec_query_plan(qs.plan_handle) p
WHERE t.objectid = OBJECT_ID('dbo.Mediana') AND t.dbid = DB_ID('StatLab');
GO
