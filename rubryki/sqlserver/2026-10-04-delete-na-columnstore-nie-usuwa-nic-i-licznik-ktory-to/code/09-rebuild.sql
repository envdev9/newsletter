-- 09-rebuild.sql - REORGANIZE nie dotknal najwiekszego, w pelni zapelnionego rowgroupu (0).
-- REBUILD robi pelny, offline-dla-indeksu rebuild - sprawdzamy czy to faktycznie odzyskuje miejsce.
USE PrasowkaNcciDml;
GO
ALTER INDEX NCCI_Orders ON dbo.Orders REBUILD;
GO
PRINT '--- Stan rowgroupow PO REBUILD (oczekujemy: jeden swiezy, gesty rowgroup, deleted_rows=0, total_rows = realna liczba zywych wierszy) ---';
SELECT row_group_id, state_description, total_rows, deleted_rows, size_in_bytes
FROM sys.column_store_row_groups
WHERE object_id = OBJECT_ID('dbo.Orders')
ORDER BY row_group_id;
GO
PRINT '--- Rozmiar PO REBUILD ---';
SELECT i.name AS IndexName,
       SUM(ps.used_page_count) * 8 / 1024.0 AS UsedMB,
       SUM(ps.reserved_page_count) * 8 / 1024.0 AS ReservedMB
FROM sys.dm_db_partition_stats ps
JOIN sys.indexes i ON i.object_id = ps.object_id AND i.index_id = ps.index_id
WHERE ps.object_id = OBJECT_ID('dbo.Orders')
GROUP BY i.name
ORDER BY i.name;
GO
