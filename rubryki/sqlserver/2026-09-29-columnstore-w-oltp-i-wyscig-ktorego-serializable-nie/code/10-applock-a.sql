-- 10-applock-a.sql - SESJA A: ten sam generator, tym razem chroniony sp_getapplock (READ COMMITTED wystarczy).
USE PrasowkaSerial;
GO
DECLARE @next int, @lockResult int;
BEGIN TRAN;
EXEC @lockResult = sp_getapplock
    @Resource = 'InvoiceGen:Tenant:1',
    @LockMode = 'Exclusive',
    @LockOwner = 'Transaction',
    @LockTimeout = 15000;
PRINT 'A: sp_getapplock wynik = ' + CAST(@lockResult AS varchar(10)) + ' (0/1 = OK, ujemne = timeout/blad)';
SELECT @next = MAX(InvoiceNo) + 1 FROM dbo.Invoices WHERE TenantId = 1;
PRINT 'A: policzylem nastepny numer = ' + CAST(@next AS varchar(10)) + ', czekam 3 s...';
WAITFOR DELAY '00:00:03';
INSERT dbo.Invoices (TenantId, InvoiceNo) VALUES (1, @next);
COMMIT;  -- zwalnia tez applock (@LockOwner = 'Transaction')
PRINT 'A: COMMIT - wstawilem InvoiceNo = ' + CAST(@next AS varchar(10));
GO
