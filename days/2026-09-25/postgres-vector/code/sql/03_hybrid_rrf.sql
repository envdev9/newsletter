-- Hybrid search: Reciprocal Rank Fusion w czystym SQL.
-- Parametry (psycopg): %(qvec)s = wektor zapytania (text '[...]'), %(qtsq)s = tsquery jako tekst.
-- RRF: wynik(dok) = suma po listach 1 / (k + pozycja_w_liście), k = 60 (wartość z pracy
-- Cormacka i in.; tu stała, bo nie ma sensu jej stroić bez zbioru ocen relewancji).
WITH vec AS (
    SELECT id, row_number() OVER (ORDER BY emb <=> %(qvec)s::vector) AS rnk
    FROM kb
    ORDER BY emb <=> %(qvec)s::vector
    LIMIT 20
),
fts AS (
    SELECT id, row_number() OVER (ORDER BY ts_rank_cd(tsv, q) DESC, id) AS rnk
    FROM kb, to_tsquery('simple', %(qtsq)s) AS q
    WHERE tsv @@ q
    ORDER BY ts_rank_cd(tsv, q) DESC, id
    LIMIT 20
)
SELECT COALESCE(v.id, f.id)                         AS id,
       v.rnk                                        AS rnk_vec,
       f.rnk                                        AS rnk_fts,
       round((COALESCE(1.0 / (60 + v.rnk), 0)
            + COALESCE(1.0 / (60 + f.rnk), 0))::numeric, 5) AS rrf,
       left(k.body, 70)                             AS body
FROM vec v
FULL OUTER JOIN fts f ON f.id = v.id
JOIN kb k ON k.id = COALESCE(v.id, f.id)
ORDER BY rrf DESC, id
LIMIT 5;
