-- 01-create-table-and-data.sql
-- Baza PrasowkaStats + tabela dbo.Orders z CELOWO SKOSNYM rozkładem CustomerId:
--   * klient 1 ("hurtownik") ma 200 000 zamówień (40% tabeli),
--   * pozostałe 300 000 wierszy rozrzucone po ok. 50 000 zwykłych klientów
--     (średnio kilka zamówień na klienta).
-- Dane są deterministyczne (bez NEWID/RAND), więc liczby powtarzają się
-- między uruchomieniami.
-- Jest tylko wąski indeks IX_Orders_CustomerId (bez INCLUDE) - covering
-- index dołożymy dopiero w kroku 05.

IF DB_ID('PrasowkaStats') IS NOT NULL
BEGIN
    ALTER DATABASE PrasowkaStats SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE PrasowkaStats;
END
GO

CREATE DATABASE PrasowkaStats;
GO

USE PrasowkaStats;
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
    CASE WHEN N % 5 < 2 THEN 1                          -- 40% wierszy = klient 1
         ELSE 2 + CAST((N * 7919) % 49999 AS INT)       -- reszta: klienci 2..50000
    END                                                  AS CustomerId,
    DATEADD(DAY, -CAST(N % 1000 AS INT), '2026-09-25')   AS OrderDate,
    CAST((N % 5000) + 0.99 AS DECIMAL(10,2))             AS Amount,
    CASE N % 4 WHEN 0 THEN 'New' WHEN 1 THEN 'Shipped'
               WHEN 2 THEN 'Delivered' ELSE 'Cancelled' END AS Status
FROM Nums;
GO

-- Zwykły, WĄSKI indeks nieklastrowany na CustomerId (tak jak w wydaniu #1).
CREATE NONCLUSTERED INDEX IX_Orders_CustomerId ON dbo.Orders (CustomerId);
GO

SELECT COUNT(*) AS WierszyWTabeli FROM dbo.Orders;
GO

-- Rozkład: ile zamówień ma klient "hurtownik" (1) i klient "zwykły" (4242).
SELECT CustomerId, COUNT(*) AS Zamowien
FROM dbo.Orders
WHERE CustomerId IN (1, 4242)
GROUP BY CustomerId
ORDER BY CustomerId;
GO

-- Rozmiar tabeli i indeksu w stronach (8 KB) - przyda się do interpretacji logical reads.
SELECT i.name AS Indeks, i.type_desc AS Typ, ps.in_row_data_page_count AS StronDanych
FROM sys.indexes i
JOIN sys.dm_db_partition_stats ps
  ON ps.object_id = i.object_id AND ps.index_id = i.index_id
WHERE i.object_id = OBJECT_ID('dbo.Orders')
ORDER BY i.index_id;
GO
