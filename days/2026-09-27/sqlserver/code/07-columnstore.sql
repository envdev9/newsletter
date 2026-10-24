-- 07-columnstore.sql - dwa dodatkowe warianty tej samej tabeli:
--   FactSales_RowIx : rowstore + NAJLEPSZY mozliwy zwykly indeks pokrywajacy pod nasza agregacje (uczciwy rywal),
--   FactSales_CCI   : clustered columnstore (CCI) - cala tabela w formacie kolumnowym.
USE PrasowkaCS;
SET NOCOUNT ON;
GO
SELECT * INTO dbo.FactSales_RowIx FROM dbo.FactSales_Row;
GO
CREATE CLUSTERED INDEX CX_FactSales_RowIx ON dbo.FactSales_RowIx (SaleId);
CREATE NONCLUSTERED INDEX IX_FactSales_RowIx_Cover ON dbo.FactSales_RowIx (StoreId, SaleDate) INCLUDE (Quantity, Amount);
GO
CREATE TABLE dbo.FactSales_CCI
(
    SaleId    bigint        NOT NULL,
    SaleDate  date          NOT NULL,
    ProductId int           NOT NULL,
    StoreId   int           NOT NULL,
    Quantity  smallint      NOT NULL,
    Amount    decimal(10,2) NOT NULL,
    INDEX CCI_FactSales CLUSTERED COLUMNSTORE
);
GO
INSERT dbo.FactSales_CCI WITH (TABLOCK) SELECT SaleId, SaleDate, ProductId, StoreId, Quantity, Amount FROM dbo.FactSales_Row;
GO
-- Rozmiary (MB) - rowstore vs rowstore+indeks vs columnstore
SELECT o.name AS tabela,
       CAST(SUM(ps.used_page_count) * 8 / 1024.0 AS decimal(10,1)) AS rozmiar_MB
FROM sys.dm_db_partition_stats ps
JOIN sys.objects o ON o.object_id = ps.object_id
WHERE o.name LIKE 'FactSales%'
GROUP BY o.name
ORDER BY o.name;
GO
-- Rowgroupy columnstore: kazda ma do ~1 048 576 wierszy
SELECT state_desc, COUNT(*) AS rowgroupow, SUM(total_rows) AS wierszy,
       CAST(SUM(size_in_bytes) / 1048576.0 AS decimal(10,1)) AS MB
FROM sys.dm_db_column_store_row_group_physical_stats
WHERE object_id = OBJECT_ID('dbo.FactSales_CCI')
GROUP BY state_desc;
GO
