-- NO-JOIN-PREDICATE: laczenie bez warunku (zapomniane ON / stary styl FROM a, b bez WHERE).
-- Uwaga: samo COUNT(*) z cross joina NIE daje ostrzezenia - optymalizator spycha agregat pod join
-- (inner strona = 1 wiersz). Dlatego MAX(a.Label + b.Label): agregat zalezy od obu stron.
USE PrasowkaAiSpill1006;
SET NOCOUNT ON;
IF OBJECT_ID(N'dbo.Tiny') IS NULL
BEGIN
    CREATE TABLE dbo.Tiny (Id int NOT NULL PRIMARY KEY, Label varchar(10) NOT NULL);
    INSERT dbo.Tiny (Id, Label) SELECT value, 'l' + CONVERT(varchar(5), value) FROM GENERATE_SERIES(1, 300);
END

SET STATISTICS XML ON;
SELECT MAX(a.Label + b.Label) AS MaxPair FROM dbo.Tiny AS a, dbo.Tiny AS b;
SET STATISTICS XML OFF;
