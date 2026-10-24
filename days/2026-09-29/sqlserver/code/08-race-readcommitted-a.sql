-- 08-race-readcommitted-a.sql - SESJA A: generuje kolejny numer faktury, READ COMMITTED (domyslny poziom izolacji).
USE PrasowkaSerial;
GO
DECLARE @next int;
BEGIN TRAN;
SELECT @next = MAX(InvoiceNo) + 1 FROM dbo.Invoices WHERE TenantId = 1;
PRINT 'A: policzylem nastepny numer = ' + CAST(@next AS varchar(10)) + ', czekam 3 s (np. licze podatek, generuje PDF)...';
WAITFOR DELAY '00:00:03';
INSERT dbo.Invoices (TenantId, InvoiceNo) VALUES (1, @next);
COMMIT;
PRINT 'A: COMMIT - wstawilem InvoiceNo = ' + CAST(@next AS varchar(10));
GO
