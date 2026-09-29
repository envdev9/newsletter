-- 08-race-readcommitted-b.sql - SESJA B: startuje ok. 1 s po A, ten sam generator, READ COMMITTED.
USE PrasowkaSerial;
GO
WAITFOR DELAY '00:00:01';
DECLARE @next int;
BEGIN TRAN;
SELECT @next = MAX(InvoiceNo) + 1 FROM dbo.Invoices WHERE TenantId = 1;
PRINT 'B: policzylem nastepny numer = ' + CAST(@next AS varchar(10)) + ', czekam 3 s...';
WAITFOR DELAY '00:00:03';
INSERT dbo.Invoices (TenantId, InvoiceNo) VALUES (1, @next);
COMMIT;
PRINT 'B: COMMIT - wstawilem InvoiceNo = ' + CAST(@next AS varchar(10));
GO
