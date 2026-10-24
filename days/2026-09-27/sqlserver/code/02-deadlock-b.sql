-- 02-deadlock-b.sql - SESJA B: przelew Bartek -> Alicja. Blokuje wiersz 2, potem 1 (ODWROTNA kolejnosc).
USE PrasowkaLock;
SET NOCOUNT ON;
BEGIN TRY
    BEGIN TRAN;
    UPDATE dbo.Accounts SET Balance = Balance - 10 WHERE AccountId = 2;
    PRINT 'B: mam blokade na wierszu 2, czekam 3 s...';
    WAITFOR DELAY '00:00:03';
    PRINT 'B: probuje wiersz 1';
    UPDATE dbo.Accounts SET Balance = Balance + 10 WHERE AccountId = 1;
    COMMIT;
    PRINT 'B: COMMIT - sesja B przezyla';
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK;
    PRINT CONCAT('B: BLAD ', ERROR_NUMBER(), ' - ', ERROR_MESSAGE());
END CATCH
GO
