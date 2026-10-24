-- 09-race-serializable-b.sql - SESJA B: startuje ok. 1 s po A, SERIALIZABLE, TRY/CATCH na 1205 (deadlock mozliwy).
USE PrasowkaSerial;
GO
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
GO
WAITFOR DELAY '00:00:01';
DECLARE @next int;
BEGIN TRAN;
BEGIN TRY
    SELECT @next = MAX(InvoiceNo) + 1 FROM dbo.Invoices WHERE TenantId = 1;
    PRINT 'B: policzylem nastepny numer = ' + CAST(@next AS varchar(10)) + ', czekam 3 s...';
    WAITFOR DELAY '00:00:03';
    INSERT dbo.Invoices (TenantId, InvoiceNo) VALUES (1, @next);
    COMMIT;
    PRINT 'B: COMMIT - wstawilem InvoiceNo = ' + CAST(@next AS varchar(10));
END TRY
BEGIN CATCH
    PRINT 'B: BLAD ' + CAST(ERROR_NUMBER() AS varchar(10)) + ' - ' + ERROR_MESSAGE();
    IF XACT_STATE() <> 0 ROLLBACK TRAN;
END CATCH
GO
