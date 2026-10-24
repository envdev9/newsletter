# Kod do wydania z 27.09 — audyt stałego kosztu kontekstu (CLAUDE.md i MCP)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Wymagania: **python3** (sprawdzono na 3.10.4),
brak zależności.

## Fragment artykułu, którego dotyczy ten kod

> Wyniki narzędzi płacisz, gdy ich użyjesz. Pamięć i definicje narzędzi płacisz, gdy tylko
> otworzysz sesję - i w każdej następnej turze. Import `@plik` w `CLAUDE.md` to wklejenie
> treści, nie link: w fixture'ze 533 z 1242 tokenów stałej pamięci to dwa zaimportowane pliki.
> Po przycięciu (drzewo, wklejony kod, ogólniki, duplikaty; dokumenty jako wskaźniki bez `@`)
> stała pamięć spadła z 1242 do 304 tok. (4,1x). Definicje trzech **syntetycznych** serwerów MCP
> to 2076 tok., z czego gadatliwy `tracker` 86% (223 tok./narz. vs 59 w zwięzłym `db`).
>
> **Dane nie pochodzą z prawdziwej sesji** (odczyt `~/.claude/projects/` odrzucony przez
> uprawnienia, nie obchodziłem). Fixture i definicje MCP są wymyślone. Model ładowania pamięci
> (hierarchia, importy, limit 5 skoków) to moje odtworzenie z pamięci dokumentacji -
> niezweryfikowane na żywym kliencie.

## Pliki

- [`ctxaudit.py`](ctxaudit.py) — narzędzie: `memory` (symulacja ładowania CLAUDE.md: hierarchia,
  importy, leniwe podkatalogi, sekcje, kandydaci do przycięcia) i `mcp` (koszt definicji
  narzędzi, what-if wyłączenia serwera, zastrzeżenia). Drukuje tylko nazwy plików i liczby.
  Tokeny = bajty/4 (heurystyka).
- [`fixture/`](fixture/) — fikcyjny projekt: `project/CLAUDE.md` (przed), `project/CLAUDE.after.md`
  (po), `docs/`, pamięci podkatalogów, `home/CLAUDE.md` (udaje plik użytkownika).
  Uwaga: `CLAUDE.after.md` wskazuje `src/Orders.Api/Endpoints/CreateOrderEndpoint.cs`, którego w
  fixture'ze nie ma (to tylko przykład wskaźnika; audyt nie sprawdza istnienia zwykłych ścieżek).
- [`gen_mcp_fixture.py`](gen_mcp_fixture.py) — generuje [`mcp_tools.json`](mcp_tools.json)
  (syntetyczne definicje w kształcie `tools/list`).
- [`test_ctxaudit.py`](test_ctxaudit.py) — 13 asercji na tymczasowych drzewach.

## Jak odpalić od zera

Flaga `-B` nie zostawia `__pycache__/`.

```bash
cd code/
python3 -B gen_mcp_fixture.py mcp_tools.json
python3 -B ctxaudit.py memory --root fixture/project --cwd fixture/project/src/Orders.Api --home fixture/home
python3 -B ctxaudit.py memory --root fixture/project --cwd fixture/project/src/Orders.Api --home fixture/home --root-file CLAUDE.after.md
python3 -B ctxaudit.py mcp mcp_tools.json
python3 -B test_ctxaudit.py
```

Na własnym projekcie: `--root` = korzeń repo, `--cwd` = katalog, w którym uruchamiasz sesję,
`--home` = katalog z Twoim `CLAUDE.md` użytkownika (pomiń, jeśli nie chcesz go czytać).
Własne MCP: JSON `{"servers": {nazwa: {"tools": [{name, description, inputSchema}]}}}`.
Opcje: `--turns`, `--window`, `--desc-max`, `--json`.

## Prawdziwy, uruchomiony output

Pełny output obu wariantów pamięci i audytu MCP jest w artykule (sekcje 2 i 4); test:

```
OK: 13/13 asercji przeszło
```

## Uczciwe ograniczenia

- Fixture i definicje MCP są **syntetyczne**; liczby ilustrują mechanizm, nie mierzą realnych projektów.
- Reguły ładowania pamięci (w tym `MAX_HOPS = 5`, pomijanie `@` w blokach kodu) to moje założenia.
- Heurystyki lintu (regex) mogą dawać fałszywe alarmy i się nakładać (dlatego "RAZEM do zbadania").
- Nie sprawdzono, czy agent sam sięga po plik wskazany zwykłą ścieżką, ani leniwego ładowania definicji MCP.
- Nie uruchomiono na prawdziwym transkrypcie ani w żywej sesji Claude Code.
