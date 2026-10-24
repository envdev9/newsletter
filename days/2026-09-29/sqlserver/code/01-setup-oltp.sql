-- 01-setup-oltp.sql - baza PrasowkaNCCI + tabela OLTP dbo.Orders (klucz klastrowany, 1 200 000 wierszy historycznych).
SET NOCOUNT ON;
IF DB_ID('PrasowkaNCCI') IS NOT NULL
BEGIN
    ALTER DATABASE PrasowkaNCCI SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE PrasowkaNCCI;
END
GO
CREATE DATABASE PrasowkaNCCI;
GO
ALTER DATABASE PrasowkaNCCI SET RECOVERY SIMPLE;
GO
USE PrasowkaNCCI;
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
SELECT COUNT_BIG(*) AS Wierszy, MIN(OrderDate) AS Od, MAX(OrderDate) AS Do FROM dbo.Orders;
GO
