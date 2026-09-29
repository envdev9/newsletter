-- 05-query-with-delta.sql - agregacja NCCI, gdy czesc danych siedzi w skompresowanych rowgroupach, a czesc w delta store.
USE PrasowkaNCCI;
GO
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
GO
PRINT '--- suma calkowita (musi objac tez 10000 wierszy z delta store) ---';
DECLARE @grp int, @sum decimal(18,2), @cnt bigint;
SELECT @grp = COUNT(*), @sum = SUM(t.Suma), @cnt = SUM(t.Ile)
FROM (SELECT CustomerId, SUM(Amount) AS Suma, COUNT(*) AS Ile FROM dbo.Orders GROUP BY CustomerId) AS t;
SELECT @grp AS Grup, @sum AS SumaWszystkich, @cnt AS WierszyRazem;
GO
PRINT '--- tylko dzisiejsze zamowienia (siedza WYLACZNIE w delta store, rowgroup 3) ---';
SELECT COUNT(*) AS DzisiejszychZamowien, SUM(Amount) AS SumaDzisiaj
FROM dbo.Orders
WHERE OrderDate = '2026-09-29';
GO
SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
GO
