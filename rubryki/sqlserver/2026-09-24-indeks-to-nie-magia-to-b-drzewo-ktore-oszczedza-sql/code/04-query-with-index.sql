-- 04-query-with-index.sql
-- DOKŁADNIE to samo zapytanie co w 02-query-no-index.sql, ale teraz
-- CustomerId ma indeks. Oczekiwana zmiana w planie: "Clustered Index Scan"
-- (przelot po całej tabeli) zamienia się na "Index Seek" na
-- IX_Orders_CustomerId (skok od razu do właściwych wierszy w B-drzewie) +
-- "Key Lookup" na indeksie klastrowanym (dociągnięcie pozostałych kolumn,
-- których nie ma w indeksie nieklastrowanym - indeks trzyma tylko
-- CustomerId + wskaźnik do wiersza, nie całą resztę tabeli).
-- Logical reads powinny spaść z tysięcy stron do pojedynczych/kilkudziesięciu.

USE PrasowkaDemo;
GO

DBCC DROPCLEANBUFFERS;
DBCC FREEPROCCACHE;
GO

SET STATISTICS IO ON;
SET STATISTICS TIME ON;
SET STATISTICS PROFILE ON;
GO

SELECT OrderId, CustomerId, OrderDate, Amount, Status
FROM dbo.Orders
WHERE CustomerId = 1;
GO

SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
SET STATISTICS PROFILE OFF;
GO
