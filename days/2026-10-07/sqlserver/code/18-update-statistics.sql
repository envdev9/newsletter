-- 18-update-statistics.sql: reczna aktualizacja statystyk po REBUILD (FULLSCAN) - czy cokolwiek sie zmienia?
SET NOCOUNT ON;
USE NcciClean;
GO
UPDATE STATISTICS dbo.Orders WITH FULLSCAN;
GO
SELECT s.name AS statystyka, sp.rows AS rows_w_stat, sp.rows_sampled, sp.modification_counter AS zmian,
       CONVERT(varchar(19), sp.last_updated, 120) AS ostatnia_aktualizacja
FROM sys.stats s CROSS APPLY sys.dm_db_stats_properties(s.object_id, s.stats_id) sp
WHERE s.object_id = OBJECT_ID('dbo.Orders') AND sp.rows IS NOT NULL ORDER BY s.stats_id;
GO
