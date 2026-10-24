-- 09-race-serializable-a.sql - SESJA A: ten sam generator, ale pod SERIALIZABLE.
USE PrasowkaSerial;
GO
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
GO
DECLARE @next int;
BEGIN TRAN;
SELECT @next = MAX(InvoiceNo) + 1 FROM dbo.Invoices WHERE TenantId = 1;
PRINT 'A: policzylem nastepny numer = ' + CAST(@next AS varchar(10)) + ', czekam 3 s...';
WAITFOR DELAY '00:00:03';
INSERT dbo.Invoices (TenantId, InvoiceNo) VALUES (1, @next);
COMMIT;
PRINT 'A: COMMIT - wstawilem InvoiceNo = ' + CAST(@next AS varchar(10));
GO
