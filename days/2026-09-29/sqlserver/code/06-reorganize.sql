-- 06-reorganize.sql - wymuszenie kompresji delta store (bez tego tuple mover zrobi to sam, ale dopiero po 1 048 576 wierszach albo w tle po czasie).
USE PrasowkaNCCI;
GO
PRINT '--- PRZED REORGANIZE ---';
SELECT row_group_id, state_description, total_rows, deleted_rows
FROM sys.column_store_row_groups
WHERE object_id = OBJECT_ID('dbo.Orders')
ORDER BY row_group_id;
GO
ALTER INDEX NCCI_Orders ON dbo.Orders REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON);
GO
PRINT '--- PO REORGANIZE ---';
SELECT row_group_id, state_description, total_rows, deleted_rows
FROM sys.column_store_row_groups
WHERE object_id = OBJECT_ID('dbo.Orders')
ORDER BY row_group_id;
GO
