-- NO-STATISTICS: baza ma AUTO_CREATE_STATISTICS OFF, kolumna Category nie ma indeksu ani statystyk.
-- Uwaga: prosty SELECT ... WHERE Category = 7 dostaje plan TRIVIAL i NIE niesie ostrzezenia
-- (zmierzone - pierwsza wersja tego skryptu). Dlatego join, ktory wymusza pelna optymalizacje.
USE PrasowkaAiSpill1006;
SET NOCOUNT ON;
IF OBJECT_ID(N'dbo.Plain') IS NULL
BEGIN
    CREATE TABLE dbo.Plain (Id int NOT NULL PRIMARY KEY, Category int NOT NULL);
    INSERT dbo.Plain (Id, Category) SELECT value, value % 50 FROM GENERATE_SERIES(1, 100000);
END

SET STATISTICS XML ON;
SELECT MAX(w.Note) AS MaxNote
FROM dbo.Plain AS p
JOIN dbo.Wide AS w ON w.Id = p.Id
WHERE p.Category = 7;
SET STATISTICS XML OFF;
