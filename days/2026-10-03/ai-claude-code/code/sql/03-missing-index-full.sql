-- Ten sam predykat, ale dodatkowy ORDER BY zmusza optymalizator do pelnego
-- (FULL) cost-based szukania planu - i tym razem MissingIndexGroup sie pojawia.
USE PrasowkaAiPlanReview;
GO
SET STATISTICS XML ON;
GO
SELECT OrderId, CustomerId, OrderStatus, TotalAmount
FROM dbo.Orders
WHERE CustomerId = 42
ORDER BY CreatedAt DESC;
GO
SET STATISTICS XML OFF;
GO
