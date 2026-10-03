-- Indeks nonclustered na CustomerId BEZ INCLUDE -> zapytanie, ktore potrzebuje
-- dodatkowych kolumn (OrderCode), musi dociagnac je z klastrowanego indeksu.
USE PrasowkaAiPlanReview;
GO
IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Orders_CustomerId_NoInclude' AND object_id = OBJECT_ID('dbo.Orders'))
    DROP INDEX IX_Orders_CustomerId_NoInclude ON dbo.Orders;
GO
CREATE NONCLUSTERED INDEX IX_Orders_CustomerId_NoInclude ON dbo.Orders (CustomerId);
GO
SET STATISTICS XML ON;
GO
SELECT OrderId, CustomerId, OrderStatus, OrderCode, TotalAmount
FROM dbo.Orders
WHERE CustomerId = 42;
GO
SET STATISTICS XML OFF;
GO
