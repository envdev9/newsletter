-- 10-setup-ncci.sql
-- Baza NcciClean: tabela OLTP dbo.Orders (klucz klastrowany) + NONCLUSTERED COLUMNSTORE INDEX, 1 200 000 wierszy, 25% ze Status = 3.
SET NOCOUNT ON;
IF DB_ID('NcciClean') IS NOT NULL
BEGIN
    ALTER DATABASE NcciClean SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE NcciClean;
END
GO
CREATE DATABASE NcciClean;
GO
USE NcciClean;
GO
ALTER DATABASE NcciClean SET RECOVERY SIMPLE;
-- Wlacza dm_exec_query_plan_stats (plan z ActualRows ostatniego wykonania) - uzywamy go do porownania Estimated vs Actual
ALTER DATABASE SCOPED CONFIGURATION SET LAST_QUERY_PLAN_STATS = ON;
GO
CREATE TABLE dbo.Orders
(
    OrderId    int           NOT NULL CONSTRAINT PK_Orders PRIMARY KEY CLUSTERED,
    CustomerId int           NOT NULL,
    Status     tinyint       NOT NULL,
    Amount     decimal(10,2) NOT NULL,
    CreatedAt  datetime2(0)  NOT NULL
);
GO
;WITH n AS
(
    SELECT TOP (1200000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i
    FROM sys.all_objects a CROSS JOIN sys.all_objects b CROSS JOIN sys.all_objects c
)
INSERT dbo.Orders (OrderId, CustomerId, Status, Amount, CreatedAt)
SELECT i, (i * 7919) % 40000, CASE WHEN i % 4 = 0 THEN 3 ELSE i % 3 END, (i % 1000) / 10.0 + 1, DATEADD(MINUTE, -i, '2026-10-07')
FROM n;
GO
CREATE NONCLUSTERED COLUMNSTORE INDEX NCCI_Orders ON dbo.Orders (CustomerId, Status, Amount, CreatedAt);
GO
SELECT Status, COUNT(*) AS Wierszy FROM dbo.Orders GROUP BY Status ORDER BY Status;
GO
