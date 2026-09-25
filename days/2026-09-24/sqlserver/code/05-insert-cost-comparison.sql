-- 05-insert-cost-comparison.sql
-- Druga strona medalu: indeks przyspiesza odczyt, ale ktoś musi za to
-- zapłacić przy zapisie. Przy każdym INSERT/UPDATE/DELETE, który zmienia
-- zaindeksowaną kolumnę, SQL Server oprócz zapisu do tabeli głównej musi
-- też dopisać/przesunąć wpis w B-drzewie indeksu (czasem to "page split" -
-- podział strony indeksu, gdy nowa wartość nie mieści się tam, gdzie
-- powinna trafić w sortowaniu). Im więcej indeksów, tym więcej takiej
-- dodatkowej pracy przy każdym zapisie.
--
-- Żeby to pokazać namacalnie, robimy dwie identyczne kopie tabeli Orders:
-- jedną BEZ indeksu na CustomerId, drugą Z indeksem - i mierzymy czas
-- wstawienia tej samej porcji 20 000 nowych wierszy do obu.

USE PrasowkaDemo;
GO

IF OBJECT_ID('dbo.OrdersNoIndex', 'U') IS NOT NULL DROP TABLE dbo.OrdersNoIndex;
IF OBJECT_ID('dbo.OrdersWithIndex', 'U') IS NOT NULL DROP TABLE dbo.OrdersWithIndex;
GO

SELECT * INTO dbo.OrdersNoIndex FROM dbo.Orders;
SELECT * INTO dbo.OrdersWithIndex FROM dbo.Orders;
GO

ALTER TABLE dbo.OrdersNoIndex ADD CONSTRAINT PK_OrdersNoIndex PRIMARY KEY CLUSTERED (OrderId);
ALTER TABLE dbo.OrdersWithIndex ADD CONSTRAINT PK_OrdersWithIndex PRIMARY KEY CLUSTERED (OrderId);
GO

CREATE NONCLUSTERED INDEX IX_OrdersWithIndex_CustomerId ON dbo.OrdersWithIndex (CustomerId);
GO

PRINT '--- INSERT 20 000 wierszy do tabeli BEZ indeksu na CustomerId ---';
SET STATISTICS TIME ON;
GO

;WITH L0 AS (SELECT 1 AS c UNION ALL SELECT 1),
L1 AS (SELECT 1 AS c FROM L0 A CROSS JOIN L0 B),
L2 AS (SELECT 1 AS c FROM L1 A CROSS JOIN L1 B),
L3 AS (SELECT 1 AS c FROM L2 A CROSS JOIN L2 B),
L4 AS (SELECT 1 AS c FROM L3 A CROSS JOIN L3 B),
Nums AS (SELECT TOP (20000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS N FROM L4)
INSERT INTO dbo.OrdersNoIndex (CustomerId, OrderDate, Amount, Status)
SELECT
    1 + ABS(CHECKSUM(NEWID())) % 50000,
    DATEADD(DAY, -(ABS(CHECKSUM(NEWID())) % 1000), '2026-09-24'),
    CAST(RAND(CHECKSUM(NEWID())) * 5000 AS DECIMAL(10,2)),
    'New'
FROM Nums;
GO

SET STATISTICS TIME OFF;
GO

PRINT '--- INSERT 20 000 wierszy do tabeli Z indeksem na CustomerId ---';
SET STATISTICS TIME ON;
GO

;WITH L0 AS (SELECT 1 AS c UNION ALL SELECT 1),
L1 AS (SELECT 1 AS c FROM L0 A CROSS JOIN L0 B),
L2 AS (SELECT 1 AS c FROM L1 A CROSS JOIN L1 B),
L3 AS (SELECT 1 AS c FROM L2 A CROSS JOIN L2 B),
L4 AS (SELECT 1 AS c FROM L3 A CROSS JOIN L3 B),
Nums AS (SELECT TOP (20000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS N FROM L4)
INSERT INTO dbo.OrdersWithIndex (CustomerId, OrderDate, Amount, Status)
SELECT
    1 + ABS(CHECKSUM(NEWID())) % 50000,
    DATEADD(DAY, -(ABS(CHECKSUM(NEWID())) % 1000), '2026-09-24'),
    CAST(RAND(CHECKSUM(NEWID())) * 5000 AS DECIMAL(10,2)),
    'New'
FROM Nums;
GO

SET STATISTICS TIME OFF;
GO

-- Sprzątanie po tym eksperymencie (tabela Orders z indeksem z kroku 03/04
-- zostaje nietknięta).
DROP TABLE dbo.OrdersNoIndex;
DROP TABLE dbo.OrdersWithIndex;
GO
