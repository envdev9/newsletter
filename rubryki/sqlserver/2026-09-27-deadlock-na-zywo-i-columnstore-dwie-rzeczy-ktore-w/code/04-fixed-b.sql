-- 04-fixed-b.sql - SESJA B po naprawie: przelew Bartek(2) -> Alicja(1).
-- Kierunek przelewu odwrotny, ale kolejnosc blokowania ta sama: najpierw wiersz 1, potem 2.
USE PrasowkaLock;
SET NOCOUNT ON;
DECLARE @from int = 2, @to int = 1, @amount decimal(12,2) = 10;
BEGIN TRY
    BEGIN TRAN;
    SELECT AccountId FROM dbo.Accounts WITH (UPDLOCK, ROWLOCK) WHERE AccountId IN (@from, @to) ORDER BY AccountId;
    PRINT 'B: mam blokady na obu wierszach (1 potem 2), czekam 3 s...';
    WAITFOR DELAY '00:00:03';
    UPDATE dbo.Accounts SET Balance = Balance - @amount WHERE AccountId = @from;
    UPDATE dbo.Accounts SET Balance = Balance + @amount WHERE AccountId = @to;
    COMMIT;
    PRINT 'B: COMMIT';
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK;
    PRINT CONCAT('B: BLAD ', ERROR_NUMBER(), ' - ', ERROR_MESSAGE());
END CATCH
GO
