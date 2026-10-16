# Wydanie #23 — Claude Code: ile naprawdę kosztuje indeks `gin_trgm_ops` i jak ma się `ILIKE`/`citext`

Dwa skrypty SQL (czyste `psql`, bez .NET) domykające dwa długi z #16: koszt zapisu/rozmiar
indeksu GIN oraz `ILIKE`/`lower()`/`citext` na PostgreSQL.

## Uruchomienie od zera

Wymagany Docker i obraz `postgres:16`. Hasło jest przykładowe, kontener nie publikuje portów.

```bash
docker run -d --name prasowka-ai-pg-1016 -e POSTGRES_PASSWORD=demo-only-1016 postgres:16
docker cp bench.sql prasowka-ai-pg-1016:/tmp/bench.sql
docker cp bench2.sql prasowka-ai-pg-1016:/tmp/bench2.sql
docker exec prasowka-ai-pg-1016 psql -U postgres -v ON_ERROR_STOP=1 -f /tmp/bench.sql
docker exec prasowka-ai-pg-1016 psql -U postgres -v ON_ERROR_STOP=1 -f /tmp/bench2.sql
docker rm -f prasowka-ai-pg-1016
```

- `bench.sql` — tworzy bazę `prasowka_ai_1016`, 200 000 adresów e-mail, cztery tabele
  (bez indeksu / btree / `varchar_pattern_ops` / GIN `gin_trgm_ops`), mierzy INSERT, UPDATE, rozmiar.
- `bench2.sql` — `CREATE INDEX` vs insert, `fastupdate` on/off, `ILIKE`, `lower()`, `citext`.
- Czasy zależą od maszyny; stabilne są rozmiary i bufory, nie milisekundy.

## Zmierzone (PostgreSQL 16, pojedyncze uruchomienie)

| Operacja | bez indeksu | btree | `varchar_pattern_ops` | GIN `gin_trgm_ops` |
|---|---|---|---|---|
| INSERT 200 000 do pustej tabeli | 457 ms | 2739 ms | 1541 ms | 8661 ms |
| INSERT 20 000 do zaindeksowanej | 34 ms | 257 ms | – | 900 ms |
| UPDATE kolumny indeksowanej, 20 000 | 89 ms | 416 ms | – | 1156 ms |
| Rozmiar indeksu po insercie przyrostowym | – | 19 MB | 19 MB | 19 MB (21 MB po dodaniu 20 tys.) |
| Rozmiar po `CREATE INDEX` na gotowej tabeli | – | 12 MB | – | 15 MB (build 3,99 s vs btree 1,24 s) |

`fastupdate=on` (domyślnie): 20 000 wierszy 933 ms, 3035 krotek w pending list (276 stron).
`fastupdate=off`: 10 481 ms (ta sama liczba wierszy, ale większa tabela — patrz uwagi w artykule).

## Fragment artykułu

Zob. `../ARTICLE.md` — sekcje 2 (koszt zapisu i rozmiar), 3 (`ILIKE`, `lower()`, `citext`) i 4 (co zmienić w skillu).
