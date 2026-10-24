-- 02-deadlock-a.sql - SESJA A: przelew Alicja -> Bartek. Blokuje wiersz 1, potem 2.
-- Uruchom rownolegle z 02-deadlock-b.sql (B blokuje w odwrotnej kolejnosci: 2, potem 1).
USE PrasowkaLock;
SET NOCOUNT ON;
BEGIN TRY
    BEGIN TRAN;
    UPDATE dbo.Accounts SET Balance = Balance - 10 WHERE AccountId = 1;
    PRINT 'A: mam blokade na wierszu 1, czekam 3 s...';
    WAITFOR DELAY '00:00:03';
    PRINT 'A: probuje wiersz 2';
    UPDATE dbo.Accounts SET Balance = Balance + 10 WHERE AccountId = 2;
    COMMIT;
    PRINT 'A: COMMIT - sesja A przezyla';
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK;
    PRINT CONCAT('A: BLAD ', ERROR_NUMBER(), ' - ', ERROR_MESSAGE());
END CATCH
GO
