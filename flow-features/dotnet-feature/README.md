# dotnet-feature

Gotowa do wklejenia wersja workflow opisanego w [backend-feature3](../backend-feature3/README.md).
Nazwa zmieniona na `dotnet-feature` (wywołanie `/dotnet-feature <opis>`). Decyzje i uzasadnienia są w README backend-feature3,
a przebieg rozmowy, z której wyszła ta wersja, w [conversation-2026-11-22.md](conversation-2026-11-22.md).

## Struktura

```
dotnet-feature/
├── global/                         → kopiujesz do ~/.claude/ (raz na maszynę)
│   ├── rules/
│   │   ├── dotnet.md               ogólne zasady C#/.NET, niejasne wymagania, weryfikacja, checklista self-review
│   │   ├── dotnet-data.md          Dapper, PostgreSQL, SqlDeployer, testy integracyjne (m.in. UPDATE zamiast delete+insert)
│   │   └── dotnet-cloud.md         API, Kubernetes, Aspire, TeamCity
│   ├── agents/
│   │   └── dotnet-developer.md     worker: model sonnet, czyta pliki zasad zamiast mieć ich kopię
│   └── skills/
│       └── dotnet-feature/
│           ├── SKILL.md            workflow: wymagania → design z krokami → implementacja → review → commit
│           ├── review-prompt.md    jeden reviewer: code + podstawowe security + ukryte założenia
│           └── security-prompt.md  osobny security review dla zmian wrażliwych (kopia z feature-backend)
└── repo/                           → kopiujesz do katalogu głównego projektu .NET (szablony do uzupełnienia)
    ├── CLAUDE.md                   co to za projekt: stack, struktura, komendy, pliki wzorcowe, import zasad
    └── .claude/rules/
        ├── architecture.md         warstwy i odpowiedzialności (ładuje się zawsze)
        ├── controllers.md          jak pisać controllery/endpointy (ładuje się przy plikach z paths:)
        ├── services.md             jak pisać serwisy
        ├── data-access.md          repozytoria, SQL, migracje w tym repo
        └── testing.md              testy w tym repo
```

## Kto co ładuje

| Plik | Kiedy trafia do kontekstu |
|---|---|
| `~/.claude/rules/*.md` | Claude Code wczytuje automatycznie reguły użytkownika. Frontmatter `paths:` ogranicza je do pracy na pasujących plikach (`*.cs`, `*.sql`…), więc sesje nie-.NET ich nie płacą. Skill i agent dodatkowo każą je przeczytać wprost, na wypadek gdyby automat nie zadziałał. |
| `<repo>/CLAUDE.md` | zawsze w sesji w tym repo; importuje `~/.claude/rules/dotnet.md` |
| `<repo>/.claude/rules/*.md` | bez `paths:` zawsze, z `paths:` przy pracy na pasujących plikach |
| skill `dotnet-feature` | `/dotnet-feature <opis>` albo automatycznie, gdy model uzna, że zadanie pasuje |
| agent `dotnet-developer` | uruchamiany przez skill w ścieżce M/L |

Priorytet zasad: polecenie / zatwierdzony design → zasady repo → zasady globalne.

## Instalacja

### 1. Globalnie (raz)

```bash
git clone https://gitea.loriapps.net/tech02/flow-feautres.git
cd flow-feautres/dotnet-feature

# kopia zapasowa agenta, który zostanie nadpisany
cp ~/.claude/agents/dotnet-developer.md ~/.claude/agents/dotnet-developer.md.bak

mkdir -p ~/.claude/rules ~/.claude/agents ~/.claude/skills
cp global/rules/*.md ~/.claude/rules/
cp global/agents/dotnet-developer.md ~/.claude/agents/
cp -r global/skills/dotnet-feature ~/.claude/skills/
```

Skutek uboczny: `feature-backend` też używa agenta `dotnet-developer`, więc od teraz jego worker działa na Sonnecie
i czyta zasady z `~/.claude/rules/`. Treść zasad jest ta sama (przeniesiona, nie przepisana), więc jakość nie powinna się zmienić.
Powrót: `mv ~/.claude/agents/dotnet-developer.md.bak ~/.claude/agents/dotnet-developer.md`.

### 2. W projekcie

```bash
cd <repo-projektu>
cp <flow-feautres>/dotnet-feature/repo/CLAUDE.md .            # jeśli CLAUDE.md już jest, scal ręcznie
mkdir -p .claude/rules && cp <flow-feautres>/dotnet-feature/repo/.claude/rules/*.md .claude/rules/
```

Potem uzupełnij miejsca `<...>`:
- ścieżki w `paths:` dopasuj do struktury repo,
- w `CLAUDE.md` wpisz **pliki wzorcowe**: to najskuteczniejsza zasada, bo model lepiej odtwarza przykład niż opis,
- usuń pliki i sekcje, które nie dotyczą (np. `data-access.md` w projekcie bez bazy).

Szablony uzupełnisz najszybciej w sesji: „przeczytaj repo i uzupełnij `CLAUDE.md` i `.claude/rules/` według faktycznego kodu;
gdzie kod jest niespójny, pokaż warianty i zapytaj, który ma być wzorem”.

### 3. Commit w projekcie

`CLAUDE.md` i `.claude/rules/` commituj do repo projektu: zasady żyją razem z kodem.

## Projekt w trakcie implementacji („spaghetti”)

1. **Inwentaryzacja:** sesja tylko czyta repo i opisuje obecne konwencje i niespójności.
2. **Decyzja:** wybierasz docelowe konwencje i 1–2 pliki wzorcowe (w razie potrzeby najpierw je porządkujesz).
3. **Zapis:** `CLAUDE.md` + `.claude/rules/`, z sekcją „Stan kodu” (nie kopiuj wzorców ze starych plików).
4. **Bez wielkiego refaktoru:** nowy kod według zasad, stary przy okazji zmian. Większe porządki jako osobne zadania przez `/dotnet-feature`.

## Jak wygląda praca ze skillem

1. **Wymagania:** skill czyta repo, a potem w 1–2 rundach zadaje zgrupowane pytania (co, kto, gdzie, wejście, wyjście,
   brzegowe, błędy, dane, poza zakresem, kryteria akceptacji), tylko o to, czego nie da się ustalić z kodu. Kończy listą „Wymagania”.
2. **Design:** pliki, sygnatury, SQL/DDL, testy, „Otwarte pytania / założenia” (jeśli są) i **„Kroki implementacji”** (numerowane). STOP do Twojego „tak”.
3. **Implementacja:** krok po kroku. Przy S widzisz „Krok 1/3: …”, „Krok 2/3: …” z wynikiem testów po każdym. Przy M/L krokami idzie worker,
   a raport zawiera wynik po każdym kroku. Potem koordynator sam uruchamia build, testy i smoke test.
4. **Review:** S self-review (albo reviewer przy nietrywialnej logice), M/L jeden reviewer, wrażliwe +security na Opusie.
5. **Commit:** po potwierdzeniu; push tylko na prośbę.
