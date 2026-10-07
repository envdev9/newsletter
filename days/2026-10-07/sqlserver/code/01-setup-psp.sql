-- 01-setup-psp.sql
-- Baza PspLab, tabela dbo.Events (skosny rozklad: TenantId=1 ma 95% wierszy), Query Store WLACZONY.
SET NOCOUNT ON;
IF DB_ID('PspLab') IS NOT NULL
BEGIN
    ALTER DATABASE PspLab SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE PspLab;
END
GO
CREATE DATABASE PspLab;
GO
USE PspLab;
GO
SELECT @@VERSION AS wersja;
SELECT compatibility_level FROM sys.databases WHERE name = 'PspLab';
SELECT name, CONVERT(varchar(10), value) AS value FROM sys.database_scoped_configurations WHERE name = 'PARAMETER_SENSITIVE_PLAN_OPTIMIZATION';
GO
CREATE TABLE dbo.Events
(
    EventId  int IDENTITY(1,1) CONSTRAINT PK_Events PRIMARY KEY,
    TenantId int NOT NULL,
    Payload  char(200) NOT NULL CONSTRAINT DF_Events_Payload DEFAULT 'x'
);
GO
;WITH n AS
(
    SELECT TOP (200000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i
    FROM sys.all_objects a CROSS JOIN sys.all_objects b
)
INSERT dbo.Events (TenantId)
SELECT CASE WHEN i <= 190000 THEN 1 ELSE 2 + (i % 100) END FROM n;
GO
CREATE NONCLUSTERED INDEX IX_Events_TenantId ON dbo.Events (TenantId);
GO
SELECT TenantId, COUNT(*) AS Wierszy FROM dbo.Events WHERE TenantId IN (1, 2, 3) GROUP BY TenantId ORDER BY TenantId;
GO
