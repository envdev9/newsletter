-- 01-create-table-and-data.sql
-- Tworzy bazę PrasowkaDemo, tabelę dbo.Orders i wypełnia ją 500 000 wierszy
-- testowych. Na tym etapie tabela ma TYLKO klucz główny (klastrowany indeks
-- na OrderId) - kolumna CustomerId, po której będziemy filtrować, nie jest
-- jeszcze niczym zaindeksowana.

IF DB_ID('PrasowkaDemo') IS NULL
BEGIN
    CREATE DATABASE PrasowkaDemo;
END
GO

USE PrasowkaDemo;
GO

IF OBJECT_ID('dbo.Orders', 'U') IS NOT NULL
    DROP TABLE dbo.Orders;
GO

CREATE TABLE dbo.Orders
(
    OrderId     INT IDENTITY(1,1) PRIMARY KEY CLUSTERED,
    CustomerId  INT           NOT NULL,
    OrderDate   DATE          NOT NULL,
    Amount      DECIMAL(10,2) NOT NULL,
    Status      VARCHAR(20)   NOT NULL
);
GO

-- Generator 500 000 wierszy BEZ pętli i bez tabeli pomocniczej: krzyżujemy
-- dwuwierszową tabelę samą ze sobą kilka razy (2 -> 4 -> 16 -> 256 -> 65536
-- -> ~4.3 mld), a TOP(500000) przycina wynik do potrzebnej liczby. To
-- standardowy wzorzec T-SQL na "tabelę liczb" - optymalizator SQL Servera
-- widzi TOP i nie materializuje pełnego iloczynu kartezjańskiego.
;WITH L0 AS (SELECT 1 AS c UNION ALL SELECT 1),
L1 AS (SELECT 1 AS c FROM L0 A CROSS JOIN L0 B),
L2 AS (SELECT 1 AS c FROM L1 A CROSS JOIN L1 B),
L3 AS (SELECT 1 AS c FROM L2 A CROSS JOIN L2 B),
L4 AS (SELECT 1 AS c FROM L3 A CROSS JOIN L3 B),
L5 AS (SELECT 1 AS c FROM L4 A CROSS JOIN L4 B),
Nums AS (SELECT TOP (500000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS N FROM L5)
INSERT INTO dbo.Orders (CustomerId, OrderDate, Amount, Status)
SELECT
    1 + ABS(CHECKSUM(NEWID())) % 50000                            AS CustomerId,
    DATEADD(DAY, -(ABS(CHECKSUM(NEWID())) % 1000), '2026-09-24')  AS OrderDate,
    CAST(RAND(CHECKSUM(NEWID())) * 5000 AS DECIMAL(10,2))         AS Amount,
    CASE ABS(CHECKSUM(NEWID())) % 4
        WHEN 0 THEN 'New'
        WHEN 1 THEN 'Shipped'
        WHEN 2 THEN 'Delivered'
        ELSE 'Cancelled'
    END                                                            AS Status
FROM Nums;
GO

SELECT COUNT(*) AS WierszyWTabeli FROM dbo.Orders;
GO

-- Ile zamówień ma akurat CustomerId = 1 - to na nim pokażemy różnicę.
-- Przy 500 000 wierszach i 50 000 możliwych klientów wychodzi średnio ~10
-- zamówień na klienta - to celowo mało, żeby indeks miał sens (szukamy
-- garstki wierszy w morzu pół miliona).
SELECT CustomerId, COUNT(*) AS Zamowien
FROM dbo.Orders
WHERE CustomerId = 1
GROUP BY CustomerId;
GO
