-- 05-blocking-writer.sql - pisarz: aktualizuje wiersz 1 i trzyma transakcje otwarta 6 s (jak dluga transakcja w aplikacji).
USE PrasowkaLock;
SET NOCOUNT ON;
BEGIN TRAN;
UPDATE dbo.Accounts SET Balance = Balance + 1 WHERE AccountId = 1;
PRINT 'WRITER: trzymam blokade X na wierszu 1 przez 6 s';
WAITFOR DELAY '00:00:06';
COMMIT;
PRINT 'WRITER: COMMIT';
GO
