-- SPILL: zmienna tabelowa + hint kompatybilnosci 140 (bez deferred compilation) => estymata 1 wiersz,
-- rzeczywiscie 500 000. Sort dostaje grant "na 1 wiersz" i wylewa sie do tempdb.
USE PrasowkaAiSpill1006;
SET NOCOUNT ON;
DECLARE @t TABLE (Id int NOT NULL, Pad varchar(60) NOT NULL);
INSERT @t (Id, Pad)
SELECT value, CONVERT(varchar(36), NEWID()) + REPLICATE('x', 20) FROM GENERATE_SERIES(1, 500000);

SET STATISTICS XML ON;
SELECT MAX(x.rn) AS MaxRn
FROM (SELECT ROW_NUMBER() OVER (ORDER BY Pad) AS rn FROM @t) AS x
OPTION (USE HINT('QUERY_OPTIMIZER_COMPATIBILITY_LEVEL_140'));
SET STATISTICS XML OFF;
