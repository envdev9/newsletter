# Kod do wydania #6 — jak model wybiera skill po `description`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **python3** (testowane na 3.10.4), bez zależności zewnętrznych. Komenda `claude`
**nie została uruchomiona** (każde wywołanie z `claude` odrzucone przez uprawnienia w tym
środowisku, jak w poprzednich wydaniach) — `skill_router_sim.py` jest **heurystyką
symulującą punkt decyzyjny**, nie modelem językowym i nie prawdziwym Claude Code.

## Fragment prasówki, którego dotyczy ten kod

> Skille nie mają wyzwalacza zewnętrznego. Model w trakcie pracy sam czyta listę
> zainstalowanych skilli (nazwa + `description`) i sam ocenia, czy któryś jest relewantny do
> tego, co właśnie robi — bez reguły, bez hooka, który by to wymuszał. To przenosi ciężar
> z mechanizmu (harness) na treść opisu — dobre `description` to inżynieria promptu, nie
> metadane. Identyczna treść skilla z różnym `description` (`dotnet-test-triage-v1-narrow`
> vs `v2-broad`) dowodzi, że o szansie zadziałania decyduje wyłącznie to jedno pole.

## Pliki

| Plik | Rola |
|---|---|
| `skills/ef-core-migration-safety/SKILL.md` | dobry, konkretny opis (operacje + kiedy użyć) |
| `skills/dotnet-test-triage-v1-narrow/SKILL.md` | dobry temat, **zbyt wąski** opis (tylko literalne frazy) |
| `skills/dotnet-test-triage-v2-broad/SKILL.md` | ta sama treść co v1, opis zaprojektowany pod parafrazy zgłoszenia |
| `skills/dotnet-helper/SKILL.md` | zły, ogólny opis (celowo) |
| `skills/general-code-assistant/SKILL.md` | zły, ogólny opis (celowo) |
| `skill_router_sim.py` | heurystyka: tokenizacja + wagi `1/df` + próg → `LOAD`/`skip`; **nie jest modelem** |
| `scenarios.py` | 5 zadań testowych (A-E) używanych przez `run_tests.py` i w artykule |
| `run_tests.py` | odpala wszystkie scenariusze, drukuje tabele, sprawdza 11 asercji |

## Uruchomienie (z katalogu `code/`)

```bash
# wszystko naraz — pełne tabele dla 5 scenariuszy + asercje; ostatnia linia: "WYNIK: 11/11"
python3 run_tests.py

# pojedyncze zadanie na dowolnych skillach z katalogu skills/
python3 skill_router_sim.py "Test dotnet test failuje, dodalem migracje EF Core zmieniajaca typ kolumny."

# ten sam problem, parafraza bez slowa "test"/"dotnet" - zobacz ktory skill (jesli ktorykolwiek) sie zaladuje
python3 skill_router_sim.py "Cos sie psuje w pipeline, mimo ze nikt nic nie zmienial od wczoraj."

# wlasny prog i katalog skilli
python3 skill_router_sim.py "twoje zadanie" --skills-dir skills --threshold 0.12
```

Exit code `run_tests.py`: `0` gdy wszystkie asercje przeszły, `1` inaczej.

## Jak czytać wynik `skill_router_sim.py`

```
skill                             score  decyzja  wspolne slowa
ef-core-migration-safety          0.427     LOAD  core, domeny, dotnet, ef, kolumny, migracje, model
```

`score` = ważony recall słów zadania znalezionych w `description` skilla (waga słowa =
`1 / liczba skilli, w których description to słowo zawiera` — żeby ogólne słowa typu
"dotnet"/"core", obecne w kilku opisach, nie ważyły tyle samo co rzadkie, specyficzne
słowa typu "pipeline"). `LOAD` = `score >= threshold` (domyślnie `0.12`). `wspolne slowa`
to realne przecięcie tokenów zadania i opisu — pozwala zobaczyć **dlaczego** coś się
załadowało albo nie.

## Czego ten kod NIE dowodzi (ważne)

- **Nie jest to test na Claude Code.** To heurystyka bag-of-words bez stemmingu, bez
  synonimów, bez rozumienia znaczenia. Realny model semantyczny prawdopodobnie złapie
  parafrazy, które ta heurystyka gubi (scenariusz E — polska odmiana słów) i odróżni
  sytuacje, które ta heurystyka myli (opis-worek przypadkowo pasujący przez jedno słowo).
- **Nie sprawdzono**, czy Claude Code faktycznie ładuje tylko `name`+`description` na
  starcie sesji, a resztę `SKILL.md` dopiero po wyborze skilla — to jest z pamięci, bez
  dostępu do dokumentacji w tej sesji. `claude --version` odrzucone przez uprawnienia.
- **Nie sprawdzono** zachowania, gdy dwa skille są jednocześnie relewantne (czy model
  ładuje oba, czy wybiera jeden) — poza tym, co pokazuje scenariusz A (dwa różne skille
  dostają `LOAD` naraz w tej symulacji; w prawdziwej sesji nieprzetestowane).

## Format `SKILL.md` użyty w tych przykładach

```markdown
---
name: <musi zgadzac sie z nazwa katalogu>
description: <1-3 zdania: co robi, kiedy uzyc (kilka wariantow zgloszenia), czym sie rozni od podobnych skilli>
allowed-tools: Read, Grep, ...
---

# <nazwa>

<tresc proceduralna>
```

Ten sam format co `changelog-entry` z wydania #2 tej rubryki
(`../../2026-09-25/ai-agentic-loop/code/skills/changelog-entry/SKILL.md`) — konsekwentnie
w całej serii.
