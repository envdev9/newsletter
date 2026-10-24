---
name: dotnet-test-triage-v2-broad
description: Diagnozuje czerwone testy .NET niezaleznie od tego jak to zgloszono - "dotnet test failuje", "pipeline/build sie wywalil na testach", "dzialalo wczoraj a dzis nie", "nikt nic nie zmienial a testy czerwone", podejrzenie flaky testu. Rozroznia regresje w kodzie produkcyjnym od testu niedeterministycznego i od problemu ze srodowiskiem/przywroceniem pakietow w CI. Uzyj przy kazdym zgloszeniu psujacego sie pipeline'u albo czerwonych testow, nawet gdy w pytaniu nie pada slowo "test" czy "dotnet".
allowed-tools: Read, Grep, Bash(dotnet test*)
---

# dotnet-test-triage-v2-broad

Ta sama procedura jak w [`../dotnet-test-triage-v1-narrow/SKILL.md`](../dotnet-test-triage-v1-narrow/SKILL.md).
Rozni sie **tylko** opis (`description`) - v2 zawiera na tyle parafraz, zeby zlapac
zgloszenie napisane bez slowa "test"/"dotnet"/"build" (np. "cos sie psuje, mimo ze nikt
nic nie zmienial"). Tresc ponizej identyczna z v1, celowo - ten plik demonstruje, ze
**to opis jest interfejsem wyboru skilla**, nie tresc.

## Procedura

1. Uruchom ponownie: `dotnet test --filter "FullyQualifiedName=<test>"`. Jesli przechodzi
   przy drugim uruchomieniu - podejrzenie flaky (czas, kolejnosc testow, `Random` bez seeda).
2. Jesli pada zawsze na tym samym asercie - to regresja w kodzie produkcyjnym, nie w tescie.
3. Jesli pada juz na etapie `dotnet restore`/`dotnet build` (przed uruchomieniem testu) -
   to nie test jest zepsuty, a build/zaleznosci (np. rozjazd wersji pakietu w lockfile).
4. Sprawdz czy failuje tylko w CI, nie lokalnie - typowa przyczyna: zaleznosc od
   strefy czasowej/locale/kolejnosci wykonania testow, ktora runner CI ustawia inaczej.
