-- Demo: vector(4) to typ ZE SZTYWNĄ długością. Próba wstawienia wektora
-- o innej liczbie wymiarów kończy się błędem już na poziomie typu, nie
-- dopiero przy porównaniu - to samo zabezpieczenie co np. char(N) w SQL.
INSERT INTO artykuly (tytul, temat_wektor)
VALUES ('Zły wektor - 3 wymiary zamiast 4', '[1,2,3]');
