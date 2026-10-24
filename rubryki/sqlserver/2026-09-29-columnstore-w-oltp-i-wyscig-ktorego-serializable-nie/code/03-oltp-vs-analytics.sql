-- 03-oltp-vs-analytics.sql - ten sam stol, dwa zupelnie inne obciazenia: punktowy odczyt OLTP i agregacja analityczna.
USE PrasowkaNCCI;
GO
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
GO
PRINT '--- OLTP: punktowy odczyt po kluczu (spodziewany Clustered Index Seek) ---';
SELECT OrderId, CustomerId, OrderDate, Status, Amount
FROM dbo.Orders
WHERE OrderId = 600000;
GO
PRINT '--- ANALITYKA: agregacja po CustomerId (40000 grup), plan wybrany automatycznie przez optymalizator ---';
DECLARE @grp1 int, @sum1 decimal(18,2);
SELECT @grp1 = COUNT(*), @sum1 = SUM(t.Suma)
FROM (SELECT CustomerId, SUM(Amount) AS Suma FROM dbo.Orders GROUP BY CustomerId) AS t;
SELECT @grp1 AS Grup, @sum1 AS SumaWszystkich;
GO
PRINT '--- ANALITYKA WYMUSZONA NA ROWSTORE: ten sam raport z hintem na klucz klastrowany (bez NCCI) ---';
DECLARE @grp2 int, @sum2 decimal(18,2);
SELECT @grp2 = COUNT(*), @sum2 = SUM(t.Suma)
FROM (SELECT CustomerId, SUM(Amount) AS Suma FROM dbo.Orders WITH (INDEX(PK_Orders)) GROUP BY CustomerId) AS t;
SELECT @grp2 AS Grup, @sum2 AS SumaWszystkich;
GO
SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
GO
