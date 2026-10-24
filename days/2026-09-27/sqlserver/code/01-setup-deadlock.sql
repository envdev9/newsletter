-- 01-setup-deadlock.sql - baza PrasowkaLock + tabela kont do demo deadlocka i blokad.
SET NOCOUNT ON;
IF DB_ID('PrasowkaLock') IS NOT NULL
BEGIN
    ALTER DATABASE PrasowkaLock SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE PrasowkaLock;
END
GO
CREATE DATABASE PrasowkaLock;
GO
USE PrasowkaLock;
GO
CREATE TABLE dbo.Accounts
(
    AccountId int           NOT NULL CONSTRAINT PK_Accounts PRIMARY KEY,
    Owner     nvarchar(50)  NOT NULL,
    Balance   decimal(12,2) NOT NULL
);
INSERT dbo.Accounts (AccountId, Owner, Balance) VALUES (1, N'Alicja', 1000), (2, N'Bartek', 1000);
SELECT AccountId, Owner, Balance FROM dbo.Accounts;
GO
