-- Klasyczna pulapka EF Core / ADO.NET: string parametr jest domyslnie wysylany
-- jako NVARCHAR (SqlDbType.NVarChar), nawet gdy kolumna w bazie to VARCHAR.
-- Indeks na OrderStatus istnieje, ale typ parametru != typ kolumny -> PlanAffectingConvert,
-- Seek staje sie niemozliwy, SQL Server musi skanowac i konwertowac kazdy wiersz.
USE PrasowkaAiPlanReview;
GO
IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Orders_OrderStatus' AND object_id = OBJECT_ID('dbo.Orders'))
    DROP INDEX IX_Orders_OrderStatus ON dbo.Orders;
GO
CREATE NONCLUSTERED INDEX IX_Orders_OrderStatus ON dbo.Orders (OrderStatus);
GO
SET STATISTICS XML ON;
GO
-- ZLE: parametr NVARCHAR (tak jak domyslnie wysyla go SqlParameter dla string/EF Core)
EXEC sp_executesql N'SELECT OrderId, OrderStatus FROM dbo.Orders WHERE OrderStatus = @p',
    N'@p nvarchar(20)', @p = N'Cancelled';
GO
-- DOBRZE: parametr VARCHAR, typ zgodny z kolumna (np. SqlParameter z explicit SqlDbType.VarChar)
EXEC sp_executesql N'SELECT OrderId, OrderStatus FROM dbo.Orders WHERE OrderStatus = @p',
    N'@p varchar(20)', @p = 'Cancelled';
GO
SET STATISTICS XML OFF;
GO
