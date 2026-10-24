-- 03-key-lookup.sql
-- Ten sam SELECT, dwa różne parametry, wąski indeks bez INCLUDE.
-- Zapytanie chce OrderDate, Amount, Status - których w indeksie nie ma,
-- więc po każdym trafionym wierszu potrzebny jest Key Lookup do tabeli.
USE PrasowkaStats;
GO

SET STATISTICS IO ON;
SET STATISTICS PROFILE ON;
GO

-- Uwaga: wyniki 200 000 wierszy przypisujemy do zmiennych (SELECT @x = ...),
-- żeby nie zalewać konsoli. Plan i odczyty stron są takie same jak przy
-- zwykłym SELECT-cie, bo wszystkie wiersze i tak muszą zostać przeczytane.
DECLARE @d DATE, @a DECIMAL(10,2), @s VARCHAR(20);

-- (a) klient rzadki: garstka wierszy -> Index Seek + Key Lookup jest tanie.
SELECT OrderDate, Amount, Status FROM dbo.Orders WHERE CustomerId = 4242;

-- (b) klient hurtownik: 200 000 wierszy. Optymalizator (znając histogram)
-- wie, że 200 000 Key Lookupów byłoby koszmarem -> wybiera skan tabeli.
SELECT @d = OrderDate, @a = Amount, @s = Status FROM dbo.Orders WHERE CustomerId = 1;

-- (c) Wymuszamy plan (a) dla hurtownika, żeby zobaczyć, ile kosztowałby
-- "błędny" plan: Index Seek + 200 000 Key Lookupów.
SELECT @d = OrderDate, @a = Amount, @s = Status
FROM dbo.Orders WITH (INDEX (IX_Orders_CustomerId))
WHERE CustomerId = 1;
GO

SET STATISTICS PROFILE OFF;
SET STATISTICS IO OFF;
GO
