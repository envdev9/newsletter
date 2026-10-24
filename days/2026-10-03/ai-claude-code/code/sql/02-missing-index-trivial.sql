-- PULAPKA: ten prosty SELECT dostaje plan TRIVIAL (StatementOptmLevel="TRIVIAL") -
-- SQL Server w tym trybie NIE uruchamia pelnego cost-based optimizera, a wiec
-- NIE generuje sugestii MissingIndexGroup, nawet jesli brakujacy indeks realnie by pomogl.
-- Zapisz wynik do pliku i wyciagnij <ShowPlanXML...> (patrz code/README.md).
USE PrasowkaAiPlanReview;
GO
SET STATISTICS XML ON;
GO
SELECT OrderId, CustomerId, OrderStatus, TotalAmount
FROM dbo.Orders
WHERE CustomerId = 42;
GO
SET STATISTICS XML OFF;
GO
