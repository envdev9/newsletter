-- 01-lab.sql
-- Laboratorium statystyk: baza StatLab, tabela dbo.Orders 1 000 000 wierszy (Status 0..3),
-- potem dosypujemy 600 000 wierszy Status = 7 (wartosc spoza histogramu) i mierzymy PIERWSZE
-- oraz DRUGIE wywolanie tego samego zapytania.
-- Zmienne sqlcmd:  UPD = ON|OFF  (AUTO_UPDATE_STATISTICS),  ASYNC = ON|OFF (AUTO_UPDATE_STATISTICS_ASYNC)
-- Przyklad: sqlcmd -v UPD=ON ASYNC=OFF -i 01-lab.sql
SET NOCOUNT ON;
IF DB_ID('StatLab') IS NOT NULL
BEGIN
    ALTER DATABASE StatLab SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE StatLab;
END
GO
CREATE DATABASE StatLab;
GO
ALTER DATABASE StatLab SET AUTO_UPDATE_STATISTICS OFF;
ALTER DATABASE StatLab SET AUTO_UPDATE_STATISTICS_ASYNC OFF;
GO
USE StatLab;
GO
CREATE TABLE dbo.Orders
(
    OrderId int IDENTITY(1,1) CONSTRAINT PK_Orders PRIMARY KEY,
    Status  tinyint     NOT NULL,
    Note    varchar(60) NOT NULL
);
GO
;WITH n AS
(
    SELECT TOP (1000000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i
    FROM sys.all_objects a CROSS JOIN sys.all_objects b CROSS JOIN sys.all_objects c
)
INSERT dbo.Orders (Status, Note)
SELECT i % 4, CONCAT('zamowienie-', (i * 7919) % 1000003)
FROM n;
GO
-- statystyka kolumny Status powstaje przy pierwszym zapytaniu (AUTO_CREATE jest ON)
SELECT COUNT(*) AS rozgrzewka FROM dbo.Orders WHERE Status = 1;
GO
-- dopiero teraz ustawiamy tryb badany (zeby ladowanie danych nie mieszalo sie z pomiarem)
ALTER DATABASE StatLab SET AUTO_UPDATE_STATISTICS $(UPD);
ALTER DATABASE StatLab SET AUTO_UPDATE_STATISTICS_ASYNC $(ASYNC);
GO
;WITH n AS
(
    SELECT TOP (600000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i
    FROM sys.all_objects a CROSS JOIN sys.all_objects b CROSS JOIN sys.all_objects c
)
INSERT dbo.Orders (Status, Note)
SELECT 7, CONCAT('nowe-', (i * 104729) % 600011)
FROM n;
GO
PRINT '=== tryb: AUTO_UPDATE=$(UPD), ASYNC=$(ASYNC) ===';
SELECT is_auto_update_stats_on AS auto_update, is_auto_update_stats_async_on AS async
FROM sys.databases WHERE name = 'StatLab';
SELECT s.name AS statystyka, sp.rows, sp.rows_sampled, sp.modification_counter
FROM sys.stats s CROSS APPLY sys.dm_db_stats_properties(s.object_id, s.stats_id) sp
WHERE s.object_id = OBJECT_ID('dbo.Orders') AND s.name LIKE '[_]WA%';
GO
-- procedura: dzieki temu oba wywolania dziela jeden wpis w plan cache (osobne batche = osobne wpisy)
CREATE PROCEDURE dbo.Mediana AS
SELECT Note AS mediana_notatki
FROM (SELECT Note, ROW_NUMBER() OVER (ORDER BY Note) AS rn FROM dbo.Orders WHERE Status = 7) q
WHERE rn = 300000;
GO
DBCC FREEPROCCACHE WITH NO_INFOMSGS;
GO
PRINT '--- wywolanie 1 ---';
SET STATISTICS TIME ON;
EXEC dbo.Mediana;
SET STATISTICS TIME OFF;
GO
:r /tmp/code/02-raport.sql
GO
WAITFOR DELAY '00:00:10';
GO
PRINT '--- po 10 s: stan statystyki ---';
SELECT s.name AS statystyka, sp.rows, sp.rows_sampled, sp.modification_counter
FROM sys.stats s CROSS APPLY sys.dm_db_stats_properties(s.object_id, s.stats_id) sp
WHERE s.object_id = OBJECT_ID('dbo.Orders') AND s.name LIKE '[_]WA%';
GO
PRINT '--- wywolanie 2 (to samo zapytanie) ---';
SET STATISTICS TIME ON;
EXEC dbo.Mediana;
SET STATISTICS TIME OFF;
GO
:r /tmp/code/02-raport.sql
GO
PRINT '--- reczne UPDATE STATISTICS WITH FULLSCAN, potem wywolanie 3 ---';
UPDATE STATISTICS dbo.Orders WITH FULLSCAN;
GO
SET STATISTICS TIME ON;
EXEC dbo.Mediana;
SET STATISTICS TIME OFF;
GO
:r /tmp/code/02-raport.sql
GO
