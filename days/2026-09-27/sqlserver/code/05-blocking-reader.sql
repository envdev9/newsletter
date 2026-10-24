-- 05-blocking-reader.sql - czytelnik: zwykly SELECT (READ COMMITTED), mierzymy jak dlugo czekal.
USE PrasowkaLock;
SET NOCOUNT ON;
SELECT is_read_committed_snapshot_on AS RCSI_on FROM sys.databases WHERE name = 'PrasowkaLock';
DECLARE @t0 datetime2 = SYSDATETIME();
SELECT AccountId, Balance FROM dbo.Accounts WHERE AccountId = 1;
PRINT CONCAT('READER: SELECT trwal ', DATEDIFF(MILLISECOND, @t0, SYSDATETIME()), ' ms');
GO
