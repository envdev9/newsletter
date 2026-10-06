-- NO-STATISTICS, proby wariantow (kolumna Category bez statystyk, AUTO_CREATE_STATISTICS OFF).
-- Kazde zapytanie zwraca wlasny plan XML; sprawdzamy, ktore niesie ColumnsWithNoStatistics.
USE PrasowkaAiSpill1006;
SET NOCOUNT ON;
SET STATISTICS XML ON;
SELECT Category, COUNT(*) AS Cnt FROM dbo.Plain GROUP BY Category;
SELECT TOP (5) Id FROM dbo.Plain WHERE Category > 7 ORDER BY Category;
SELECT COUNT(*) AS Cnt FROM dbo.Plain AS p JOIN dbo.Tiny AS t ON t.Id = p.Category;
SET STATISTICS XML OFF;
