-- MEMORY-GRANT: kolumna varchar(4000) z krotkimi wartosciami. Optymalizator zaklada ~polowe
-- deklarowanej dlugosci na wiersz, wiec sort dostaje ogromny grant, a wykorzystuje ulamek.
USE PrasowkaAiSpill1006;
SET NOCOUNT ON;
CREATE TABLE dbo.Wide (Id int NOT NULL PRIMARY KEY, Note varchar(4000) NOT NULL);
INSERT dbo.Wide (Id, Note)
SELECT value, 'n' + CONVERT(varchar(12), value) FROM GENERATE_SERIES(1, 100000);

SET STATISTICS XML ON;
SELECT MAX(x.rn) AS MaxRn
FROM (SELECT ROW_NUMBER() OVER (ORDER BY Note) AS rn FROM dbo.Wide) AS x;
SET STATISTICS XML OFF;
