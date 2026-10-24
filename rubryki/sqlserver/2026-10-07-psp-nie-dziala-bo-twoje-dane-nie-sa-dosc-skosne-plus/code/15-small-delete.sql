-- 15-small-delete.sql
-- Faza 2: PONIZEJ progu auto-update statystyk. Po fazie 1 w tabeli jest 900 000 wierszy; prog auto-update to ok.
-- SQRT(1000 * 900000) = 30 000 zmian (wzor z SQL Server 2016+ dla duzych tabel; nie weryfikowalismy go osobno).
-- Kasujemy 20 000 wierszy ze Status = 2. Po tym kroku NIE odpalamy zadnego zapytania ze Status w predykacie
-- przed pomiarem (16-stats-only.sql), wiec nic nie wywola auto-update.
SET NOCOUNT ON;
USE NcciClean;
GO
DELETE TOP (20000) FROM dbo.Orders WHERE Status = 2;
SELECT @@ROWCOUNT AS skasowano;
GO
