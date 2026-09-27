-- 09-segment-elimination.sql - dlaczego filtr po dacie NIE pomogl columnstore w 08 (segment skipped 0)
-- i jak to naprawic: zbudowac columnstore z danych POSORTOWANYCH po kolumnie filtra.
-- Sprawdzony sposob: klastrowany indeks rowstore po SaleDate, potem CCI z DROP_EXISTING i MAXDOP = 1.
-- (Proste INSERT ... SELECT ... ORDER BY do columnstore NIE dalo posortowanych rowgroupow - sprawdzone.)
USE PrasowkaCS;
SET NOCOUNT ON;
GO
DROP TABLE IF EXISTS dbo.FactSales_CCI_Ord;
SELECT SaleId, SaleDate, ProductId, StoreId, Quantity, Amount INTO dbo.FactSales_CCI_Ord FROM dbo.FactSales_Row;
GO
CREATE CLUSTERED INDEX CCI_FactSales_Ord ON dbo.FactSales_CCI_Ord (SaleDate);
GO
CREATE CLUSTERED COLUMNSTORE INDEX CCI_FactSales_Ord ON dbo.FactSales_CCI_Ord WITH (DROP_EXISTING = ON, MAXDOP = 1);
GO
-- zakresy dat w rowgroupach (kolumna 2 = SaleDate; min/max to wewnetrzne data_id slownika/wartosci)
SELECT s.segment_id, s.row_count, s.min_data_id, s.max_data_id
FROM sys.column_store_segments s
JOIN sys.partitions p ON p.partition_id = s.partition_id
WHERE p.object_id = OBJECT_ID('dbo.FactSales_CCI_Ord') AND s.column_id = 2
ORDER BY s.segment_id;
GO
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
PRINT '--- Q2 na columnstore NIEposortowanym (jak w 08)';
SELECT MAX(revenue) FROM (SELECT StoreId, SUM(Amount) AS revenue FROM dbo.FactSales_CCI WHERE SaleDate >= '2025-01-01' AND SaleDate < '2025-04-01' GROUP BY StoreId) x OPTION (MAXDOP 1);
PRINT '--- Q2 na columnstore posortowanym po SaleDate';
SELECT MAX(revenue) FROM (SELECT StoreId, SUM(Amount) AS revenue FROM dbo.FactSales_CCI_Ord WHERE SaleDate >= '2025-01-01' AND SaleDate < '2025-04-01' GROUP BY StoreId) x OPTION (MAXDOP 1);
GO
