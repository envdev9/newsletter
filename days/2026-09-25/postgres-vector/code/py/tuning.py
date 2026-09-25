"""Strojenie IVFFlat/HNSW: recall@10 i czas zapytania względem DOKŁADNEGO wyszukiwania.
Prawda (ground truth) = ORDER BY ... LIMIT 10 na tabeli bez indeksów (Seq Scan)."""
import statistics
import time

from common import connect

K = 10
Q_SQL = f"SELECT id FROM bench ORDER BY emb <=> %s::vector LIMIT {K}"

IVF_CONFIGS = [20, 100]                      # lists
IVF_PROBES = [1, 5, 20]                      # probes (dla lists=20 dodajemy też probes=lists)
HNSW_CONFIGS = [(8, 32), (16, 64), (32, 128)]  # (m, ef_construction)
HNSW_EF_SEARCH = [10, 40, 100, 200]


def timed_run(cur, queries):
    """Zwraca (lista zbiorów id, lista czasów w ms). Jedno rozgrzewkowe przejście + jedno mierzone."""
    for q in queries:
        cur.execute(Q_SQL, (q,))
        cur.fetchall()
    results, times = [], []
    for q in queries:
        t = time.perf_counter()
        cur.execute(Q_SQL, (q,))
        rows = cur.fetchall()
        times.append((time.perf_counter() - t) * 1000)
        results.append({r[0] for r in rows})
    return results, times


def recall(results, truth):
    return sum(len(r & t) / K for r, t in zip(results, truth)) / len(truth)


def p95(xs):
    return sorted(xs)[int(len(xs) * 0.95) - 1]


def uses_index(cur, q, name):
    cur.execute("EXPLAIN " + Q_SQL, (q,))
    return any(name in row[0] for row in cur.fetchall())


def row(label, rec, times, exact_mean):
    m = statistics.mean(times)
    print(f"  {label:<26} recall@{K}={rec * 100:5.1f}%   mean={m:7.2f} ms   p95={p95(times):7.2f} ms   x{exact_mean / m:5.1f} vs exact")


def main():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SET max_parallel_workers_per_gather = 0")   # uczciwie: bez równoległości, jeden rdzeń
    cur.execute("SET maintenance_work_mem = '256MB'")
    cur.execute("SELECT emb::text FROM bench_q ORDER BY id")
    queries = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT count(*) FROM bench")
    n = cur.fetchone()[0]
    cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    print(f"pgvector {cur.fetchone()[0]}, korpus: {n} wektorów x 384 wymiary, {len(queries)} zapytań, k={K}, operator <=>")

    print("\n[EXACT] Seq Scan bez indeksu (ground truth):")
    truth, exact_times = timed_run(cur, queries)
    exact_mean = statistics.mean(exact_times)
    row("Seq Scan", 1.0, exact_times, exact_mean)

    print("\n[IVFFlat]")
    for lists in IVF_CONFIGS:
        t = time.perf_counter()
        cur.execute(f"CREATE INDEX bench_ivf ON bench USING ivfflat (emb vector_cosine_ops) WITH (lists = {lists})")
        build = time.perf_counter() - t
        cur.execute("SELECT pg_size_pretty(pg_relation_size('bench_ivf'))")
        print(f" lists={lists}: build {build:.1f}s, rozmiar indeksu {cur.fetchone()[0]}")
        probes_list = IVF_PROBES + ([lists] if lists not in IVF_PROBES else [])
        for probes in sorted(set(p for p in probes_list if p <= lists)):
            cur.execute(f"SET ivfflat.probes = {probes}")
            res, times = timed_run(cur, queries)
            ok = "" if uses_index(cur, queries[0], "bench_ivf") else "  (UWAGA: planner nie użył indeksu!)"
            row(f"lists={lists} probes={probes}", recall(res, truth), times, exact_mean)
            if ok:
                print(ok)
        cur.execute("DROP INDEX bench_ivf")
        cur.execute("RESET ivfflat.probes")

    print("\n[HNSW]")
    for m, efc in HNSW_CONFIGS:
        t = time.perf_counter()
        cur.execute(f"CREATE INDEX bench_hnsw ON bench USING hnsw (emb vector_cosine_ops) WITH (m = {m}, ef_construction = {efc})")
        build = time.perf_counter() - t
        cur.execute("SELECT pg_size_pretty(pg_relation_size('bench_hnsw'))")
        print(f" m={m} ef_construction={efc}: build {build:.1f}s, rozmiar indeksu {cur.fetchone()[0]}")
        for ef in HNSW_EF_SEARCH:
            cur.execute(f"SET hnsw.ef_search = {ef}")
            res, times = timed_run(cur, queries)
            row(f"m={m} efc={efc} ef_search={ef}", recall(res, truth), times, exact_mean)
            if not uses_index(cur, queries[0], "bench_hnsw"):
                print("  (UWAGA: planner nie użył indeksu!)")
        cur.execute("DROP INDEX bench_hnsw")
        cur.execute("RESET hnsw.ef_search")


if __name__ == "__main__":
    main()
