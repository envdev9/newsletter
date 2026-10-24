-- To samo, przepisane: zakres zamiast funkcji, NOT EXISTS, jawne kolumny, indeks na FK.
CREATE TABLE dbo.Customers (
    CustomerId INT IDENTITY(1,1) CONSTRAINT PK_Customers PRIMARY KEY,
    Email      VARCHAR(200) NOT NULL,
    Name       NVARCHAR(200) NOT NULL
);

CREATE TABLE dbo.Orders (
    OrderId    INT IDENTITY(1,1) CONSTRAINT PK_Orders PRIMARY KEY,
    CustomerId INT NOT NULL,
    CreatedAt  DATETIME2 NOT NULL,
    Status     TINYINT NOT NULL,
    Total      DECIMAL(18,2) NOT NULL,
    CONSTRAINT FK_Orders_Customers FOREIGN KEY (CustomerId) REFERENCES dbo.Customers (CustomerId)
);

CREATE NONCLUSTERED INDEX IX_Orders_CustomerId ON dbo.Orders (CustomerId) INCLUDE (Total);
CREATE NONCLUSTERED INDEX IX_Orders_CreatedAt  ON dbo.Orders (CreatedAt) INCLUDE (Total);

SELECT OrderId, CustomerId, CreatedAt, Total
FROM dbo.Orders
WHERE CreatedAt >= '2026-09-01' AND CreatedAt < '2026-10-01';

SELECT c.CustomerId, c.Name
FROM dbo.Customers AS c
WHERE c.Email = 'jan@example.com';

SELECT c.CustomerId
FROM dbo.Customers AS c
WHERE NOT EXISTS (SELECT 1 FROM dbo.Orders AS o WHERE o.CustomerId = c.CustomerId);

SELECT TOP 10 OrderId, Total FROM dbo.Orders ORDER BY Total DESC;
