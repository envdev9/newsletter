-- 07-reorganize.sql - dopiero REORGANIZE/REBUILD fizycznie odzyskuje miejsce po DELETE/UPDATE na NCCI.
USE PrasowkaNcciDml;
GO
PRINT '--- Rozmiar PRZED reorganizacja (indeks klastrowany PK_Orders vs NCCI_Orders) ---';
SELECT i.name AS IndexName,
       SUM(ps.used_page_count) * 8 / 1024.0 AS UsedMB,
       SUM(ps.reserved_page_count) * 8 / 1024.0 AS ReservedMB
FROM sys.dm_db_partition_stats ps
JOIN sys.indexes i ON i.object_id = ps.object_id AND i.index_id = ps.index_id
WHERE ps.object_id = OBJECT_ID('dbo.Orders')
GROUP BY i.name
ORDER BY i.name;
GO
ALTER INDEX NCCI_Orders ON dbo.Orders REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON);
GO
PRINT '--- Stan rowgroupow PO REORGANIZE (oczekujemy: delta store skompresowany, stare rowgroupy z deleted_rows > 0 moga dostac TOMBSTONE jesli udzial skasowanych wierszy byl wysoki) ---';
SELECT row_group_id, state_description, total_rows, deleted_rows, size_in_bytes
FROM sys.column_store_row_groups
WHERE object_id = OBJECT_ID('dbo.Orders')
ORDER BY row_group_id;
GO
PRINT '--- Rozmiar PO REORGANIZE ---';
SELECT i.name AS IndexName,
       SUM(ps.used_page_count) * 8 / 1024.0 AS UsedMB,
       SUM(ps.reserved_page_count) * 8 / 1024.0 AS ReservedMB
FROM sys.dm_db_partition_stats ps
JOIN sys.indexes i ON i.object_id = ps.object_id AND i.index_id = ps.index_id
WHERE ps.object_id = OBJECT_ID('dbo.Orders')
GROUP BY i.name
ORDER BY i.name;
GO
