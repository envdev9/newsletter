-- 06-facts-setup.sql - baza PrasowkaCS + tabela faktow sprzedazy jako ZWYKLY rowstore (5 000 000 wierszy, dane deterministyczne).
SET NOCOUNT ON;
IF DB_ID('PrasowkaCS') IS NOT NULL
BEGIN
    ALTER DATABASE PrasowkaCS SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE PrasowkaCS;
END
GO
CREATE DATABASE PrasowkaCS;
GO
ALTER DATABASE PrasowkaCS SET RECOVERY SIMPLE;
GO
USE PrasowkaCS;
GO
CREATE TABLE dbo.FactSales_Row
(
    SaleId    bigint        NOT NULL CONSTRAINT PK_FactSales_Row PRIMARY KEY CLUSTERED,
    SaleDate  date          NOT NULL,
    ProductId int           NOT NULL,
    StoreId   int           NOT NULL,
    Quantity  smallint      NOT NULL,
    Amount    decimal(10,2) NOT NULL
);
GO
;WITH n AS
(
    SELECT TOP (5000000) CAST(ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS bigint) AS i
    FROM sys.all_columns a CROSS JOIN sys.all_columns b
)
INSERT dbo.FactSales_Row WITH (TABLOCK) (SaleId, SaleDate, ProductId, StoreId, Quantity, Amount)
SELECT i,
       DATEADD(DAY, CAST(i % 1095 AS int), CAST('2023-01-01' AS date)),
       CAST((i * 7919) % 2000 + 1 AS int),
       CAST(i % 50 + 1 AS int),
       CAST(i % 5 + 1 AS smallint),
       CAST(((i * 31) % 50000) / 100.0 + 1 AS decimal(10,2))
FROM n
ORDER BY i;
GO
SELECT COUNT_BIG(*) AS Wierszy, MIN(SaleDate) AS Od, MAX(SaleDate) AS Do FROM dbo.FactSales_Row;
GO
