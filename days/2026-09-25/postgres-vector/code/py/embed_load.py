"""Liczy PRAWDZIWE embeddingi (lokalny model ONNX przez fastembed, bez kluczy API)
i ładuje je do Postgresa przez COPY."""
import os
import time

from common import MODEL_NAME, connect, get_model, vec_literal
from corpus import KB_DOCS, bench_corpus

N_DOCS = int(os.environ.get("N_DOCS", "8000"))
N_QUERIES = int(os.environ.get("N_QUERIES", "100"))


def embed(model, texts):
    return [vec_literal(v) for v in model.embed(texts, batch_size=64)]


def copy_rows(cur, table, texts, vecs):
    with cur.copy(f"COPY {table} (id, body, emb) FROM STDIN") as cp:
        for i, (t, v) in enumerate(zip(texts, vecs), start=1):
            cp.write_row((i, t, v))


def main():
    t0 = time.time()
    model = get_model()
    print(f"model: {MODEL_NAME} (załadowany w {time.time() - t0:.1f}s)")

    docs, queries = bench_corpus(N_DOCS, N_QUERIES)
    conn = connect()
    cur = conn.cursor()

    kb_vecs = embed(model, KB_DOCS)
    print(f"wymiar wektora: {len(kb_vecs[0].split(','))}")
    copy_rows(cur, "kb", KB_DOCS, kb_vecs)

    t1 = time.time()
    dv = embed(model, docs)
    dt = time.time() - t1
    print(f"embeddingi korpusu: {len(docs)} zdań w {dt:.1f}s ({len(docs) / dt:.0f} zdań/s, CPU)")
    copy_rows(cur, "bench", docs, dv)
    copy_rows(cur, "bench_q", queries, embed(model, queries))

    cur.execute("SELECT (SELECT count(*) FROM kb), (SELECT count(*) FROM bench), (SELECT count(*) FROM bench_q)")
    print("wiersze kb/bench/bench_q:", cur.fetchone())
    # indeks GIN (tsvector) i HNSW dla kb - po załadowaniu danych
    sql_path = os.path.join(os.path.dirname(__file__), "..", "sql", "02_fts_index.sql")
    cur.execute(open(sql_path, encoding="utf-8").read())
    print("utworzono indeksy kb_tsv_gin (GIN) i kb_emb_hnsw (HNSW) na tabeli kb")
    print("przykład dokumentu:", docs[0])
    print("przykład zapytania:", queries[0])


if __name__ == "__main__":
    main()
