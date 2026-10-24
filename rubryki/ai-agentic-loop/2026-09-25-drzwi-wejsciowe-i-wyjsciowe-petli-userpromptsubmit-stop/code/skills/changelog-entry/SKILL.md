---
name: changelog-entry
description: Generuje wpis do CHANGELOG.md (format Keep a Changelog) z listy commitow w konwencji Conventional Commits. Uzyj, gdy ktos prosi o changelog, release notes, notatki do wydania albo pyta "co weszlo od ostatniego taga".
allowed-tools: Read, Edit, Bash(git log *), Bash(git describe *), Bash(python3 *group_commits.py*)
---

# changelog-entry

Zamien historie gita na wpis do changeloga. **Grupowanie robi skrypt** (deterministyczne),
Ty robisz redakcje (jezyk, scalanie duplikatow, ocena co jest breaking).

## Krok 1 - zbierz commity

```bash
git describe --tags --abbrev=0            # ostatni tag; jesli brak taga - uzyj calej historii
git log <tag>..HEAD --pretty=format:%s    # same tematy commitow
```

## Krok 2 - pogrupuj skryptem

Przekaz tematy na stdin:

```bash
git log <tag>..HEAD --pretty=format:%s | python3 .claude/skills/changelog-entry/group_commits.py --version 1.4.0 --date 2026-09-25
```

Skrypt wypisuje Markdown z sekcjami Added / Fixed / Changed / Other; commity z `!` po
typie lub z `BREAKING CHANGE` trafiaja tez do sekcji **Breaking**. Exit 3 = brak commitow.

## Krok 3 - redakcja (Twoja robota)

- Polacz commity opisujace ten sam efekt dla uzytkownika w jedna linie.
- Pisz z perspektywy uzytkownika ("Dodano filtr po statusie"), nie implementatora.
- Sekcja **Other** to commity bez konwencji - przejrzyj je recznie, nie zgaduj typu.
- Wstaw wynik na gore `CHANGELOG.md`, pod naglowek `# Changelog`. Nie ruszaj starszych wpisow.
