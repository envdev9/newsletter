-- 07-setup-serial.sql - baza PrasowkaSerial: generator numerow faktur per tenant (klasyczny wyscig "MAX+1").
SET NOCOUNT ON;
IF DB_ID('PrasowkaSerial') IS NOT NULL
BEGIN
    ALTER DATABASE PrasowkaSerial SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE PrasowkaSerial;
END
GO
CREATE DATABASE PrasowkaSerial;
GO
USE PrasowkaSerial;
GO
CREATE TABLE dbo.Invoices
(
    InvoiceId  bigint       IDENTITY(1,1) NOT NULL CONSTRAINT PK_Invoices PRIMARY KEY CLUSTERED,
    TenantId   int          NOT NULL,
    InvoiceNo  int          NOT NULL,
    CreatedAt  datetime2(3) NOT NULL CONSTRAINT DF_Invoices_CreatedAt DEFAULT SYSUTCDATETIME()
);
GO
CREATE NONCLUSTERED INDEX IX_Invoices_Tenant ON dbo.Invoices (TenantId, InvoiceNo);
GO
INSERT dbo.Invoices (TenantId, InvoiceNo) VALUES (1, 1);
GO
SELECT * FROM dbo.Invoices;
GO
