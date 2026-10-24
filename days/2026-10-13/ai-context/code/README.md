# Kod do wydania z 13.10 — wyszukiwarka narzędzi: synonimy, aliasy, n-gramy, prior sesji + uczciwa ewaluacja

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Wymagania: **python3** (sprawdzono na 3.10.4),
brak zależności. Nic nie jest zapisywane na dysk. Katalog narzędzi jest ten sam SYNTETYCZNY co w
[#14](../../../2026-10-07/ai-context/code/ctxlazy.py), skopiowany do `ctxsearch.py` (kod jest samodzielny).

## Fragment artykułu, którego dotyczy ten kod

> BM25 trafia 34/40 zapytań, gdy dzielą słowo z narzędziem, i 4/23, gdy nie dzielą. Słownik synonimów po
> stronie zapytania podnosi recall@5 na teście z 17/30 do 26/30; aliasy w opisie narzędzia kosztują
> +3 370 tok. (+12,8%) i wypadają gorzej; fuzja RRF z n-gramami znaków nie pomaga. Na zbiorze, na którym
> budowano słownik, wynik to 18/18 @5 (21/30 @1 na teście vs 18/18 na dev). Prior sesji (podbicie serwerów
> już użytych) naprawia niejednoznaczność (8/12 → 12/12), ale boost 3,0 zjada jawnie nazwany serwer.
>
> **Dane syntetyczne, zapytania i słowniki pisał jeden autor; żaden model ani CLI nie były uruchamiane.**
> Zachowanie modelu formułującego zapytania do tool search — niezweryfikowane.

## Pliki

- [`ctxsearch.py`](ctxsearch.py) — katalog, retrievery (`bm25`, `ngram`, `+syn`, `+alias`, RRF, `+stop`),
  zestawy `DEV`/`TEST`/`FRESH`/`AMBIG`, polecenia ewaluacyjne.
- [`test_ctxsearch.py`](test_ctxsearch.py) — 40 asercji (katalog, stemming, RRF, prior, wartości
  regresyjne, rozłączność zestawów).

## Jak odpalić

Flaga `-B` nie zostawia `__pycache__/`. Polecenia z katalogu `code/`:

```bash
python3 -B ctxsearch.py eval
python3 -B ctxsearch.py failures
python3 -B ctxsearch.py overlap
python3 -B ctxsearch.py cost
python3 -B ctxsearch.py prior
python3 -B ctxsearch.py peek
python3 -B ctxsearch.py query "silence the pager" --k 3
python3 -B ctxsearch.py query "create comment" --session github --k 3
python3 -B test_ctxsearch.py
```

## Prawdziwy, uruchomiony output

`eval`:

```
katalog: 264 narzedzi; dev=18, test=30, fresh=15 zapytan
| retriever | dev: @1 / @3 / @5 / MRR | test: @1 / @3 / @5 / MRR | fresh: @1 / @3 / @5 / MRR |
|---|---|---|---|
| bm25 | 10/18 / 10/18 / 10/18 / 0.56 | 8/30 / 14/30 / 17/30 / 0.41 | 5/15 / 8/15 / 11/15 / 0.49 |
| ngram | 7/18 / 9/18 / 9/18 / 0.45 | 10/30 / 17/30 / 19/30 / 0.45 | 3/15 / 4/15 / 4/15 / 0.28 |
| bm25+syn | 18/18 / 18/18 / 18/18 / 1.00 | 21/30 / 24/30 / 26/30 / 0.77 | 8/15 / 11/15 / 13/15 / 0.67 |
| bm25+alias | 15/18 / 17/18 / 17/18 / 0.88 | 20/30 / 21/30 / 24/30 / 0.72 | 8/15 / 12/15 / 12/15 / 0.65 |
| rrf(bm25,ngram) | 8/18 / 9/18 / 9/18 / 0.48 | 8/30 / 16/30 / 17/30 / 0.41 | 2/15 / 7/15 / 8/15 / 0.31 |
| rrf(syn,alias,ngram) | 17/18 / 18/18 / 18/18 / 0.97 | 21/30 / 25/30 / 27/30 / 0.77 | 5/15 / 11/15 / 11/15 / 0.51 |
| bm25+stop | 9/18 / 9/18 / 9/18 / 0.51 | 10/30 / 14/30 / 17/30 / 0.44 | 6/15 / 8/15 / 9/15 / 0.47 |
| rrf(syn,alias,ngram)+stop | 17/18 / 18/18 / 18/18 / 0.97 | 22/30 / 24/30 / 27/30 / 0.79 | 7/15 / 11/15 / 11/15 / 0.60 |
```

`overlap` (recall@5, 63 zapytania): `bm25` 34/40 ze wspólnym słowem vs 4/23 bez; `bm25+syn` 38/40 vs 19/23;
`bm25+alias` 36/40 vs 17/23; `ngram` 29/40 vs 3/23; `rrf(bm25,ngram)` 34/40 vs 0/23.

`cost`: `definicje pelne: 26380 tok.; z aliasami: 29750 tok. (+3370, +12.8%)`; `bm25+syn` recall>=90% przy k=5
(~500 tok.), `bm25` nie osiąga 90% przy żadnym k <= 264.

`peek` (4 dopisane hasła po obejrzeniu błędów testu), `bm25+syn` @5: test 26/30 → 28/30, fresh 13/15 → 14/15;
`rrf(syn,alias,ngram)`: test 27/30 → 28/30, fresh 11/15 → 11/15.

`prior`: boost 0,0 → 8/12 @1; 0,1 / 0,25 / 0,5 / 1,0 → 12/12; 3,0 → 11/12 (`postgres run sql`
przegrywa z `github__search_workflow_run`). Bez priora `jira__*_comment` wygrywa także w sesji `github`.

Test: `OK: 40 asercji, 0 niepowodzen`.

## Uczciwe ograniczenia

- Brak prawdziwych embeddingów (stdlib): „semantyka” to ręczny słownik (`THESAURUS`) i ręczne aliasy.
- Zapytania `TEST`/`FRESH` pisał ten sam autor co słownik, przed pierwszym uruchomieniem, ale to nie jest
  niezależny benchmark. Słownik dla `DEV` budowano znając te zapytania — jego wynik jest zawyżony z założenia.
- `bm25+stop` i `PEEK_EXTRA` dodano po obejrzeniu błędów (post-hoc); `fresh` ma inny skład niż `test`
  (więcej zapytań bez wspólnego słowa), więc różnica test/fresh nie jest dowodem przeuczenia.
- Zestaw niejednoznaczny (`AMBIG`, 12 zapytań) to głównie jedna rodzina (`comment`); stałej boost nie
  należy z niego uogólniać. Przyczyna przewagi `jira` bez priora (prawdopodobnie normalizacja długości) nie
  była badana.
- Nie sprawdzano, jak realny model formułuje zapytania do tool search ani dokumentacji `claude`.
