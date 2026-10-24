-- 05-covering-index.sql
-- Covering index: kolumny potrzebne zapytaniu dokładamy jako INCLUDE, więc
-- Key Lookup znika, a problem parameter sniffingu praktycznie też (Index Seek
-- jest dobry i dla klienta rzadkiego, i dla hurtownika).
-- (Uruchamiaj sqlcmd z flagą -I.)
USE PrasowkaStats;
GO

-- Wąski indeks zastępujemy pokrywającym (nie trzymamy dwóch na tej samej kolumnie).
DROP INDEX IX_Orders_CustomerId ON dbo.Orders;
GO
CREATE NONCLUSTERED INDEX IX_Orders_CustomerId_Cov
    ON dbo.Orders (CustomerId)
    INCLUDE (OrderDate, Amount);
GO

-- Rozmiar indeksów w stronach: covering nie jest za darmo (więcej stron =
-- więcej miejsca i droższy zapis - każdy INSERT/UPDATE tych kolumn dotyka też indeksu).
SELECT i.name AS Indeks, ps.in_row_data_page_count AS StronDanych
FROM sys.indexes i
JOIN sys.dm_db_partition_stats ps
  ON ps.object_id = i.object_id AND ps.index_id = i.index_id
WHERE i.object_id = OBJECT_ID('dbo.Orders')
ORDER BY i.index_id;
GO

SET STATISTICS IO ON;
SET STATISTICS PROFILE ON;
GO
-- To samo zapytanie co w procedurze, dla obu klientów: w planie NIE MA już Key Lookup.
SELECT COUNT(*) AS Orders, SUM(Amount) AS TotalAmount, MAX(OrderDate) AS LastOrder
FROM dbo.Orders WHERE CustomerId = 4242;
GO
SELECT COUNT(*) AS Orders, SUM(Amount) AS TotalAmount, MAX(OrderDate) AS LastOrder
FROM dbo.Orders WHERE CustomerId = 1;
GO
SET STATISTICS PROFILE OFF;
GO

-- Sniffing po covering indeksie: hurtownik pierwszy (najgorszy przypadek), potem rzadki.
ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE;
GO
PRINT '--- procedura z covering indeksem: hurtownik, potem rzadki (ten sam plan)';
EXEC dbo.usp_CustomerSummary @CustomerId = 1;
GO
EXEC dbo.usp_CustomerSummary @CustomerId = 4242;
GO
PRINT '--- odwrotna kolejnosc: cache czyszczony, pierwszy rzadki, potem hurtownik';
ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE;
GO
EXEC dbo.usp_CustomerSummary @CustomerId = 4242;
GO
EXEC dbo.usp_CustomerSummary @CustomerId = 1;
GO
SET STATISTICS IO OFF;
GO
