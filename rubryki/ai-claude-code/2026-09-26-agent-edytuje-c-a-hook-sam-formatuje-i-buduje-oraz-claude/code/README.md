# Kod do wydania #3 — hook PostToolUse (format + build) i zespołowy settings.json

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> **Hook `PostToolUse`** na `Write|Edit|MultiEdit`: po każdej edycji pliku `.cs` formatuje
> go (`dotnet format whitespace --include <plik>`) i buduje projekt; błędy kompilacji
> wracają do Claude na stderr z kodem wyjścia 2. **Zespołowy `settings.json`**: uprawnienia
> (allow na `dotnet build/test/format`, deny na `git push`, `dotnet ef database update`,
> `.env`) i hook — w repo, dla wszystkich; osobiste ustawienia w `settings.local.json`
> poza gitem. Pułapka: `--include` z bezwzględną ścieżką kończy się kodem 0 i niczego
> nie formatuje.

## Struktura

```
code/
├── claude-hooks/
│   ├── dotnet-post-edit.py       # -> .claude/hooks/dotnet-post-edit.py
│   └── settings.snippet.json     # wpięcie PostToolUse
├── claude-config/
│   ├── settings.json             # -> .claude/settings.json (uprawnienia + hook)
│   └── gitignore.snippet         # linia do .gitignore
├── sample-app/                   # mały projekt net10.0 + .editorconfig (poligon dla demo)
├── demo.py                       # 5 scenariuszy hooka na kopii sample-app
└── validate_settings.py          # lint settings.json
```

(W tym repo katalogi nie mają kropki w nazwie — kopiując do własnego projektu użyj
`.claude/hooks/` i `.claude/settings.json`.)

Wymagania: Python 3.8+ (tylko stdlib), .NET SDK z `net10.0` (dla `demo.py`; pierwszy
przebieg robi `dotnet restore`, potrzebuje NuGeta/cache).

## Jak uruchomić

Z katalogu `code/`:

```bash
dotnet run --project sample-app/Orders.App/Orders.App.csproj   # wypisze 148.22
python3 demo.py                                                 # 5 scenariuszy hooka
python3 demo.py --debug                                         # + wyjście dotnet format na stderr
python3 validate_settings.py                                    # lint settings.json
```

## Użycie w prawdziwym repo

```bash
mkdir -p .claude/hooks
cp claude-hooks/dotnet-post-edit.py .claude/hooks/
cp claude-config/settings.json .claude/settings.json    # albo scal z istniejącym
# dopisz do .gitignore:  .claude/settings.local.json
dotnet restore                                          # hook używa --no-restore
```

Repo musi mieć `.editorconfig` (bez niego `dotnet format` użyje domyślnych reguł) i
katalog z **jednym** `.csproj` nad edytowanym plikiem.

## Weryfikacja — co uruchomiono naprawdę

Środowisko: .NET SDK 10.0.400, Python 3.10.4.

```
$ python3 demo.py
OK   exit=0 (oczekiwano 0)  czysty plik, buduje sie
     plik zmieniony przez hook: nie
OK   exit=0 (oczekiwano 0)  brzydkie formatowanie -> auto-format
     plik zmieniony przez hook: tak
     stdout| dotnet-post-edit: sformatowano Order.cs wg .editorconfig - wczytaj plik ponownie przed kolejna edycja
     --- plik po formatowaniu ---
     | namespace Orders.App;
     | 
     | public record Order(int Id, string Customer, decimal NetAmount);
     | 
     | public static class OrderPricing
     | {
     |     public static decimal WithVat(Order order)
     |     {
     |         return Math.Round(order.NetAmount * 1.23m, 2);
     |     }
     | }
OK   exit=2 (oczekiwano 2)  blad kompilacji -> blokada
     plik zmieniony przez hook: nie
     stderr| BUILD NIE PRZECHODZI po edycji Order.cs (1 bledow):
     stderr|   /tmp/post-edit-demo-XXXX/sample-app/Orders.App/Order.cs(7,67): error CS1061: 'Order' does not contain a definition for 'GrossAmount' and no accessible extension method 'GrossAmount' accepting a first argument of type 'Order' could be found (are you missing a using directive or an assembly reference?)
     stderr| Napraw bledy kompilacji zanim przejdziesz dalej.
OK   exit=0 (oczekiwano 0)  inne narzedzie niz edycja
     plik zmieniony przez hook: nie
OK   exit=0 (oczekiwano 0)  plik nie-.cs
     plik zmieniony przez hook: nie

WYNIK: 5/5 przypadkow zgodnych
```

(`XXXX` = losowa nazwa katalogu tymczasowego.) `validate_settings.py` zwraca
`WYNIK: konfiguracja poprawna.` (pełny output w artykule).

### Czego NIE zweryfikowano

- Wpięcia w żywej sesji Claude Code: że hook odpali się po `Edit`, że model zobaczy stderr
  (exit 2) ani czy widzi stdout przy exit 0.
- Dokładnego kształtu payloadu `PostToolUse` — hook czyta tylko `tool_name` i
  `tool_input.file_path` (założenie z pamięci; dokumentacji nie udało się pobrać).
- Składni reguł `permissions` i pierwszeństwa deny/allow — lint sprawdza tylko kształt.
- Zachowania na dużych solucjach (czas builda), wielu `.csproj` w jednym katalogu (hook wtedy pomija).
- Skill do przeglądu SQL/indeksów: `sqlcmd` niedostępny w środowisku, więc temat odłożony.
