-- 12-delete.sql: kasujemy cala "wiadomosc" Status = 3 (300 000 wierszy = 25%).
SET NOCOUNT ON;
USE NcciClean;
GO
DELETE FROM dbo.Orders WHERE Status = 3;
SELECT @@ROWCOUNT AS skasowano;
GO
