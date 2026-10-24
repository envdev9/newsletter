-- 12-prime-bad-plan.sql - klasyczny parameter sniffing: pierwsze wywolanie "halasliwym" tenantem zatruwa plan cache.
USE PrasowkaQueryHints;
GO
-- Wyniki EXEC ladujemy do tabeli tymczasowej (#trash), zeby nie zasypac konsoli 190 000 wierszy -
-- STATISTICS IO/TIME i tak mierzy PRAWDZIWE wykonanie zapytania, tylko nie drukujemy gridu.
CREATE TABLE #trash (EventId bigint, TenantId int, Payload varchar(200));
GO
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
GO
PRINT '--- Pierwsze wywolanie: TenantId=1 (190 000 z 200 000 wierszy) - kompiluje i CACHUJE plan ---';
TRUNCATE TABLE #trash;
INSERT #trash EXEC dbo.GetEventsByTenant @TenantId = 1;
GO
PRINT '--- Drugie wywolanie: TenantId=2 (100 wierszy) - DOSTAJE ten sam, zly plan z cache ---';
TRUNCATE TABLE #trash;
INSERT #trash EXEC dbo.GetEventsByTenant @TenantId = 2;
GO
SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
GO
DROP TABLE #trash;
GO
