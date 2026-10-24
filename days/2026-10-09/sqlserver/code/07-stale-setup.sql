-- 07-stale-setup.sql
-- Baza StaleLab: dbo.Orders 1 000 000 wierszy, klucz klastrowy + NCCI, AUTO_UPDATE_STATISTICS = OFF (AUTO_CREATE zostaje ON).
-- Statusy 0..3 po 250 000. Potem DOLADOWUJEMY 600 000 wierszy ze Status = 7 (wartosc, ktorej nie ma w histogramie).
SET NOCOUNT ON;
IF DB_ID('StaleLab') IS NOT NULL
BEGIN
    ALTER DATABASE StaleLab SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE StaleLab;
END
GO
CREATE DATABASE StaleLab;
GO
ALTER DATABASE StaleLab SET AUTO_UPDATE_STATISTICS OFF;
ALTER DATABASE StaleLab SET AUTO_UPDATE_STATISTICS_ASYNC OFF;
GO
USE StaleLab;
GO
SELECT name, is_auto_create_stats_on, is_auto_update_stats_on FROM sys.databases WHERE name = 'StaleLab';
GO
CREATE TABLE dbo.Orders
(
    OrderId    int IDENTITY(1,1) CONSTRAINT PK_Orders PRIMARY KEY,
    CustomerId int           NOT NULL,
    Status     tinyint       NOT NULL,
    Amount     decimal(10,2) NOT NULL,
    Note       varchar(60)   NOT NULL
);
GO
;WITH n AS
(
    SELECT TOP (1000000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i
    FROM sys.all_objects a CROSS JOIN sys.all_objects b CROSS JOIN sys.all_objects c
)
INSERT dbo.Orders (CustomerId, Status, Amount, Note)
SELECT 1 + (i * 7919) % 500000, i % 4, 10 + (i * 31) % 9000 / 10.0, CONCAT('zamowienie-', i)
FROM n;
GO
CREATE NONCLUSTERED COLUMNSTORE INDEX NCCI_Orders ON dbo.Orders (CustomerId, Status, Amount);
GO
-- Pierwsze zapytanie tworzy auto-statystyki kolumn (AUTO_CREATE jest ON) - bez tego nie byloby co postarzec.
SELECT COUNT(*) AS rozgrzewka FROM dbo.Orders WHERE Status = 1;
SELECT COUNT(*) AS rozgrzewka FROM dbo.Orders WHERE CustomerId = 1;
GO
-- Doladowanie 600 000 wierszy Status = 7 (statystyki NIE sa aktualizowane - AUTO_UPDATE OFF)
;WITH n AS
(
    SELECT TOP (600000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i
    FROM sys.all_objects a CROSS JOIN sys.all_objects b CROSS JOIN sys.all_objects c
)
INSERT dbo.Orders (CustomerId, Status, Amount, Note)
SELECT 1 + (i * 104729) % 500000, 7, 10 + (i * 17) % 9000 / 10.0, CONCAT('nowe-', i)
FROM n;
GO
-- Wymiar klientow (do joinu w pomiarze): 500 000 wierszy, szeroki wiersz, zeby seek/lookup kosztowal
CREATE TABLE dbo.Customers (CustomerId int NOT NULL CONSTRAINT PK_Customers PRIMARY KEY, Name char(100) NOT NULL);
;WITH n AS
(
    SELECT TOP (500000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i
    FROM sys.all_objects a CROSS JOIN sys.all_objects b CROSS JOIN sys.all_objects c
)
INSERT dbo.Customers (CustomerId, Name) SELECT i, CONCAT('klient-', i) FROM n;
GO
SELECT s.name AS statystyka, sp.rows, sp.rows_sampled, sp.modification_counter, sp.last_updated
FROM sys.stats s CROSS APPLY sys.dm_db_stats_properties(s.object_id, s.stats_id) sp
WHERE s.object_id = OBJECT_ID('dbo.Orders') AND sp.rows IS NOT NULL ORDER BY s.name;
SELECT COUNT(*) AS wierszy_w_tabeli, SUM(CASE WHEN Status = 7 THEN 1 ELSE 0 END) AS status7 FROM dbo.Orders;
GO
