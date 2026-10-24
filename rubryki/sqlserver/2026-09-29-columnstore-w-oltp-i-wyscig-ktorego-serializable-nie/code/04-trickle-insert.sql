-- 04-trickle-insert.sql - symulacja normalnego ruchu OLTP: male, czeste INSERT-y do tabeli z juz istniejacym NCCI.
USE PrasowkaNCCI;
GO
-- 5 malych partii po 2000 wierszy - tak wyglada zwykly ruch aplikacji, nie hurtowy load.
DECLARE @batch int = 1;
WHILE @batch <= 5
BEGIN
    ;WITH n AS
    (
        SELECT TOP (2000) CAST(ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS bigint) AS i
        FROM sys.all_columns a CROSS JOIN sys.all_columns b
    )
    INSERT dbo.Orders (CustomerId, OrderDate, Status, Amount)
    SELECT CAST(i % 40000 + 1 AS int),
           CAST('2026-09-29' AS date),
           0,
           CAST(((i * 17) % 90000) / 100.0 + 1 AS decimal(10,2))
    FROM n;
    SET @batch += 1;
END
GO
SELECT COUNT_BIG(*) AS WierszyPoInsertach FROM dbo.Orders;
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
