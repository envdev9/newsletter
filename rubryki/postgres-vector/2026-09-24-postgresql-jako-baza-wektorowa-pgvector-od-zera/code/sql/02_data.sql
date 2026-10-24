-- Osiem "artykułów" - krótkich tekstów, każdemu ręcznie przypisany wektor
-- [zwierzęta, technologia, sport, kuchnia]. Wartości dobrane tak, żeby dało
-- się na oko przewidzieć, które teksty są "blisko siebie", zanim uruchomimy
-- zapytanie - to jest test na to, czy baza faktycznie liczy odległości
-- poprawnie, a nie tylko "coś zwraca".
INSERT INTO artykuly (tytul, temat_wektor) VALUES
    ('Koty domowe śpią średnio 16 godzin na dobę',              '[0.90, 0.00, 0.00, 0.00]'),
    ('Psy rasy border collie potrzebują długich spacerów',      '[0.80, 0.00, 0.15, 0.00]'),
    ('Nowy model GPU przyspiesza trenowanie sieci neuronowych', '[0.00, 0.95, 0.05, 0.00]'),
    ('PostgreSQL to relacyjna baza danych z rozszerzeniami',    '[0.00, 0.85, 0.00, 0.00]'),
    ('Reprezentacja wygrała mecz piłki nożnej w finale',        '[0.00, 0.00, 0.90, 0.05]'),
    ('Koszykówka to jeden z najpopularniejszych sportów w USA', '[0.00, 0.00, 0.95, 0.00]'),
    ('Przepis na pierogi z kapustą i grzybami na wigilię',      '[0.00, 0.00, 0.00, 0.95]'),
    ('Kucharz przygotował rybę na obiad w restauracji',         '[0.05, 0.00, 0.00, 0.90]');
