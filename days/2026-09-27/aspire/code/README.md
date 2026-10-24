# Kod do wydania #4 — .NET Aspire: parametry, sekrety, `WithEnvironment`, `AddExecutable`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Wymagania

- **.NET 10 SDK** (sprawdzone na `10.0.400`), pakiety Aspire `13.5.2` z nuget.org.
- Docker **niepotrzebny** — zero kontenerów. Do `env-printer` potrzebny `sh` (Linux/macOS).
- Jeśli `dotnet` nie jest w PATH: `export PATH="$HOME/.dotnet:$PATH"`.

## Fragment prasówki, którego dotyczy ten kod

> `AddParameter("nazwa")` czyta `Parameters:nazwa` z konfiguracji (brak = stan `ValueMissing`,
> zależne zasoby nie startują). `AddParameter("nazwa", "wartość")` to **stała** — konfiguracja
> jej nie nadpisze. `WithEnvironment` przyjmuje literał, parametr, `ReferenceExpression`
> albo callback z `ExecutionContext`. `AddExecutable` uruchamia dowolny proces z tymi samymi
> parametrami.

## Struktura

```
code/
├── AppHost/        # AddParameter, WithEnvironment (4 formy), AddExecutable
├── ConfigApi/      # /env (sekrety zamaskowane: długość + skrót), /health
└── Config.Verify/  # testy AppHosta: scenariusz A (parametry podane), B (brak sekretu)
```

## Uruchomienie

Z katalogu `code/`:

```bash
dotnet run --project Config.Verify/Config.Verify.csproj
```

Kod wyjścia 0 = sukces. Prawdziwy wynik (`SDK 10.0.400`, `Aspire 13.5.2`, Linux); na górze
wypisuje się jeszcze log procesu `env-printer` (intencjonalnie włączony):

```
=== A: parametry podane ===
GET config-api /env -> {"appMode":"demo","greeting":"Witaj","fixedText":"stała z kodu","runMode":"run","apiKey":"len=14;sha256=953A6F3A","dbConnectionPrefix":"Host=db.local;Database=shop;","dbConnectionHasPassword":true}
[PASS] literał: APP_MODE == demo
[PASS] AddParameter(nazwa): GREETING == Witaj (z Parameters:greeting)
[PASS] AddParameter(nazwa, wartość) jest STAŁE: FIXED_TEXT ignoruje konfigurację
[PASS] callback WithEnvironment(ctx): RUN_MODE == run
[PASS] sekret dotarł do procesu (długość i skrót się zgadzają)
[PASS] ReferenceExpression złożył connection string
  (linii logu env-printer: 2)
log env-printer -> 2026-09-27T00:45:08.9520000Z env-printer: GREETING=Witaj KEY_LEN=14
[PASS] AddExecutable dostał GREETING i sekret (KEY_LEN)
=== B: brak Parameters:api-key ===
  stan: api-key=ValueMissing
  stan: config-api=FailedToStart
  stan: env-printer=FailedToStart
[PASS] brak sekretu -> config-api NIE jest Running/Healthy (...)
WSZYSTKO OK
```

Sekrety w teście (`test-key-12345`, `p@ss-987`) to atrapy.

## Ręcznie (niezweryfikowane)

```bash
dotnet run --project AppHost --launch-profile http -- "Parameters:greeting=Hej" \
   "Parameters:api-key=moj-klucz" "Parameters:db-password=haslo"
```

Nie sprawdzaliśmy dashboardu, user-secrets ani interaktywnego uzupełniania parametrów.

## Porządek

Test sam zatrzymuje procesy. Katalogi `bin/`, `obj/` są w `.gitignore`.
