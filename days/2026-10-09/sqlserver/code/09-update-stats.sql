-- 09-update-stats.sql
-- Reczne odswiezenie statystyk (AUTO_UPDATE_STATISTICS jest OFF, wiec nikt inny tego nie zrobi).
SET NOCOUNT ON;
USE StaleLab;
GO
UPDATE STATISTICS dbo.Orders WITH FULLSCAN;
GO
SELECT s.name AS statystyka, sp.rows, sp.rows_sampled, sp.modification_counter
FROM sys.stats s CROSS APPLY sys.dm_db_stats_properties(s.object_id, s.stats_id) sp
WHERE s.object_id = OBJECT_ID('dbo.Orders') AND sp.rows IS NOT NULL ORDER BY s.name;
GO
