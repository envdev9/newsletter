-- 10-analytics-after-rebuild.sql - to samo zapytanie co w 03/05/08, teraz PO pelnym REBUILD.
USE PrasowkaNcciDml;
GO
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
GO
PRINT '--- PO REBUILD: agregacja po CustomerId ---';
DECLARE @grp int, @sum decimal(18,2), @rows bigint;
SELECT @grp = COUNT(*), @sum = SUM(t.Suma), @rows = SUM(t.Ile)
FROM (SELECT CustomerId, SUM(Amount) AS Suma, COUNT(*) AS Ile FROM dbo.Orders GROUP BY CustomerId) AS t;
SELECT @grp AS Grup, @sum AS SumaWszystkich, @rows AS WierszyRazem;
GO
SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
GO
