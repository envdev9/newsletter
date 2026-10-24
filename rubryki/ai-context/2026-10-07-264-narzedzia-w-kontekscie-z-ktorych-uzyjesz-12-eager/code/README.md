# Kod do wydania z 7.10 — eager kontra leniwe ładowanie definicji narzędzi (tool search)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Wymagania: **python3** (sprawdzono na 3.10.4),
brak zależności.

## Fragment artykułu, którego dotyczy ten kod

> Odroczenie definicji narzędzi przesuwa koszt, nie usuwa go. Na syntetycznym katalogu 264 narzędzi
> (26 380 tok., bajty/4) w sesji 12 zadań x 5 tur: `eager` 1 582 800 token-tur, `deferred_names`
> (same nazwy + `tool_search`) 283 385 (5,6x), `deferred_blind` 173 285 (9,1x), idealna wyrocznia
> 41 400 (38x). Załadowane definicje zostają w kontekście, więc `k` (liczba wyników) jest pokrętłem
> kosztu. Prosta wyszukiwarka BM25 ma jednak recall tylko 10/18 na parafrazach (11/18 przy k=10) -
> oszczędność trzeba oceniać razem z tym, czy narzędzie da się znaleźć.
>
> **Dane syntetyczne, żaden model ani API nie były uruchamiane.** Reguły Claude Code i wpływ na
> prompt cache - niezweryfikowane (hipoteza).

## Pliki

- [`ctxlazy.py`](ctxlazy.py) — generator katalogu, szacunek tokenów, wyszukiwarka BM25, symulacja
  strategii (`eager`, `deferred_names`, `deferred_blind`, `oracle`), polecenia `catalog`, `run`,
  `sweep`, `breakeven`, `recall`.
- [`test_ctxlazy.py`](test_ctxlazy.py) — 15 asercji.

## Jak odpalić

Flaga `-B` nie zostawia `__pycache__/`. Nic nie jest zapisywane na dysk.

```bash
cd code/
python3 -B ctxlazy.py catalog
python3 -B ctxlazy.py run --k 5
python3 -B ctxlazy.py sweep
python3 -B ctxlazy.py breakeven
python3 -B ctxlazy.py recall
python3 -B test_ctxlazy.py
```

## Prawdziwy, uruchomiony output

`run` (k=5):

```
| strategia | stale tok/ture | koniec sesji tok/ture | token-tury | vs eager | zadan znalezionych | ponowien |
|---|---:|---:|---:|---:|---:|---:|
| eager | 26380 | 26380 | 1582800 | 1.0x | 12/12 | 0 |
| deferred_names | 1926 | 7723 | 283385 | 5.6x | 12/12 | 2 |
| deferred_blind | 91 | 5888 | 173285 | 9.1x | 12/12 | 2 |
| oracle | 91 | 1145 | 41400 | 38.2x | 12/12 | 0 |
```

`recall`:

```
| zapytanie | oczekiwane | pozycja |
| close the bug report | jira__transition_ticket | brak |
| silence the pager | monitoring__acknowledge_alert | 9 |
| make the app bigger, more instances | kubernetes__scale_deployment | 1 |
| why is this query slow | postgres__explain_query | 47 |
| tell the team in chat | slack__post_message | brak |
| when can we all meet | calendar__find_free_slot | brak |
| save this to disk | files__write_text | 1 |
| ship the change into main | github__merge_pull_request | brak |
| show me the last errors from the container | kubernetes__pod_logs | 1 |
| run the failed ci again | github__rerun_workflow | 1 |
| how many requests per second | monitoring__query_metric | brak |
| give this to Anna | jira__assign_ticket | 43 |
| create comment | jira__create_comment | 1 |
| list comments | jira__list_comment | 1 |
| delete message | slack__delete_message | 1 |
| get event | calendar__get_event | 1 |
| search issue | github__search_issue | 1 |
| list alerts | monitoring__list_alert | 1 |
| k | recall@k |
| 1 | 10/18 |
| 3 | 10/18 |
| 5 | 10/18 |
| 10 | 11/18 |
```

Test: `OK: 0 niepowodzen` (15 linii `OK`).

## Uczciwe ograniczenia

- Katalog z szablonów: opisy krótsze i bardziej jednorodne niż w realnych serwerach MCP.
- Zadania `run` w większości literalne; 2 zapytania ponawiane podałem ręcznie, więc `12/12` jest zawyżone.
- W `recall` remisy BM25 rozstrzyga kolejność alfabetyczna - trafienia "niejednoznacznych" zapytań
  na 1. miejscu częściowo wynikają z tego.
- Założenie: załadowane definicje zostają do końca sesji. Wpływ na prompt cache i reguły Claude Code
  nie były weryfikowane.
