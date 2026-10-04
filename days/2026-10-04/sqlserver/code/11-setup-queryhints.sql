-- 11-setup-queryhints.sql - baza PrasowkaQueryHints: tabela ze SKOSNYM rozkladem (klasyczny parameter sniffing)
-- + Query Store wlaczony od razu (potrzebny do sp_query_store_set_hints).
SET NOCOUNT ON;
IF DB_ID('PrasowkaQueryHints') IS NOT NULL
BEGIN
    ALTER DATABASE PrasowkaQueryHints SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE PrasowkaQueryHints;
END
GO
CREATE DATABASE PrasowkaQueryHints;
GO
ALTER DATABASE PrasowkaQueryHints SET RECOVERY SIMPLE;
GO
ALTER DATABASE PrasowkaQueryHints SET QUERY_STORE = ON;
ALTER DATABASE PrasowkaQueryHints SET QUERY_STORE (OPERATION_MODE = READ_WRITE, QUERY_CAPTURE_MODE = ALL);
GO
USE PrasowkaQueryHints;
GO
CREATE TABLE dbo.Events
(
    EventId  bigint       IDENTITY(1,1) NOT NULL CONSTRAINT PK_Events PRIMARY KEY CLUSTERED,
    TenantId int          NOT NULL,
    Payload  varchar(200) NOT NULL
);
GO
CREATE NONCLUSTERED INDEX IX_Events_TenantId ON dbo.Events (TenantId);
GO
-- Tenant 1 to "halasliwy" najemca: 190 000 z 200 000 wierszy (95%).
INSERT dbo.Events WITH (TABLOCK) (TenantId, Payload)
SELECT 1, REPLICATE('x', 100)
FROM (SELECT TOP (190000) 1 AS x FROM sys.all_columns a CROSS JOIN sys.all_columns b) AS n;
GO
-- Tenanci 2..101: po 100 wierszy kazdy (razem 10 000 wierszy) - typowy, maly najemca.
;WITH tenants AS (SELECT TOP (100) 1 + ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS TenantId FROM sys.all_columns)
INSERT dbo.Events (TenantId, Payload)
SELECT t.TenantId, REPLICATE('y', 100)
FROM tenants t
CROSS JOIN (SELECT TOP (100) 1 AS x FROM sys.all_columns) AS reps;
GO
CREATE OR ALTER PROCEDURE dbo.GetEventsByTenant
    @TenantId int
AS
BEGIN
    SELECT EventId, TenantId, Payload
    FROM dbo.Events
    WHERE TenantId = @TenantId;
END
GO
SELECT TenantId, COUNT(*) AS Ile FROM dbo.Events WHERE TenantId IN (1,2) GROUP BY TenantId ORDER BY TenantId;
SELECT COUNT_BIG(*) AS WierszyRazem FROM dbo.Events;
GO
