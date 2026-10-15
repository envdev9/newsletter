#!/usr/bin/env python3
"""Niezalezna weryfikacja dowodow spojnosci z work/cases.json (bez kodu C#).

Inny algorytm niz w C#:
  * korzenie liczone przyrostowo ze stosem (laczenie po koncowych bitach), nie rekurencja na k;
  * dowod weryfikowany "odwrocona" rekurencja SUBPROOF (zdejmowanie elementow od konca),
    a nie iteracyjnym algorytmem z RFC 9162.
"""
import hashlib
import json
import sys


def leaf(d: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + d).digest()


def node(l: bytes, r: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + l + r).digest()


def root_incremental(leaf_hashes):
    stack = []  # (hash, rozmiar poddrzewa)
    for h in leaf_hashes:
        cur, size = h, 1
        while stack and stack[-1][1] == size:
            l, _ = stack.pop()
            cur, size = node(l, cur), size * 2
        stack.append((cur, size))
    acc = stack[-1][0]
    for h, _ in reversed(stack[:-1]):
        acc = node(h, acc)
    return acc


def pow2_below(n):
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def rebuild(m, n, b, first_root, proof):
    """Zwraca (stary_korzen, nowy_korzen) dla poddrzewa; konsumuje proof od konca."""
    if m == n:
        if b:
            return first_root, first_root
        h = proof.pop()
        return h, h
    k = pow2_below(n)
    s = proof.pop()
    if m <= k:
        o, nw = rebuild(m, k, b, first_root, proof)
        return o, node(nw, s)
    o, nw = rebuild(m - k, n - k, False, first_root, proof)
    return node(s, o), node(s, nw)


def verify(m, n, root_m, root_n, proof_hex):
    proof = [bytes.fromhex(x) for x in proof_hex]
    if m == n:
        return not proof and root_m == root_n
    try:
        o, nw = rebuild(m, n, True, root_m, proof)
    except IndexError:
        return False
    return not proof and o == root_m and nw == root_n


def main(path):
    doc = json.load(open(path))
    lh = [leaf(e.encode()) for e in doc["entries"]]
    ok = bad = root_mismatch = fork_rejected = 0
    for c in doc["cases"]:
        m, n = c["m"], c["n"]
        rm, rn = bytes.fromhex(c["root_m"]), bytes.fromhex(c["root_n"])
        if c.get("fork"):
            if not verify(m, n, rm, rn, c["proof"]):
                fork_rejected += 1
            else:
                bad += 1
            continue
        if root_incremental(lh[:m]) != rm or root_incremental(lh[:n]) != rn:
            root_mismatch += 1
        if verify(m, n, rm, rn, c["proof"]):
            ok += 1
        else:
            bad += 1
    print(f"przypadkow uczciwych zweryfikowanych: {ok}")
    print(f"korzenie z C# != korzenie z Pythona: {root_mismatch}")
    print(f"rozgalezienie (fork) poprawnie odrzucone: {fork_rejected}")
    print(f"bledy: {bad}")
    return 0 if bad == 0 and root_mismatch == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "work/cases.json"))
