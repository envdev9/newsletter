-- 02-query-no-index.sql
-- Odpalamy zapytanie filtrujące po CustomerId, ZANIM powstanie jakikolwiek
-- indeks na tej kolumnie. SET STATISTICS IO/TIME pokazuje realne liczby:
-- ile stron (8 KB) SQL Server musiał przeczytać (logical reads) i ile to
-- trwało. SET STATISTICS PROFILE dołącza tekstowy plan wykonania - w kolumnie
-- StmtText zobaczysz operator "Clustered Index Scan", czyli: SQL Server
-- przeleciał całą tabelę wiersz po wierszu, bo nie miał jak "przeskoczyć"
-- od razu do CustomerId = 1.

USE PrasowkaDemo;
GO

-- Czyścimy cache stron i plan cache, żeby liczby nie były zafałszowane przez
-- to, że dane już siedzą w pamięci z poprzedniego uruchomienia. W produkcji
-- NIGDY tego nie robi się ot tak (to wyrzuca z pamięci realne dane innych
-- aplikacji) - tu robimy to świadomie, żeby porównanie było uczciwe.
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
