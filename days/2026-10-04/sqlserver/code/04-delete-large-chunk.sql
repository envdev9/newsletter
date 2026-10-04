-- 04-delete-large-chunk.sql - realny DELETE dużej porcji wierszy (Status=3, ~25%) i wpływ na rowgroupy NCCI.
USE PrasowkaNcciDml;
GO
PRINT '--- PRZED DELETE: stan rowgroupow ---';
SELECT row_group_id, state_description, total_rows, deleted_rows, size_in_bytes
FROM sys.column_store_row_groups
WHERE object_id = OBJECT_ID('dbo.Orders')
ORDER BY row_group_id;
GO
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
GO
DELETE FROM dbo.Orders WHERE Status = 3;
GO
SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
GO
PRINT '--- PO DELETE: stan rowgroupow (deleted_rows powinno wzrosnac, total_rows BEZ ZMIAN) ---';
SELECT row_group_id, state_description, total_rows, deleted_rows, size_in_bytes
FROM sys.column_store_row_groups
WHERE object_id = OBJECT_ID('dbo.Orders')
ORDER BY row_group_id;
GO
PRINT '--- Ile fizycznie zostalo wierszy wg COUNT(*) vs suma total_rows w rowgroupach ---';
SELECT COUNT_BIG(*) AS WierszyWidocznychAppce FROM dbo.Orders;
SELECT SUM(total_rows) AS SumaTotalRowsWRowgroupach, SUM(deleted_rows) AS SumaDeletedRows
FROM sys.column_store_row_groups WHERE object_id = OBJECT_ID('dbo.Orders');
GO
