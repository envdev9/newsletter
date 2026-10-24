-- 04-fixed-a.sql - SESJA A po naprawie: przelew Alicja(1) -> Bartek(2).
-- Regula: ZAWSZE blokuj wiersze w rosnacej kolejnosci AccountId, niezaleznie od kierunku przelewu.
USE PrasowkaLock;
SET NOCOUNT ON;
DECLARE @from int = 1, @to int = 2, @amount decimal(12,2) = 10;
BEGIN TRY
    BEGIN TRAN;
    -- krok 1: zablokuj OBA wiersze od razu, w kolejnosci klucza (jedno polecenie, deterministyczna kolejnosc)
    SELECT AccountId FROM dbo.Accounts WITH (UPDLOCK, ROWLOCK) WHERE AccountId IN (@from, @to) ORDER BY AccountId;
    PRINT 'A: mam blokady na obu wierszach (1 potem 2), czekam 3 s...';
    WAITFOR DELAY '00:00:03';
    UPDATE dbo.Accounts SET Balance = Balance - @amount WHERE AccountId = @from;
    UPDATE dbo.Accounts SET Balance = Balance + @amount WHERE AccountId = @to;
    COMMIT;
    PRINT 'A: COMMIT';
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK;
    PRINT CONCAT('A: BLAD ', ERROR_NUMBER(), ' - ', ERROR_MESSAGE());
END CATCH
GO
