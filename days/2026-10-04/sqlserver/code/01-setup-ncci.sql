-- 01-setup-ncci.sql - baza PrasowkaNcciDml + tabela OLTP dbo.Orders (klucz klastrowany, 1 200 000 wierszy).
-- Ten sam generator danych co w wydaniu #7 - tu sprawdzamy co dzieje sie przy UPDATE/DELETE na NCCI.
SET NOCOUNT ON;
IF DB_ID('PrasowkaNcciDml') IS NOT NULL
BEGIN
    ALTER DATABASE PrasowkaNcciDml SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE PrasowkaNcciDml;
END
GO
CREATE DATABASE PrasowkaNcciDml;
GO
ALTER DATABASE PrasowkaNcciDml SET RECOVERY SIMPLE;
GO
USE PrasowkaNcciDml;
GO
CREATE TABLE dbo.Orders
(
    OrderId    bigint        IDENTITY(1,1) NOT NULL CONSTRAINT PK_Orders PRIMARY KEY CLUSTERED,
    CustomerId int           NOT NULL,
    OrderDate  date          NOT NULL,
    Status     tinyint       NOT NULL,  -- 0=Nowe,1=Oplacone,2=Wyslane,3=Anulowane
    Amount     decimal(10,2) NOT NULL
);
GO
;WITH n AS
(
    SELECT TOP (1200000) CAST(ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS bigint) AS i
    FROM sys.all_columns a CROSS JOIN sys.all_columns b
)
INSERT dbo.Orders WITH (TABLOCK) (CustomerId, OrderDate, Status, Amount)
SELECT CAST(i % 40000 + 1 AS int),
       DATEADD(DAY, CAST(i % 730 AS int), CAST('2024-01-01' AS date)),
       CAST(i % 4 AS tinyint),
       CAST(((i * 31) % 90000) / 100.0 + 1 AS decimal(10,2))
FROM n
ORDER BY i;
GO
SELECT COUNT_BIG(*) AS Wierszy,
       SUM(CASE WHEN Status = 3 THEN 1 ELSE 0 END) AS Anulowane
FROM dbo.Orders;
GO
