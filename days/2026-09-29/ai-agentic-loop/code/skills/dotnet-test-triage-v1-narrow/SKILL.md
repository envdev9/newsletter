---
name: dotnet-test-triage-v1-narrow
description: Diagnozuje czerwony wynik komendy dotnet test. Uzyj, gdy dotnet test zwraca czerwone testy albo build testowy sie nie powiodl.
allowed-tools: Read, Grep, Bash(dotnet test*)
---

# dotnet-test-triage-v1-narrow

Wersja **v1** - opis trzyma sie tylko literalnej komendy. Dziala, gdy ktos pisze
dokladnie "dotnet test failuje". Zobacz [`../dotnet-test-triage-v2-broad/SKILL.md`](../dotnet-test-triage-v2-broad/SKILL.md)
- ta sama procedura, opis przewidujacy inne sformulowania tego samego problemu.

## Procedura

1. Uruchom ponownie: `dotnet test --filter "FullyQualifiedName=<test>"`. Jesli przechodzi
   przy drugim uruchomieniu - podejrzenie flaky (czas, kolejnosc testow, `Random` bez seeda).
2. Jesli pada zawsze na tym samym asercie - to regresja w kodzie produkcyjnym, nie w tescie.
3. Jesli pada juz na etapie `dotnet restore`/`dotnet build` (przed uruchomieniem testu) -
   to nie test jest zepsuty, a build/zaleznosci (np. rozjazd wersji pakietu w lockfile).
4. Sprawdz czy failuje tylko w CI, nie lokalnie - typowa przyczyna: zaleznosc od
   strefy czasowej/locale/kolejnosci wykonania testow, ktora runner CI ustawia inaczej.
