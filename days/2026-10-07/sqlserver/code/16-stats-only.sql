-- 16-stats-only.sql: tylko tabela statystyk (BEZ zapytania kontrolnego, ktore moglo by wywolac auto-update).
-- Uzycie: sqlcmd -v ETAP="..." -i 16-stats-only.sql
SET NOCOUNT ON;
USE NcciClean;
GO
PRINT '##### ETAP: $(ETAP)';
SELECT s.name AS statystyka, sp.rows AS rows_w_stat, sp.modification_counter AS zmian,
       CONVERT(varchar(19), sp.last_updated, 120) AS ostatnia_aktualizacja
FROM sys.stats s CROSS APPLY sys.dm_db_stats_properties(s.object_id, s.stats_id) sp
WHERE s.object_id = OBJECT_ID('dbo.Orders') AND sp.rows IS NOT NULL ORDER BY s.stats_id;
SELECT row_group_id AS rg, state_desc AS stan, total_rows, deleted_rows
FROM sys.dm_db_column_store_row_group_physical_stats WHERE object_id = OBJECT_ID('dbo.Orders') ORDER BY row_group_id;
GO
