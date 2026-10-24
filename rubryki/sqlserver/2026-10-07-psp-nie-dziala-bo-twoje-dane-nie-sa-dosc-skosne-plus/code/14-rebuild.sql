-- 14-rebuild.sql
SET NOCOUNT ON;
USE NcciClean;
GO
ALTER INDEX NCCI_Orders ON dbo.Orders REBUILD;
GO
