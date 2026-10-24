-- 10-applock-b.sql - SESJA B: startuje ok. 1 s po A, ten sam sp_getapplock - musi poczekac na A.
USE PrasowkaSerial;
GO
WAITFOR DELAY '00:00:01';
DECLARE @next int, @lockResult int, @start datetime2 = SYSUTCDATETIME();
BEGIN TRAN;
EXEC @lockResult = sp_getapplock
    @Resource = 'InvoiceGen:Tenant:1',
    @LockMode = 'Exclusive',
    @LockOwner = 'Transaction',
    @LockTimeout = 15000;
PRINT 'B: sp_getapplock wynik = ' + CAST(@lockResult AS varchar(10))
    + ', czekalem ' + CAST(DATEDIFF(MILLISECOND, @start, SYSUTCDATETIME()) AS varchar(10)) + ' ms na blokade';
SELECT @next = MAX(InvoiceNo) + 1 FROM dbo.Invoices WHERE TenantId = 1;
PRINT 'B: policzylem nastepny numer = ' + CAST(@next AS varchar(10)) + ' (widze juz insert od A)';
INSERT dbo.Invoices (TenantId, InvoiceNo) VALUES (1, @next);
COMMIT;
PRINT 'B: COMMIT - wstawilem InvoiceNo = ' + CAST(@next AS varchar(10));
GO
