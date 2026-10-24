-- 02-create-ncci.sql - nonclustered columnstore index OBOK istniejacego klucza klastrowanego (OLTP zostaje OLTP).
USE PrasowkaNCCI;
GO
CREATE NONCLUSTERED COLUMNSTORE INDEX NCCI_Orders
    ON dbo.Orders (CustomerId, OrderDate, Status, Amount);
GO
SELECT
    row_group_id,
    state_description,
    total_rows,
    deleted_rows,
    size_in_bytes
FROM sys.column_store_row_groups
WHERE object_id = OBJECT_ID('dbo.Orders')
ORDER BY row_group_id;
GO
