-- 01-setup.sql
-- Baza PspMulti: dbo.Ev z DWIEMA skosnymi kolumnami (TenantId, Region) + trzecia rownomierna (Kind).
-- Skosnosc (max EQ_ROWS / min EQ_ROWS w histogramie) jest ekstremalna (>= 100 000), zeby PSP w ogole ruszyl (patrz #14).
SET NOCOUNT ON;
IF DB_ID('PspMulti') IS NOT NULL
BEGIN
    ALTER DATABASE PspMulti SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE PspMulti;
END
GO
CREATE DATABASE PspMulti;
GO
ALTER DATABASE PspMulti SET QUERY_STORE = ON (OPERATION_MODE = READ_WRITE, QUERY_CAPTURE_MODE = ALL, DATA_FLUSH_INTERVAL_SECONDS = 60);
GO
USE PspMulti;
GO
SELECT @@VERSION AS wersja;
SELECT compatibility_level FROM sys.databases WHERE name = 'PspMulti';
GO
CREATE TABLE dbo.Ev
(
    EventId  int IDENTITY(1,1) CONSTRAINT PK_Ev PRIMARY KEY,
    TenantId int NOT NULL,
    Region   int NOT NULL,
    Kind     int NOT NULL,
    Payload  char(200) NOT NULL CONSTRAINT DF_Ev_Payload DEFAULT 'x'
);
GO
;WITH n AS
(
    SELECT TOP (200000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i
    FROM sys.all_objects a CROSS JOIN sys.all_objects b
)
INSERT dbo.Ev (TenantId, Region, Kind)
SELECT CASE WHEN i <= 190000 THEN 1 WHEN i = 190001 THEN 2 ELSE 3 + (i % 50) END,   -- TenantId: gigant 190000, tenant 2 = 1 wiersz
       CASE WHEN i = 5 THEN 2 WHEN i % 10 = 0 THEN 3 + (i % 7) ELSE 1 END,          -- Region: dominujacy 1, region 2 = 1 wiersz
       i % 20                                                                        -- Kind: rownomiernie
FROM n;
GO
CREATE NONCLUSTERED INDEX IX_Ev_TenantId ON dbo.Ev (TenantId);
CREATE NONCLUSTERED INDEX IX_Ev_Region   ON dbo.Ev (Region);
CREATE NONCLUSTERED INDEX IX_Ev_Kind     ON dbo.Ev (Kind);
GO
SELECT 'TenantId' AS kolumna, TenantId AS wartosc, COUNT(*) AS wierszy FROM dbo.Ev WHERE TenantId IN (1, 2) GROUP BY TenantId
UNION ALL
SELECT 'Region', Region, COUNT(*) FROM dbo.Ev WHERE Region IN (1, 2) GROUP BY Region
ORDER BY 1, 2;
GO
