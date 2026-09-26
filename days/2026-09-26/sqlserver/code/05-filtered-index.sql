-- 05-filtered-index.sql
-- Filtered index na "kolejce zadan": 500 000 wierszy, tylko 500 oczekujacych.
-- Uruchamiaj z sqlcmd -I (filtered index wymaga QUOTED_IDENTIFIER ON).
USE PrasowkaQS;
GO
-- idempotentnie: sprzatamy po poprzednim uruchomieniu
DROP INDEX IF EXISTS IX_Tasks_Status_CreatedAt ON dbo.Tasks;
DROP INDEX IF EXISTS IX_Tasks_Pending ON dbo.Tasks;
GO
SET STATISTICS IO ON;
GO

PRINT '=== (a) bez indeksu na Status: skan calej tabeli';
SELECT TOP (10) TaskId, CreatedAt FROM dbo.Tasks WHERE Status = 0 ORDER BY CreatedAt;
GO

PRINT '=== (b) zwykly indeks (Status, CreatedAt)';
CREATE NONCLUSTERED INDEX IX_Tasks_Status_CreatedAt ON dbo.Tasks (Status, CreatedAt);
GO
SELECT TOP (10) TaskId, CreatedAt FROM dbo.Tasks WHERE Status = 0 ORDER BY CreatedAt;
GO
SET STATISTICS IO OFF;
GO
SELECT i.name AS Indeks, ps.in_row_data_page_count AS Stron, ps.row_count AS Wierszy
FROM sys.indexes i
JOIN sys.dm_db_partition_stats ps ON ps.object_id = i.object_id AND ps.index_id = i.index_id
WHERE i.object_id = OBJECT_ID('dbo.Tasks') AND i.name = 'IX_Tasks_Status_CreatedAt';
GO
DROP INDEX IX_Tasks_Status_CreatedAt ON dbo.Tasks;
GO

PRINT '=== (c) filtered index: tylko wiersze Status = 0';
CREATE NONCLUSTERED INDEX IX_Tasks_Pending ON dbo.Tasks (CreatedAt) WHERE Status = 0;
GO
SET STATISTICS IO ON;
GO
SELECT TOP (10) TaskId, CreatedAt FROM dbo.Tasks WHERE Status = 0 ORDER BY CreatedAt;
GO
SET STATISTICS IO OFF;
GO
SELECT i.name AS Indeks, i.filter_definition, ps.in_row_data_page_count AS Stron, ps.row_count AS Wierszy
FROM sys.indexes i
JOIN sys.dm_db_partition_stats ps ON ps.object_id = i.object_id AND ps.index_id = i.index_id
WHERE i.object_id = OBJECT_ID('dbo.Tasks') AND i.name = 'IX_Tasks_Pending';
GO

-- Pulapka: parametr. Optymalizator musi WYBRAC plan bez znajomosci wartosci,
-- a @s moze byc 1, wiec filtered index nie jest "bezpieczny" -> nie zostaje uzyty.
SET STATISTICS IO ON;
GO
PRINT '=== (d) sp_executesql z parametrem @s: filtered index pomijany';
EXEC sp_executesql N'SELECT TOP (10) TaskId, CreatedAt FROM dbo.Tasks WHERE Status = @s ORDER BY CreatedAt', N'@s TINYINT', @s = 0;
GO
PRINT '=== (e) to samo + OPTION (RECOMPILE): wartosc znana, filtered index wraca';
EXEC sp_executesql N'SELECT TOP (10) TaskId, CreatedAt FROM dbo.Tasks WHERE Status = @s ORDER BY CreatedAt OPTION (RECOMPILE)', N'@s TINYINT', @s = 0;
GO
SET STATISTICS IO OFF;
GO
