# Kod do wydania #13 — równoległe agenty na `git worktree`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **python3** (testowane na 3.10.4), **git** (testowane na 2.34.1; `git init -b`
wymaga >= 2.28), bez zależności zewnętrznych. Skrypt tworzy tymczasowe repo w `/tmp`
(`prasowka-wt-*`) i **sam je usuwa** na końcu (ostatnia asercja to sprawdza).

**Rolę agentów grają funkcje Pythona** (edytują pliki i commitują) — nie model, nie Claude
Code. Realny jest cały git. Komenda `claude` nie była uruchamiana.

## Fragment prasówki, którego dotyczy ten kod

> Izolacja kontekstu subagenta to nie izolacja plików. Dwóch agentów w jednym katalogu
> to cichy *lost update*. `git worktree` daje każdemu agentowi własny katalog roboczy,
> `HEAD` i indeks przy wspólnej bazie obiektów; ten sam branch nie może być wystawiony
> dwa razy. Konflikt nie znika — przesuwa się na merge, gdzie jest jawny i odwracalny.
> Sprzątanie: git odmawia usunięcia brudnego worktree i niezmergowanego brancha bez `--force`/`-D`.

## Pliki

| Plik | Rola |
|---|---|
| `worktree_fanout.py` | cały scenariusz: lost update, 4 worktree równolegle, merge, konflikt, rebase, sprzątanie; 25 asercji |

## Uruchomienie

```bash
python3 worktree_fanout.py
```

Exit code `0` gdy wszystkie asercje przeszły, `1` inaczej. Hashe commitów w wyjściu różnią
się między uruchomieniami; czasy (0,44 s / 1,75 s) zależą od maszyny, asercja sprawdza
tylko stosunek < 60%.

## Realny output (skrócony tylko o powtórzenia; ścieżki tymczasowe zastąpione `<TMP>`)

```
== 2. worktree: 4 agentow, osobne katalogi i branche ==
<TMP>/repo        9e2e897 [main]
<TMP>/wt-agent-a  9e2e897 [agent-a]
...
proba drugiego checkoutu agent-a -> kod 128: Preparing worktree (checking out 'agent-a')
fatal: 'agent-a' is already checked out at '<TMP>/wt-agent-a'
czas sciany 0.44s, suma pracy agentow 1.75s
== 3. sprzatanie ...
remove na brudnym worktree -> kod 128: fatal: '<TMP>/wt-agent-b' contains modified or untracked files, use --force to delete it
branch -d agent-b (niezmergowany) -> kod 1: error: The branch 'agent-b' is not fully merged.
== 4. merge ...
merge agent-c -> kod 1
CONFLICT (content): Merge conflict in CHANGELOG.md
...
WYNIK: 25/25
```

## Czego ten kod NIE dowodzi

- Zachowania żywej sesji `claude`, `isolation: "worktree"` narzędzia `Agent` (znane tylko
  z opisu narzędzia), `permissionMode`, hooków w trybie headless.
- Że prawdziwy agent wybierze rozłączne pliki lub sam rozwiąże konflikt.
- `dotnet build/test` w worktree (fixture to dwa pliki `.cs` bez projektu), plików spoza gita,
  innych wersji gita, Windows.
