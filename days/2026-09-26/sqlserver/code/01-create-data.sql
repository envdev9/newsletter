-- 01-create-data.sql
-- Baza PrasowkaQS z dwiema tabelami:
--   dbo.Orders - ta sama skosna tabela co w wydaniu #2 (klient 1 = 200 000 z 500 000
--                wierszy), tylko wąski indeks IX_Orders_CustomerId (bez INCLUDE),
--                czyli podatna na parameter sniffing.
--   dbo.Tasks  - "kolejka zadań": 500 000 wierszy, z czego tylko 500 ma Status = 0
--                (oczekujące), reszta Status = 1 (zrobione). Idealna pod filtered index.
-- Dane deterministyczne (bez NEWID/RAND).

IF DB_ID('PrasowkaQS') IS NOT NULL
BEGIN
    ALTER DATABASE PrasowkaQS SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE PrasowkaQS;
END
GO

CREATE DATABASE PrasowkaQS;
GO

USE PrasowkaQS;
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

;WITH L0 AS (SELECT 1 AS c UNION ALL SELECT 1),
L1 AS (SELECT 1 AS c FROM L0 A CROSS JOIN L0 B),
L2 AS (SELECT 1 AS c FROM L1 A CROSS JOIN L1 B),
L3 AS (SELECT 1 AS c FROM L2 A CROSS JOIN L2 B),
L4 AS (SELECT 1 AS c FROM L3 A CROSS JOIN L3 B),
L5 AS (SELECT 1 AS c FROM L4 A CROSS JOIN L4 B),
Nums AS (SELECT TOP (500000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS N FROM L5)
INSERT INTO dbo.Orders (CustomerId, OrderDate, Amount, Status)
SELECT
    CASE WHEN N % 5 < 2 THEN 1
         ELSE 2 + CAST((N * 7919) % 49999 AS INT)
    END,
    DATEADD(DAY, -CAST(N % 1000 AS INT), '2026-09-26'),
    CAST((N % 5000) + 0.99 AS DECIMAL(10,2)),
    CASE N % 4 WHEN 0 THEN 'New' WHEN 1 THEN 'Shipped'
               WHEN 2 THEN 'Delivered' ELSE 'Cancelled' END
FROM Nums;
GO

CREATE NONCLUSTERED INDEX IX_Orders_CustomerId ON dbo.Orders (CustomerId);
GO

CREATE TABLE dbo.Tasks
(
    TaskId    INT IDENTITY(1,1) PRIMARY KEY CLUSTERED,
    Status    TINYINT       NOT NULL,      -- 0 = oczekujace, 1 = zrobione
    CreatedAt DATETIME2(0)  NOT NULL,
    Payload   VARCHAR(100)  NOT NULL
);
GO

;WITH L0 AS (SELECT 1 AS c UNION ALL SELECT 1),
L1 AS (SELECT 1 AS c FROM L0 A CROSS JOIN L0 B),
L2 AS (SELECT 1 AS c FROM L1 A CROSS JOIN L1 B),
L3 AS (SELECT 1 AS c FROM L2 A CROSS JOIN L2 B),
L4 AS (SELECT 1 AS c FROM L3 A CROSS JOIN L3 B),
L5 AS (SELECT 1 AS c FROM L4 A CROSS JOIN L4 B),
Nums AS (SELECT TOP (500000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS N FROM L5)
INSERT INTO dbo.Tasks (Status, CreatedAt, Payload)
SELECT
    CASE WHEN N % 1000 = 0 THEN 0 ELSE 1 END,
    DATEADD(SECOND, N, '2026-01-01'),
    REPLICATE('x', 80)
FROM Nums;
GO

SELECT (SELECT COUNT(*) FROM dbo.Orders) AS Orders,
       (SELECT COUNT(*) FROM dbo.Tasks)  AS Tasks,
       (SELECT COUNT(*) FROM dbo.Tasks WHERE Status = 0) AS TasksPending;
GO

SELECT OBJECT_NAME(i.object_id) AS Tabela, i.name AS Indeks, ps.in_row_data_page_count AS StronDanych
FROM sys.indexes i
JOIN sys.dm_db_partition_stats ps ON ps.object_id = i.object_id AND ps.index_id = i.index_id
WHERE i.object_id IN (OBJECT_ID('dbo.Orders'), OBJECT_ID('dbo.Tasks'))
ORDER BY Tabela, i.index_id;
GO
