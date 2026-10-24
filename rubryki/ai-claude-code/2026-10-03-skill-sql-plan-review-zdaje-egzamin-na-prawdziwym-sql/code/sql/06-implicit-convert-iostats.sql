-- Ten sam para zapytan jak w 05, ale z STATISTICS IO - zeby zmierzyc realny koszt
-- (logical reads) roznicy miedzy Index Scan (zly typ parametru) a Index Seek (dobry typ).
USE PrasowkaAiPlanReview;
GO
SET STATISTICS IO ON;
GO
PRINT '--- NVARCHAR param (niezgodnosc typu) ---';
EXEC sp_executesql N'SELECT OrderId, OrderStatus FROM dbo.Orders WHERE OrderStatus = @p',
    N'@p nvarchar(20)', @p = N'Cancelled';
GO
PRINT '--- VARCHAR param (typ zgodny z kolumna) ---';
EXEC sp_executesql N'SELECT OrderId, OrderStatus FROM dbo.Orders WHERE OrderStatus = @p',
    N'@p varchar(20)', @p = 'Cancelled';
GO
SET STATISTICS IO OFF;
GO
