"""Hybrid search: wektor vs pełnotekstowe vs RRF - na tych samych zapytaniach."""
import os
import re

from common import connect, get_model, vec_literal

SQL_DIR = os.path.join(os.path.dirname(__file__), "..", "sql")

QUERIES = [
    "błąd 40001 przy transakcji",                                    # kod błędu: to lubi FTS
    "jak szybko szukać najbliższych sąsiadów w milionach rekordów",   # parafraza: to lubi wektor
    "baza ignoruje indeks",                                           # parafraza bez wspólnych słów
    "halfvec",                                                        # rzadki token
    "łączenie rankingów z wyszukiwania pełnotekstowego i wektorowego",
]


def to_or_tsquery(text: str) -> str:
    # websearch_to_tsquery łączy słowa przez AND - dla długiego zdania nic nie zwróci.
    # Dla rankingu chcemy OR: dokument dostaje punkty za każde trafione słowo.
    words = re.findall(r"\w+", text.lower())
    return " | ".join(words)


def top(cur, sql, params):
    cur.execute(sql, params)
    return cur.fetchall()


def main():
    model = get_model()
    conn = connect()
    cur = conn.cursor()
    rrf_sql = open(os.path.join(SQL_DIR, "03_hybrid_rrf.sql"), encoding="utf-8").read()

    for q in QUERIES:
        qvec = vec_literal(next(iter(model.embed([q]))))
        qtsq = to_or_tsquery(q)
        print("=" * 100)
        print(f"ZAPYTANIE: {q!r}   (tsquery: {qtsq})")

        vec = top(cur, "SELECT id, round((emb <=> %(v)s::vector)::numeric, 3), left(body, 70) "
                       "FROM kb ORDER BY emb <=> %(v)s::vector LIMIT 3", {"v": qvec})
        print("-- tylko wektor (kosinus):")
        for r in vec:
            print(f"   id={r[0]:>2} dist={r[1]}  {r[2]}")

        fts = top(cur, "SELECT id, round(ts_rank_cd(tsv, q)::numeric, 3), left(body, 70) "
                       "FROM kb, to_tsquery('simple', %(t)s) q WHERE tsv @@ q "
                       "ORDER BY ts_rank_cd(tsv, q) DESC, id LIMIT 3", {"t": qtsq})
        print("-- tylko pełnotekstowe (ts_rank_cd):")
        if not fts:
            print("   (brak trafień)")
        for r in fts:
            print(f"   id={r[0]:>2} rank={r[1]}  {r[2]}")

        rrf = top(cur, rrf_sql, {"qvec": qvec, "qtsq": qtsq})
        print("-- RRF (wektor + FTS):")
        for r in rrf[:3]:
            print(f"   id={r[0]:>2} vec#{r[1]} fts#{r[2]} rrf={r[3]}  {r[4]}")

    print("=" * 100)
    print("EXPLAIN części FTS (enable_seqscan=off, bo na 24 wierszach planner woli Seq Scan):")
    cur.execute("SET enable_seqscan = off")
    cur.execute("EXPLAIN SELECT id FROM kb WHERE tsv @@ to_tsquery('simple', 'halfvec')")
    for (line,) in cur.fetchall():
        print("  ", line)


if __name__ == "__main__":
    main()
