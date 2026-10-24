USE PrasowkaAiPlanReview;
GO

IF OBJECT_ID('dbo.Orders', 'U') IS NOT NULL DROP TABLE dbo.Orders;
GO

CREATE TABLE dbo.Orders
(
    OrderId        INT IDENTITY(1,1) PRIMARY KEY,
    CustomerId     INT NOT NULL,
    OrderStatus    VARCHAR(20) NOT NULL,     -- VARCHAR - jak czesto w starszych schematach .NET
    OrderCode      NVARCHAR(30) NOT NULL,
    TotalAmount    DECIMAL(10,2) NOT NULL,
    CreatedAt      DATETIME2 NOT NULL
);
GO

-- 50 000 wierszy: CustomerId rownomiernie 1..5000 (10 zamowien/klienta),
-- OrderStatus mocno skosny: 'Cancelled' tylko 1 na 500 wierszy (100/50000 = rzadka wartosc).
SET NOCOUNT ON;
DECLARE @i INT = 1;
WHILE @i <= 50000
BEGIN
    INSERT INTO dbo.Orders (CustomerId, OrderStatus, OrderCode, TotalAmount, CreatedAt)
    VALUES (
        1 + (@i % 5000),
        CASE WHEN @i % 500 = 0 THEN 'Cancelled' ELSE 'Open' END,
        N'ORD-' + CAST(@i AS NVARCHAR(10)),
        (@i % 1000) + 0.50,
        DATEADD(SECOND, @i, '2026-01-01')
    );
    SET @i += 1;
END
GO

DECLARE @cnt INT = (SELECT COUNT(*) FROM dbo.Orders);
PRINT 'Rows: ' + CAST(@cnt AS VARCHAR(20));
GO
