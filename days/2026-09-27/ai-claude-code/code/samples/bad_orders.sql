-- Przyklad "zle": schemat + zapytania z typowymi antywzorcami (do testu skanera).
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

-- 1) SELECT * + funkcja na kolumnie + NOLOCK
SELECT *
FROM dbo.Orders WITH (NOLOCK)
WHERE YEAR(CreatedAt) = 2026 AND MONTH(CreatedAt) = 9;

-- 2) wiodacy wildcard + literal N'' na kolumnie VARCHAR
SELECT c.CustomerId, c.Name
FROM dbo.Customers AS c
WHERE c.Email LIKE '%@example.com' OR c.Email = N'jan@example.com';

-- 3) NOT IN z podzapytaniem
SELECT c.CustomerId
FROM dbo.Customers AS c
WHERE c.CustomerId NOT IN (SELECT o.CustomerId FROM dbo.Orders AS o);

-- 4) TOP bez ORDER BY  (SELECT * w komentarzu ma byc zignorowane: SELECT * FROM x)
SELECT TOP 10 OrderId, Total FROM dbo.Orders;
